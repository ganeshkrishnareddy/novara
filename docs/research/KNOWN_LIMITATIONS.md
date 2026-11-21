# Known limitations — initial

Recorded limitations as of 2026-11-22. This list grows as audits land.

## Environment

- Container tooling is not yet available in the development environment, so no container can be built or run yet. Local Docker Compose installation and all container-based testing are unavailable.
- No CI runner, remote Git host or test database exists yet.
- No code signing, notarisation or store submission credentials exist.

## Scope reality

- One prompt cannot deliver a finished ten-product integration. External credentials, licence decisions, platform signing and app-store approval remain human steps.
- The product will be honest about which features are fully implemented, experimental, unavailable or awaiting credentials.
- Do not claim signed, notarised or store-approved binaries unless that actually happened.

## Source projects

- Papermark's last upstream push was 2026-08-28; freshness and maintenance status need checking.
- Seven repositories have licence files GitHub cannot classify; their terms are unknown until read.
- Two repositories are AGPL-3.0; reuse terms are unresolved.
