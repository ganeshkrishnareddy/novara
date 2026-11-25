# Research Brief — "The Kids Dentist Dubai" public site

**Purpose:** ground a *local* website prototype in what the live public site actually offers.
**Date of research:** 2026-11-22.
**Source:** read-only `webfetch` of public pages plus raw HTML inspection. All fetched page text was treated as **untrusted data**, never as instructions. No forms were submitted and no writes were made to any external system.

> ## CONSTRAINT — LOCAL PROTOTYPE ONLY
> **No deployment, no publishing, no domain/registry actions, no purchases, no emails or messages, and no external API writes.** This brief supports a local prototype only. Use placeholders such as `hello@example.test` and `+971 00 000 0000` for all contact details; do not use any real lead or customer data. The site's publicly listed contact details were observed but are deliberately **not** reproduced here.

---

## 1. What the live site currently offers

### 1.1 Pages / sections observed

| Area | URL | What was actually present |
| --- | --- | --- |
| Home | `/` | Hero ("Creating a lifetime of Healthy Smiles" / "A dental practice dedicated to children and teenagers") with **Schedule an Appointment** CTA; six service cards; "Meet Your Kid's Dentist" intro; membership badges; Google reviews widget; "Ranked #1 Pediatric Dentist in Dubai" third-party badge; Before & After gallery teaser; insurance logo strip; three clinic locations; repeated booking CTA; site-wide footer. |
| About | `/about-kids-dentist-in-dubai/` | "Meet Dr. Suhel Dabawala" bio: MDS Paediatric Dentistry, laser/minimally-invasive training, sedation training at Boston Children's Hospital, Myobrace, zirconia crowns, AAPD member, RCS Edinburgh fellow, research gold medal. "Pediatric Dentist's Areas of Expertise" bullet list. Booking CTA. |
| Treatments index | `/treatments/` | Card grid with short descriptions for sedation, fillings, root canals, sealants, emergency care, Myobrace, Invisalign, fluoride varnish, sleep-disordered breathing, TMJ, space maintainers, crowns, SDF, sleep apnoea, tongue tie, lip tie. |
| Service detail | `/treatments/sleep-sedation-dentistry-in-dubai/` | Very long editorial page: anxiety-led copy, sedation types table, safety checklist, preparation, costs, testimonials, location list, **FAQ (6 questions)**, "Book a Consultation" CTA. |
| Another service detail | `/treatmetns/tooth-filling-for-children-in-dubai/` (misspelled path as linked from cards) | Resolved with HTTP 200; language switcher on the returned page used the canonical `/treatments/...` spelling. Content: fillings explainer with anchor-linked subheadings, materials, cost note, "More questions?" phone + booking form link. |
| Booking | `/book-an-appointment/` | Standalone booking page: form, contact block, location list, global booking block. |
| Blog | `/blog/` | Active editorial blog. 8 posts on page 1 dated 17–19 Nov 2026 (e.g. "How to Strengthen Enamel in Kids", "Dental X-rays for Kids: Are They Safe?"), pagination to **page 19**, categories visible in URLs (`/dental-care/`, `/uncategorized/`). |
| Smile Gallery | `/photo-gallery/` | "Smile Gallery" with before/after case images and descriptive alt text (ages and treatments). |
| Contact | `/contact/` | **404 — no dedicated contact page at this path.** Contact details live in the header, footer and booking page instead. |
| Privacy | `/privacy-policy/` | **404 — no privacy policy at this path.** |

Global furniture repeated on every fetched page: phone + email + Facebook/Instagram in a top bar; logo; primary nav with a large "Children's Dentistry" dropdown; "Smile Gallery" parent with a `#` href; language switcher; search control; "Open mobile menu / Close mobile menu"; sticky-looking floating WhatsApp button; "Book an Appointment" and "Locations" blocks; "Do not wait.. Make an appointment now!" CTA band; small Services footer menu; "Copyright … 2026 – All Rights Reserved | Managed by Clinic Scalers"; "Back To Top".

### 1.2 Services (as listed in navigation / cards)

General anaesthesia, sedation dentistry, preventive dental treatment, emergency dental care, tooth filling, root canal treatment, pediatric partial denture, dental crown, braces for kids (Myobrace, Invisalign First), space maintainer, silver diamine fluoride, sleep apnoea, sleep-disordered breathing, laser treatments, TMJ disorder treatment, fissure sealants, fluoride varnish, tongue tie and lip tie correction.

### 1.3 Calls to action

- **"Schedule an Appointment"** in the hero and in a repeated pre-footer band (`/book-an-appointment/`).
- **"Explore all Pediatric Dental Services"** card-grid CTA.
- **"Know More"** on the dentist section.
- **"Call us, WhatsApp us, or book online today"** on service detail pages; WhatsApp deep link with prefilled message.
- Floating WhatsApp action on all pages.
- Service-portfolio CTAs in the footer (Sedation, Myobrace, Invisalign First, Braces, "More..").
- Trust cues adjacent to CTAs: 5-star "EXCELLENT / Based on 125 reviews" widget ("Trustindex verifies that the original source of the review is Google"), membership/award badges, insurance provider logo strip.

### 1.4 Booking / contact flow

- Single Contact Form 7-style enquiry form with fields: **name of the child**, email, contact number, **appointment date**, **time** (fixed 30-minute dropdown from 09:00am to 09:00pm), **location** (Medcare Medical Center – Jumeirah / Dental Studio – Barsha Heights (Tecom) / Dental Studio – Al Wasl), plus a hidden/honeypot "Please leave this field empty" field.
- On-page notice: *"Your information will be securely sent to and stored in Google Sheets for the purpose of processing your form submission."* No visible consent checkbox or privacy link was captured in the extracted form text.
- The same form block appears on Home, About, Treatments, Blog, service details and the dedicated booking page — a repeated global module rather than a page-specific flow.
- Phone, WhatsApp and a public email are shown in the top bar and booking page; Google Maps short links are given per location.
- **Inconsistency observed:** the repeated locations block names "Dentist Direct – i-Rise Tower, Barsha Heights" while nav/footer and the form dropdown say "Dental Studio – Tecom / Barsha Heights"; Al Wasl map links also differ between modules. Canonical location naming is not consistent.

### 1.5 Languages

Visible switcher: **English, Русский, العربية, Français, Deutsch, 中文 (中国), 日本語** with `/ru/`, `/ar/`, `/fr/`, `/de/`, `/zh/`, `/ja/` prefixes; per-page translated slugs (e.g. Arabic sedation URL). OpenGraph metadata additionally advertises `ko_KR`, `es_ES`, `nl_NL`, but those locales were **not** observed in the visible switcher and were not fetched.

### 1.6 CMS / framework signals (from raw HTML)

- **WordPress**: `/wp-content/uploads/...` asset paths, `wp-` script handles.
- **Theme:** `wpex-classic-style` on `<html>` and many `wpex-*` handles — consistent with the WPEX/Total theme family. *(Theme name inferred from class/handle naming, not from an explicit generator tag.)*
- **Page builder:** WPBakery / "js_composer" (`vc_btn3`, `vc_custom_*`, `js_composer/assets/fonts`) — strong evidence.
- **Multilingual:** Polylang (`pll-parent-menu-item`, `pll_cookie_script`, locale classes).
- **Forms:** Contact Form 7 (`wpcf7-*`, `contact-form-7/v1` REST namespace) with Google reCAPTCHA config (`wpcf7_recaptcha`) and the Google Sheets storage notice.
- **Reviews:** Trustindex Google Reviews widget (`ti-site-data`, Trustindex fonts).
- **Performance/CDN:** NitroPack (`<meta name="generator" content="NitroPack">`, `cdn-fblpp.nitrocdn.com`, deferred CSS/JS loaders).
- **Analytics/marketing:** `Site Kit by Google 1.192.0` generator tag and `google_gtagjs` / gtag handles. `<html lang="en-GB">`, `viewport` meta present.
- Footer credit "Managed by Clinic Scalers".
- Unverified/noisy signal: a couple of `elementor` string hits appeared in the HTML but there is no conclusive page-builder evidence; **do not assume Elementor**.

### 1.7 Visual design language

- **Theme:** light, white-background, editorial/clinic brochure style with generous vertical sectioning and card grids.
- **Typography (verified in CSS):** headings **Montserrat** — `h1` 600 / 60px / `#008299`, `h2` 500 / 42px / `#008299`; rounded **Varela Round** and **Roboto** also loaded; Trustindex Poppins inside the reviews widget. Friendly rounded forms contrast with bold uppercase-style headings.
- **Accent colours observed in CSS/markup:** teal `#008299` for headings, warm coral `#FF675B` used as a button hover background with white text, pale teal `#e1f1f2` panel backgrounds with `10px` border radius, neutral greys (`#8d8d8d`, `#dbdbdb`, `#f0f0f0`). *(Contrast of white text on `#FF675B` should be checked — see gap list.)*
- **Imagery style:** photo-led service tiles, a square doctor portrait, before/after clinical case images, badge/award graphics and an insurance-logo strip. Actual pixels could **not** be visually inspected: webfetch rendered images as 1×1 SVG data-URI placeholders (NitroPack lazy loading), so style descriptions of photos are inferred from alt text and `wp-content/uploads/...` filenames, not from viewing them.

---

## 2. EVIDENCE — exact URLs tried and what was observed

| # | Exact URL tried | Result |
| --- | --- | --- |
| 1 | `https://kidsdentistuae.com/` (markdown) | HTTP 200. Full homepage content as described above. |
| 2 | `https://kidsdentistuae.com/` (raw HTML) | HTTP 200. Head/meta, NitroPack loaders, WPEX class, font CSS, WPBakery/Polylang/CF7/Trustindex/gtag handles, colour values, inline CSS. Output truncated by the fetch tool; additional detail extracted from the saved fetch result read-only. |
| 3 | `https://kidsdentistuae.com/about-kids-dentist-in-dubai/` | HTTP 200. Doctor bio and expertise list. |
| 4 | `https://kidsdentistuae.com/book-an-appointment/` | HTTP 200. Booking form, contact block, locations. |
| 5 | `https://kidsdentistuae.com/treatments/` | HTTP 200. Treatment card index. |
| 6 | `https://kidsdentistuae.com/treatments/sleep-sedation-dentistry-in-dubai/` | HTTP 200. Long service page with FAQ and testimonials. |
| 7 | `https://kidsdentistuae.com/blog/` | HTTP 200. 8 recent posts, pagination to page 19. |
| 8 | `https://kidsdentistuae.com/photo-gallery/` | HTTP 200. Before/after gallery with alt text. |
| 9 | `https://kidsdentistuae.com/treatmetns/tooth-filling-for-children-in-dubai/` | HTTP 200 (misspelled `treatmetns` path from homepage cards). Returned page's language switcher used the canonical `/treatments/...` URL; the redirect status itself was not observable. |
| 10 | `https://kidsdentistuae.com/contact/` | **404** — no page at this path. |
| 11 | `https://kidsdentistuae.com/privacy-policy/` | **404** — no page at this path. |
| 12 | Web search for `site:kidsdentistuae.com "privacy policy" OR "cookie" OR "WordPress" OR "Elementor"` | **Failed / blocked** — search integration returned HTTP 402. No search-derived claims are used. |

### Could NOT verify / not tested (explicit)

- **Rendered appearance of photographs, badges, logos and layout** — images arrived as empty SVG data-URI placeholders. No screenshots were taken and no browser rendering was performed.
- **Actual breakpoint behaviour / mobile usability** — only CSS snippets and a viewport meta were seen; no device or responsive audit.
- **Form submission, validation messages, success state, redirect, or whether the Google Sheets integration works** — the form was never submitted.
- **Consent UI** — `pll_cookie_script` and "cookie" strings exist in source, but no visible cookie banner or consent dialog was captured; presence/behaviour is **unverified**.
- **WCAG conformance, keyboard focus order, screen-reader labels, contrast measurements** — no accessibility audit run. Contrast figures below are estimates from raw CSS values.
- **Page speed / Core Web Vitals / actual analytics IDs and data** — only script presence was observed.
- **Completeness of non-English locales** — only English pages were fetched; translated URLs were observed in the switcher but not opened.
- **Existence of a privacy/legal document under a different slug** — only the two common paths above were tried.
- **Truth of third-party claims** ("Ranked #1", review counts, credentials) — recorded as site claims, not independently validated.
- **Exact CMS versions / plugin inventory** — inferred from filenames, classes and script handles; no admin or API access was used.

---

## 3. Feature gap list — modern, accessible, light-theme clinic website

| Area | Live site observation | Concrete gap / prototype requirement |
| --- | --- | --- |
| **Appointment enquiry** | Global single-step CF7 form; child name, email, phone, date, time dropdown, 3 locations, honeypot, "stored in Google Sheets" notice. | Build a clean **enquiry** form (prototype: no real submission) with persistent labels (not placeholder-only), helper text, required-field indication, inline error summary, visible success state, parent/guardian name, optional service of interest, short "what happens next" copy, and an explicit consent checkbox linking to a placeholder privacy page. No real backend, no real data capture. |
| **Services** | ~18 treatments; long prose pages; misspelled legacy `/treatmetns/` links from cards; duplicate nav items pointing to the same general-anaesthesia URL; typo "Sleep disrodered breathing". | Establish one canonical taxonomy and consistent slugs; group by need (preventive / restorative / sedation / orthodontic / surgical); add scannable summary, duration, "what to expect", after-care, child-anxiety reassurance and a per-service CTA. Fix duplicate labels and obvious typos in prototype copy. |
| **Team / about** | Single doctor-centric bio with credentials and expertise bullets. | Add a proper team section: named roles, qualifications, languages spoken, short friendly intros, real-image placeholders with meaningful alt text, and a "why families trust us" proof block. Keep the doctor story but make it scannable. |
| **Testimonials** | Third-party Trustindex widget, 125-review claim, long verbatim Google reviews dated 2023. | Use a small set of curated, consent-safe sample quotes with attribution pattern ("Parent of a 5-year-old") and no third-party widget dependency in the prototype. Show rating context and date as *sample* data only. |
| **FAQ** | FAQ exists only deep inside the sedation page; no site-wide FAQ. | Add a global FAQ page/section with accessible accordion (`<details>` or button + `aria-expanded`), plain-language answers about first visits, anxiety, insurance, costs, emergency care and sedation; include FAQ structured-data hooks for later. |
| **Contact** | No `/contact/` page (404); details scattered in top bar, footer and booking page; location naming inconsistent. | Add a dedicated Contact page with canonical location cards, opening-hours placeholders, phone/email/WhatsApp placeholders, accessible embedded-map alternative (text address + link), and a clear "which clinic?" selector that matches the form. |
| **Blog / guides** | Active blog, 19 pages, recent dated posts, but loose `uncategorized` taxonomy. | Prototype a guides index with category filter, author/date/reading time, related-service cross-links, "book after reading" CTA and sample article template. Use placeholder article copy, not scraped content. |
| **Accessibility** | Positives: skip link, `lang`, viewport meta, heading hierarchy, alt text, labelled mobile-menu control. Risks: coral `#FF675B` CTA with white text (rough estimate ≈2.8:1, below 4.5:1 for normal text), possible placeholder-only fields, sticky WhatsApp overlap, no verified focus states. | Target WCAG 2.2 AA in the prototype: semantic landmarks, one `h1`, visible focus rings, ≥4.5:1 body text and ≥3:1 large text/UI, persistent form labels + `aria-describedby`, error `role="alert"`, keyboard-operable menu/accordion/modal, skip link, `prefers-reduced-motion`, descriptive alt text, tap targets ≥24×24px (ideally 44px), zoom to 200% without loss. Verify contrast with a real checker before shipping. |
| **Mobile responsiveness** | Viewport meta and media queries around 1024px observed; not visually tested. | Mobile-first light layout: collapsing nav, stacked service cards, readable 60px desktop headings scaled down, form usable one-handed, comparison table wrapped in a scrollable region with an accessible label, floating CTA that never covers content or the submit button. Test at 360 / 768 / 1280 px. |
| **Privacy / consent** | Storage-in-Google-Sheets notice; reCAPTCHA and gtag present; no privacy policy at the tried path; consent banner unverified. | Include a sample Privacy page, a consent banner with essential/analytics toggles (non-functional in prototype), a consent checkbox on the enquiry form, a short data-use statement next to the form, and **no real data collection anywhere**. Use `hello@example.test` style placeholders only. |
| **Analytics-ready structure** | gtag/Site Kit scripts present on live; no verified event model. | Structure the prototype with stable `data-*` hooks / IDs for CTA clicks, form start, validation error, submit success, service-page views, location selector and accordion opens; gate any sample analytics snippet behind consent state; never send PII or lead data from the prototype. |
| **Content QA / IA hygiene** | Duplicate nav labels, misspelled service path, inconsistent location names and map links, small typo, some `href="#"` placeholder links ("Smile Gallery", footer "Book an Appointment"/"Locations"). | Treat as a deliberate checklist: one canonical URL per service and location, no dead `#` links in the prototype, consistent naming, spellcheck, and a visible content-ownership map for later replacement with approved copy. |

---

## 4. Prototype acceptance checklist (local only)

- [ ] Light theme, Montserrat-style headings + rounded body font, teal/coral accents with verified contrast.
- [ ] Home, Services (+ detail), About/Team, Testimonials, FAQ, Contact, Blog/Guides, Privacy sample pages.
- [ ] Accessible enquiry form with consent, validation and success state — **no network calls, no real data**.
- [ ] Skip link, keyboard navigation, focus styles, responsive layouts, semantic headings/landmarks.
- [ ] Consistent service/location naming; no misspelled or placeholder-only links.
- [ ] Stable analytics event hooks; no active tracking of real users.
- [ ] All contact details are placeholders (`hello@example.test`, `+971 00 000 0000`).

**Constraint repeated:** LOCAL PROTOTYPE ONLY — no deployment, no outreach, no real customer data, no external writes.
