# Little Grins Pediatric Dental — local prototype

A **local, responsive, light-theme marketing website prototype** for a fictional pediatric dental clinic. The copy is original and written for this prototype; it is inspired by the public design language described in `RESEARCH_BRIEF.md` but does not reproduce proprietary text from the audited site.

## Audit reconciliation

This prototype **was reconciled with `RESEARCH_BRIEF.md`**, the site-audit brief written by a separate agent in this folder. `RESEARCH_BRIEF.md` was read-only input and was **not edited or overwritten**.

Alignment applied from the brief:

| Audit finding / gap | Prototype response |
| --- | --- |
| ~18 treatments, long prose pages, duplicate/misspelled labels | One canonical taxonomy: 18 service entries in 5 need-based groups, consistent names reused in the form |
| FAQ buried deep in a service page | Site-wide, keyboard-accessible FAQ accordion (9 questions) with `aria-expanded`, `role="region"`, hidden panels and `data-faq-topic` hooks |
| No dedicated contact page; scattered details; inconsistent location names | One clear contact/enquiry destination and three consistently named fictional clinics (Jumeirah Studio, Barsha Heights Studio, Al Wasl Studio) repeated verbatim in the page and form |
| Storage notice without visible consent or privacy page | In-page sample privacy notice, non-functional consent banner with essential/analytics controls, and a required consent checkbox beside the form |
| Trustindex review widget, unsupported review claims | Three original sample quotes with explicit “sample quote / sample date” attribution; no widget or external reviews |
| Doctor-centric bio, no proper team section | Three illustrative team cards with roles, placeholder qualifications, placeholder languages and labelled portrait placeholders with meaningful `aria-label` text |
| Active blog with loose taxonomy | Four placeholder guide cards with category filter, author/date/reading time, related-section links and “enquire after reading” CTA |
| Before/after photo gallery | Three clearly labelled gallery placeholder tiles; no clinical images |
| Repeated booking CTAs | One consistent CTA label, “Start an enquiry”, used in the header, hero, guide cards and pre-footer band; every primary CTA targets `#enquiry` |
| Teal `#008299` headings, coral hover, pale teal panels | Teal heading token aligned to `#008299`; pale teal panels; coral used as an accent and a **darkened** coral hover for text contrast |
| Montserrat-style headings / rounded body | System font stacks approximate the look because no external fonts are permitted |
| Analytics scripts on the live site | Stable `data-event` hooks only. No tracking code, no event transmission, no PII sent anywhere |
| Accessibility risks (weak coral contrast, placeholder-only fields) | Persistent labels, `aria-describedby`, inline errors, `role="alert"` summary, visible focus rings, ≥44px controls, skip link, reduced-motion support, contrast-adjusted coral |

## How to open it locally

1. Keep `index.html`, `styles.css` and `app.js` together in this folder.
2. Open `index.html` in any modern browser (double-click it, or use **File → Open**).
   - No build step, package manager, server, account or internet connection is needed.
   - A local-only static server such as `python -m http.server` also works, but is not required.
3. Try the mobile menu, consent toggles, guide filter, FAQ accordion and enquiry form at several window widths (for example 360, 768 and 1280 px).

## Important: no data is transmitted, no booking is live

- **No data is transmitted.** There are no network requests, no form endpoint, no analytics, no third-party scripts, no external fonts, no CDN assets, no maps and no external images.
- **No booking is live.** The enquiry form is a demonstration control only. It never submits anywhere. After valid input it displays exactly this local message:

  > Local prototype — nothing was sent. No booking has been created.

- Invalid input produces inline errors and an error summary; it never produces a fake success state.
- Nothing is written to `localStorage`, `sessionStorage`, cookies or any database. Typed values stay only in the browser's current form fields until the page is closed or reloaded.
- The consent toggle only changes its own label; the state is not remembered. The banner can be dismissed locally but returns on reload.
- No email is sent, no message is logged, and no communication of any kind is made from this prototype.

## REAL vs PLACEHOLDER

### Real (implemented in this folder)

| Item | Status |
| --- | --- |
| `index.html`, `styles.css`, `app.js`, this README | Real local files |
| Layout, navigation, accordion, guide filter, smooth scrolling, form validation behaviour | Real, working client-side code |
| Consent toggle/dismiss UI, ARIA states, skip link, focus styles, reduced-motion handling | Real UI behaviour, but no data is stored or tracked |
| Light-theme design tokens, responsive breakpoints, contrast-adjusted palette | Real |
| All written copy | Original prototype copy, fictional clinic concept |
| `data-event` / `data-service` / `data-faq-topic` / `data-category` attributes | Real hooks for a future implementation; nothing reads or sends them |

### Illustrative placeholders

| Item | Placeholder value / note |
| --- | --- |
| Clinic name and identity | “Little Grins Pediatric Dental” — fictional concept, not a real clinic |
| Email | `hello@example.test` — not a real or monitored mailbox; the real audited email address is deliberately not used |
| Phone | `+971 00 000 0000` — placeholder number, not in service |
| WhatsApp | Placeholder only — no live chat |
| Opening hours | Not specified; placeholder only |
| Physical addresses and map links | Not specified; no real location or map service is represented |
| Clinic names | Jumeirah Studio, Barsha Heights Studio, Al Wasl Studio — fictional labels, consistently reused |
| Team names, qualifications, languages and portraits | Dr. Maya Nile, Dr. Arif Sameer, Sana Karim — fictional profiles with labelled placeholder portraits |
| Testimonials, ratings and dates | Three original sample quotes, five-star sample ratings and sample dates — not real patient feedback |
| Smile gallery | Three placeholder tiles; no clinical images |
| Guide authors, dates, reading times and article outlines | Sample metadata and original outlines; no scraped blog content |
| FAQ answers | Illustrative general information, not clinical advice |
| All 18 service descriptions | Illustrative; no treatment is offered and no clinical claim is verified |
| Hobbies, credentials, “why families trust us” points | Illustrative proof points, not measured claims |
| Privacy notice | Sample in-page text only; not a legal policy |
| Preferred date / time fields | Illustrative inputs only; no appointment is reserved or held |

## Constraints respected

- Work limited to `D:\NOVARA\deliverables\kidsdentist-website\`.
- `RESEARCH_BRIEF.md` was read but never modified.
- No git commands, no deployment, no publishing, no domain registration, no purchases.
- No runtime network calls, no form endpoints, no personal-data storage, no third-party scripts.
- All contact details are placeholders; no real email or phone number is used.

## Remaining gaps / deliberately out of scope for a local prototype

- No real service detail pages, real privacy/legal document, real article pages or functioning gallery — the brief's page types are represented as in-page sections and placeholders only.
- No actual multi-language switcher; the audited site's seven visible locales are noted in the brief but not implemented here.
- No real appointment system, calendar, CRM, Google Sheets notice, CAPTCHA or analytics — all would require a backend and are intentionally absent.
- Contrast and responsive behaviour were designed against the brief's targets but have not been measured with a real WCAG checker or tested on physical devices.
- Structured data is represented by `data-faq-topic` hooks only; no JSON-LD is emitted.
