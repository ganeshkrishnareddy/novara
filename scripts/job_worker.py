"""Local durable job worker for NOVARA (PL-071).

Runs the polling ``JobWorker`` against the configured NOVARA database. This
stands in for a Celery worker: no broker or external service is contacted, and
every job transition is persisted in the same database the API writes.

Usage (from the repository root):

    .venv\\Scripts\\python.exe scripts/job_worker.py            # poll forever
    .venv\\Scripts\\python.exe scripts/job_worker.py --once     # one cycle
    .venv\\Scripts\\python.exe scripts/job_worker.py --workspace <id>
    .venv\\Scripts\\python.exe scripts/job_worker.py --types noop,metrics.refresh

Stop with Ctrl+C. A crash is safe: jobs left ``running`` are requeued by the
next worker after ``--recover-after`` seconds.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from novara_core.modules import import_all  # noqa: E402
from novara_core.modules.jobs import JobWorker  # noqa: E402

import_all()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NOVARA durable job worker")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    parser.add_argument("--workspace", help="restrict claims to one workspace id")
    parser.add_argument(
        "--types",
        help="comma-separated job types to claim (default: every registered type)",
    )
    parser.add_argument("--poll", type=float, default=1.0, help="poll interval seconds")
    parser.add_argument("--batch", type=int, default=10, help="jobs per cycle (1-100)")
    parser.add_argument(
        "--recover-after",
        type=int,
        default=300,
        help="requeue jobs left running longer than this many seconds",
    )
    parser.add_argument("--worker-id", help="stable worker identifier")
    args = parser.parse_args(argv)

    job_types = [t.strip() for t in args.types.split(",") if t.strip()] if args.types else None
    worker = JobWorker(
        worker_id=args.worker_id,
        job_types=job_types,
        workspace_id=args.workspace,
        poll_seconds=args.poll,
        batch_limit=args.batch,
        recover_after_seconds=args.recover_after,
    )
    print(f"worker {worker.worker_id} started", flush=True)
    if args.once:
        summary = worker.tick()
        print(
            "cycle finished: claimed={claimed} succeeded={succeeded} "
            "retried={retried} dead_lettered={dead_lettered} recovered={recovered}".format(
                **summary
            ),
            flush=True,
        )
        return 0
    try:
        while True:
            summary = worker.tick()
            if summary["claimed"] or summary["recovered"]:
                print(
                    "cycle: claimed={claimed} succeeded={succeeded} "
                    "retried={retried} dead_lettered={dead_lettered} "
                    "recovered={recovered}".format(**summary),
                    flush=True,
                )
            time.sleep(worker.poll_seconds)
    except KeyboardInterrupt:
        print("worker stopped", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
