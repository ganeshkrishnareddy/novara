# Integration strategy

Status: scaffold — pending architecture review (T-008).

Principle: prefer modular adapters, public APIs, SDKs and clean-room implementations over copying source. No integration code may be written until `LICENSE_COMPLIANCE.md` is complete.

Foundation implied by the founder vision: one shared customer identity, one permission model, one event contract set and one analytics stream across every module.
