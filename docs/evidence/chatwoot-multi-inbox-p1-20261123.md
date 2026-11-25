# CW-048 multi-inbox routing — named evidence (2026-11-23)

| Master ID | Named test | Proved locally |
|---|---|---|
| CW-048 | `test_cw048_multi_inbox_p1.py::test_cw048_inbox_scoped_queues_and_agent_membership` | Two real local inboxes with distinct channel types; two invited support members, each added to one inbox; each agent lists and reads only their own inbox queue; cross-inbox queue and filter requests return 403; owner retains oversight; inbox creation and membership are audited. |

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_cw048_multi_inbox_p1.py -q --disable-warnings
# 1 passed, 1 warning in 1.39s
```

No external mailbox, provider credential or message send is involved. The full
suite result is recorded in `docs/NOVARA_AUTONOMOUS_EXECUTION.md` after this P1
cycle merges.
