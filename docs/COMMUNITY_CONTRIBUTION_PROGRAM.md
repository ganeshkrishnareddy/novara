# NOVARA community contribution program

Status: proposed program framework for the locally prepared portal. It does not create a reward scheme, authorise spending, or publish anything. All benefits and verification mechanisms remain subject to owner decision.

Project: NOVARA — "Everything Connected. Everything Under Control."
Repository: https://github.com/ganeshkrishnareddy/novara

## 1. Principles

1. Contributions are judged on **substantive work**, never on GitHub engagement metrics.
2. Stars, forks, watches, follows, likes, or shares are voluntary user actions on GitHub. They are **not** contributions, are **not** rewarded, and are **not** required for eligibility.
3. No credits, tools, premium access, gifts, discounts, or other benefits are offered in exchange for stars, follows, or any engagement action.
4. No automation of starring, following, or similar engagement is permitted. No app feature is gated behind starring or following. No GitHub endorsement is implied.
5. A human review decides eligibility. Automated checks may inform review but do not decide it.
6. Rights and licensing of any contribution are decided by the owner; the repository has no root `LICENSE` yet, and the project is an **open-source foundation subject to final repository licensing review; licence file pending owner decision.**

## 2. Legitimate contribution activities

| Activity | Examples | Evidence expected |
| --- | --- | --- |
| Documentation | Fix errors, write guides, clarify limitations | Changed doc file with accurate claims |
| Testing and QA | Add tests, reproduce bugs, record evidence | Named test files, commands, reproducible logs |
| Bug reports | Clear reproduction steps and expected/actual behaviour | Issue with steps, environment, and evidence |
| Clean-room code | Implement a compatible local capability without copied source | Code, named tests, note on approach |
| Accessibility and UX | Keyboard/focus fixes, semantic markup, contrast checks | Before/after description and verification |
| Translations | Translate docs or UI strings | Complete, reviewed translation files |
| Security reports | Responsible disclosure of a concrete issue | Private report; no public exploit details before fix |
| Media and tutorials | Local, honest walkthroughs labelled as QA/local capture | Source files and accurate labelling |
| Website improvements | Static site fixes consistent with the claims audit | Changed site files and validator output |

Out of scope: promotional vote campaigns, engagement exchanges, "star for access" schemes, copied source from the ten reference projects, and any claim of affiliation with them.

## 3. Eligibility criteria

A contribution is eligible for review only if it:

- is substantive, specific, and attributable to a real person or documented team;
- respects the licensing boundary (no copied source from Formbricks, Meilisearch, GrowthBook, Papermark, Plane, Mautic, Chatwoot, Novu, Marketing Skills, or Sellbird; see `docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md`);
- uses accurate claims and labels local/synthetic evidence as such;
- does not request or provide any engagement metric as consideration;
- can be verified by a human reviewer from the submitted material.

A star, follow, watch, or social share is **not** a qualifying contribution. Being a first-time contributor is not a disadvantage; there are no arbitrary popularity thresholds.

## 4. Review workflow and statuses

| Status | Meaning |
| --- | --- |
| Submitted | Contribution received and logged; no assessment yet |
| Under review | A human reviewer is checking quality, claims, and licensing |
| Accepted | Contribution meets criteria and is approved for integration/merge |
| Needs changes | Reviewer requested specific changes; contributor may resubmit |
| Rejected | Contribution does not meet criteria; reason recorded respectfully |
| Benefit approved | If a benefit is available, owner-approved budget and criteria confirmed for this contribution |
| Completed | Contribution integrated/closed and any approved benefit delivered or formally declined |

Process:

1. **Submitted** — contributor submits work with a short description and evidence.
2. **Under review** — reviewer verifies substance, claims, and licensing; may request changes.
3. Decision: **Accepted**, **Needs changes**, or **Rejected**, with a written reason.
4. If a benefit is being considered, it follows a separate owner decision: **Benefit approved** only when an approved budget and published criteria exist. Otherwise the contribution still closes as **Completed** with no benefit.
5. **Completed** — record the outcome. Benefits, if any, are based on substantive contribution under published criteria and an approved budget, **never** on engagement metrics.

There is no automatic entitlement to a benefit. Any benefit is **subject to approved budget and availability** and must be approved by the owner before being promised or announced.

## 5. Privacy-conscious GitHub identity verification (optional)

If verification is needed to attribute a contribution:

- GitHub OAuth is **optional** and requires explicit, informed consent; a safe manual verification path must remain available if OAuth is unavailable or declined.
- Request the **minimum scopes** necessary to confirm account identity and contribution authorship. Do not request scopes for unrelated repository or account access.
- Use a **secure server-side session**; do not store access tokens unnecessarily, do not persist tokens in logs or client storage, and do not collect passwords.
- Provide **account deletion controls** so a contributor can withdraw stored identity data.
- Verification confirms identity only; **human review still decides eligibility**. Verification does not create entitlement, and it must not be used to track engagement or to condition app features.

No verification or OAuth integration is implemented by this document. Any implementation requires a separate privacy and security review.

## 6. Owner decisions still required

| Decision | Status |
| --- | --- |
| Whether any benefit program exists at all, and its published criteria | Pending owner decision |
| Budget approval and availability for any benefit | Pending owner decision |
| Choice and implementation of OAuth verification vs manual-only verification | Pending owner decision |
| Terms for accepting contributions given the absent root LICENSE file | Pending owner decision |
| Who performs human review and how decisions are recorded | Pending owner decision |
| Publication of this program on the website or README | Pending owner authorization |

## 7. Engagement policy reminder

No star, fork, watch, follow, or social engagement incentive of any kind. No automation of engagement. No app feature gating. No implied GitHub endorsement. Nothing in this program authorises a reward, a public announcement, or publication of the portal.

Nothing is published; the site is prepared locally only.
