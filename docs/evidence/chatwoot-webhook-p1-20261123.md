# CW-108 outbound support webhook — named evidence (2026-11-23)

This is clean-room NOVARA code. The receiver is a real loopback HTTP server; no
mock, fake delivery count or external provider is involved. No secret or token
is printed.

| Master ID | Named test | Proved locally |
|---|---|---|
| CW-108 | `test_cw108_webhook_p1.py::test_cw108_signed_webhook_retries_and_is_allow_listed` | A subscribed local event produces one signed callback after two real HTTP 503 responses; retries are persisted with statuses 503/503/200, one delivery id and one signature; the API exposes the attempt log; non-allow-listed link-local URLs are rejected at configuration time. |

## Commands and results

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_cw108_webhook_p1.py apps/api/tests/test_mautic_marketing_p1.py -q --disable-warnings
# 20 passed, 1 warning in 7.92s
```

The full-suite result is recorded in `docs/NOVARA_AUTONOMOUS_EXECUTION.md` after
the rest of the current P1 cycle merges.

## Security detail

`WebhookCreate.url` now enforces a host allow-list in addition to the existing
HTTP(S)-without-credentials check. Loopback hosts (`127.0.0.1`, `localhost`,
`::1`) remain available for local tests; deployments add real receivers with
`NOVARA_WEBHOOK_ALLOWED_HOSTS` (comma-separated hostnames). This blocks
link-local/metadata endpoints and arbitrary external destinations unless an
operator explicitly permits them. Signing is HMAC-SHA256 over
`delivery_id + "." + raw_body`, reusing the shared deliverer exercised by
PM-117 and MT-050.

## Honest limitations

- The allow-list is hostname-based, not a full SSRF resolver/redirect guard;
  deployments should still restrict egress at the network boundary.
- No external provider, public URL or real customer event is contacted by this
  evidence. Delivery is proved only to the local loopback receiver.
