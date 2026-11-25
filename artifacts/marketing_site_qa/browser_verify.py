"""Local-only Chrome DevTools Protocol verification for the NOVARA portal.

No external requests: every URL is http://127.0.0.1. Chrome is launched headless
with a dedicated profile. All observations are written as JSON for the record.
"""
from __future__ import annotations

import argparse
import base64
import itertools
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUT = Path(r"D:\NOVARA\artifacts\marketing_site_qa")
HTTP_PORTS = {"site": 8766, "subpath": 8767, "app": 8765}


class CDP:
    def __init__(self, port: int, url_match: str):
        deadline = time.time() + 25
        target = None
        while time.time() < deadline and target is None:
            try:
                raw = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/json", timeout=2
                ).read()
                targets = json.loads(raw)
                pages = [
                    t for t in targets
                    if t.get("type") == "page" and url_match in t.get("url", "")
                ]
                if pages:
                    target = pages[0]
            except Exception:
                time.sleep(0.25)
        if target is None:
            raise RuntimeError(f"No CDP page target containing {url_match!r} on port {port}")
        self.target = target
        self.ws = websocket.create_connection(
            target["webSocketDebuggerUrl"], timeout=25, suppress_origin=True
        )
        self.ids = itertools.count(1)
        self.events: list[dict] = []
        self.call("Runtime.enable")
        self.call("Log.enable")
        self.call("Page.enable")

    def call(self, method: str, params: dict | None = None):
        mid = next(self.ids)
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)

    def js(self, expression: str):
        result = self.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        if result.get("exceptionDetails"):
            raise RuntimeError(str(result["exceptionDetails"]))
        return result.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


SITE_JS = r"""
(() => {
  const q = (s) => document.querySelector(s);
  const meta = (name, attr = 'name') => {
    const el = q(`meta[${attr}="${name}"]`);
    return el ? el.getAttribute('content') : null;
  };
  const imgs = Array.from(document.images).map((i) => ({
    src: i.getAttribute('src'),
    loaded: !!(i.complete && i.naturalWidth > 0),
    naturalWidth: i.naturalWidth,
    alt: i.getAttribute('alt') || ''
  }));
  const anchors = Array.from(document.querySelectorAll('a')).map((a) => ({
    href: a.getAttribute('href'),
    target: a.target,
    rel: a.rel
  }));
  const badFragments = Array.from(document.querySelectorAll('a[href^="#"]'))
    .map((a) => a.getAttribute('href').slice(1))
    .filter((id) => id && !document.getElementById(id));
  const video = q('video');
  const source = video ? video.querySelector('source') : null;
  let ldType = null;
  try {
    ldType = JSON.parse(q('script[type="application/ld+json"]').textContent)['@type'];
  } catch (e) { ldType = 'PARSE_ERROR: ' + e.message; }
  return {
    url: location.href,
    title: document.title,
    description: meta('description'),
    canonical: q('link[rel="canonical"]')?.getAttribute('href'),
    ogTitle: meta('og:title', 'property'),
    ogImage: meta('og:image', 'property'),
    twitterCard: meta('twitter:card'),
    jsonLdType: ldType,
    lang: document.documentElement.lang,
    viewport: meta('viewport'),
    themeColor: meta('theme-color'),
    sections: Array.from(document.querySelectorAll('main section')).map((s) => s.id || '(hero)'),
    headings: document.querySelectorAll('main h2').length,
    images: imgs,
    anchors,
    badFragments,
    unsafeBlank: anchors.filter((a) => a.target === '_blank' &&
      !(a.rel || '').toLowerCase().includes('noopener')).map((a) => a.href),
    video: video ? {
      resolvedSrc: source ? new URL(source.getAttribute('src'), location.href).href : null,
      readyState: video.readyState,
      networkState: video.networkState,
      error: video.error ? video.error.message : null,
      hasControls: video.controls
    } : null,
    cssApplied: getComputedStyle(q('.site-header')).position === 'sticky',
    cookieValue: document.cookie,
    externalRequests: performance.getEntriesByType('resource')
      .map((r) => r.name).filter((u) => !u.startsWith(location.origin)),
    bodyBg: getComputedStyle(document.body).backgroundColor,
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    navDisplay: q('#primary-nav') ? getComputedStyle(q('#primary-nav')).display : null,
    toggleDisplay: q('#nav-toggle') ? getComputedStyle(q('#nav-toggle')).display : null,
    navExpanded: q('#nav-toggle') ? q('#nav-toggle').getAttribute('aria-expanded') : null,
    mojibake: /[ÃÂ]|â€|\ufffd/.test(document.body.innerText)
  };
})()
"""


def console_problems(cdp: CDP):
    problems = []
    for ev in cdp.events:
        method = ev.get("method", "")
        if method == "Runtime.exceptionThrown":
            problems.append("EXCEPTION: " + str(ev.get("params", {}).get("exceptionDetails", {}).get("text")))
        elif method == "Log.entryAdded":
            entry = ev.get("params", {}).get("entry", {})
            if entry.get("level") in ("error", "warning"):
                problems.append(f"{entry.get('level').upper()}: {entry.get('text')}")
        elif method == "Runtime.consoleAPICalled" and ev.get("params", {}).get("type") == "error":
            problems.append("CONSOLE: " + " ".join(
                str(a.get("value", a.get("description", "")))
                for a in ev.get("params", {}).get("args", [])
            ))
    return problems


def check_site(port: int, label: str):
    http_port = HTTP_PORTS[label]
    url = f"http://127.0.0.1:{http_port}/" if label != "subpath" else f"http://127.0.0.1:{http_port}/novara/"
    profile = OUT / f"cdp-{label}-profile"
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        f"--remote-debugging-port={port}", "--remote-allow-origins=*",
        f"--user-data-dir={profile}", "--window-size=1440,900", url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = {"url": url, "label": label, "viewports": {}, "checks": {}}
    cdp = None
    try:
        cdp = CDP(port, url)
        time.sleep(1.2)
        # Trigger loading="lazy" images before asserting they loaded.
        cdp.js("""
        (async () => {
          document.documentElement.style.scrollBehavior = 'auto';
          for (const img of Array.from(document.images)) {
            img.loading = 'eager';
            img.scrollIntoView({block: 'center', behavior: 'instant'});
            await new Promise((r) => setTimeout(r, 250));
          }
          window.scrollTo({top: 0, behavior: 'instant'});
          return true;
        })()
        """)
        time.sleep(0.4)
        cdp.events.clear()
        base = cdp.js(SITE_JS)

        checks = result["checks"]
        checks["title_has_novara"] = "NOVARA" in (base["title"] or "")
        checks["description_present"] = bool(base["description"])
        checks["canonical_present"] = bool(base["canonical"])
        checks["og_and_twitter_present"] = all([base["ogTitle"], base["ogImage"], base["twitterCard"]])
        checks["json_ld_valid"] = base["jsonLdType"] == "SoftwareApplication"
        checks["lang_en"] = base["lang"] == "en"
        checks["css_loaded"] = base["cssApplied"]
        checks["all_images_loaded"] = all(i["loaded"] for i in base["images"])
        checks["all_images_have_alt"] = all(bool(i["alt"]) for i in base["images"])
        checks["all_fragments_resolve"] = len(base["badFragments"]) == 0
        checks["blank_links_safe"] = len(base["unsafeBlank"]) == 0
        checks["video_source_resolves"] = bool(base["video"] and base["video"]["resolvedSrc"])
        checks["video_has_controls"] = bool(base["video"] and base["video"]["hasControls"])
        checks["sections_present"] = len(base["sections"]) >= 10
        checks["no_mojibake_in_render"] = base["mojibake"] is False
        checks["no_cookies_set"] = base["cookieValue"] == ""
        checks["no_external_requests"] = len(base["externalRequests"]) == 0
        checks["light_background"] = base["bodyBg"] in ("rgb(255, 255, 255)", "rgb(247, 248, 247)")
        result["base"] = base

        # Verify media resources with real HEAD requests from the browser context.
        media = cdp.js(r"""
        (async () => {
          const urls = Array.from(document.images).map(i => new URL(i.getAttribute('src'), location.href).href)
            .concat(Array.from(document.querySelectorAll('video source')).map(s => new URL(s.getAttribute('src'), location.href).href))
            .concat([new URL('assets/css/styles.css', location.href).href,
                     new URL('assets/js/site.js', location.href).href]);
          const out = [];
          for (const u of urls) {
            try { const r = await fetch(u, {method: 'GET'}); out.push({u, status: r.status}); }
            catch (e) { out.push({u, status: -1, error: String(e)}); }
          }
          return out;
        })()
        """)
        result["media_status"] = media
        checks["all_local_assets_http_200"] = all(m.get("status") == 200 for m in media)

        for name, w, h, mobile in (("desktop", 1440, 900, False),
                                   ("tablet", 820, 1100, False),
                                   ("mobile", 390, 844, True)):
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": w, "height": h, "deviceScaleFactor": 1, "mobile": mobile,
            })
            cdp.js("window.scrollTo(0,0)")
            time.sleep(0.5)
            vp = cdp.js(SITE_JS)
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "fromSurface": True, "captureBeyondViewport": False,
            })
            png = OUT / f"cdp_{label}_{name}.png"
            png.write_bytes(base64.b64decode(shot["data"]))
            entry = {
                "width": vp["innerWidth"],
                "scrollWidth": vp["scrollWidth"],
                "no_horizontal_overflow": vp["scrollWidth"] <= vp["innerWidth"] + 1,
                "toggle_display": vp["toggleDisplay"],
                "nav_display": vp["navDisplay"],
                "screenshot": str(png),
            }
            if name == "mobile":
                cdp.js("document.getElementById('nav-toggle').click()")
                time.sleep(0.25)
                after = cdp.js(SITE_JS)
                entry["nav_opens_on_mobile"] = (
                    after["navDisplay"] == "flex" and after["navExpanded"] == "true"
                )
                cdp.js("document.getElementById('nav-toggle').click()")
                time.sleep(0.2)
            result["viewports"][name] = entry
        cdp.events.clear()
        result["console_problems"] = console_problems(cdp)
        checks["no_console_errors"] = len(result["console_problems"]) == 0
    finally:
        if cdp:
            cdp.close()
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
    return result


def check_app(port: int):
    url = f"http://127.0.0.1:{HTTP_PORTS['app']}/"
    profile = OUT / "cdp-app-profile"
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        f"--remote-debugging-port={port}", "--remote-allow-origins=*",
        f"--user-data-dir={profile}", "--window-size=1440,1000", url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = {"url": url}
    cdp = None
    try:
        cdp = CDP(port, url)
        time.sleep(3.5)
        info = cdp.js(r"""
        (() => {
          const t = document.body.innerText || '';
          return {
            title: document.title,
            textLength: t.length,
            head: t.slice(0, 2600),
            mojibake: /[ÃÂ]|â€|\ufffd/.test(t),
            hasSearchPlaceholder: !!document.querySelector('[placeholder*="Search"]'),
            communityNav: Array.from(document.querySelectorAll('a,button')).some(
              (e) => /community/i.test(e.textContent || ''))
          };
        })()
        """)
        result["app"] = info
        result["app"]["no_mojibake_in_render"] = info["mojibake"] is False
    finally:
        if cdp:
            cdp.close()
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
    return result


def check_community(port: int):
    url = f"http://127.0.0.1:{HTTP_PORTS['app']}/"
    profile = OUT / "cdp-community-profile"
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        f"--remote-debugging-port={port}", "--remote-allow-origins=*",
        f"--user-data-dir={profile}", "--window-size=1440,1000", url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = {"url": url}
    cdp = None
    try:
        cdp = CDP(port, url)
        time.sleep(3.0)
        info = cdp.js(r"""
        (() => {
          try {
            if (typeof window.loadCommunity !== 'function') {
              return {ok: false, error: 'loadCommunity is not global'};
            }
            if (!document.getElementById('view')) {
              const mount = document.createElement('div');
              mount.id = 'view';
              document.body.appendChild(mount);
            }
            window.loadCommunity(999999);
            const v = document.getElementById('view') || document.body;
            const text = v.innerText || '';
            const links = Array.from(v.querySelectorAll('a[href*="github.com"]'))
              .map((a) => ({href: a.getAttribute('href'), safe: a.target === '_blank' &&
                (a.rel || '').toLowerCase().includes('noopener')}));
            return {
              ok: true,
              heading: /NOVARA community/.test(text),
              policy: /No GitHub action is automated/.test(text),
              voluntary: /free|gated|voluntary/i.test(text),
              mojibake: /[ÃÂ]|â€|\ufffd/.test(text),
              githubLinks: links.length,
              allBlankSafe: links.every((l) => l.safe),
              textHead: text.slice(0, 1600)
            };
          } catch (e) { return {ok: false, error: String(e)}; }
        })()
        """)
        result["community"] = info
    finally:
        if cdp:
            cdp.close()
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--mode", choices=["site", "subpath", "app", "community"], required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == "app":
        result = check_app(args.port)
    elif args.mode == "community":
        result = check_community(args.port)
    else:
        result = check_site(args.port, args.mode)
    path = OUT / f"verify_{args.mode}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    checks = result.get("checks", {})
    if checks:
        for k, v in checks.items():
            print(f"[{'PASS' if v else 'FAIL'}] {k}")
        print(f"SUMMARY {sum(1 for v in checks.values() if v)}/{len(checks)}")
    else:
        print(json.dumps(result.get("app", {}), indent=2)[:3000])
    print("WROTE", path)


if __name__ == "__main__":
    main()
