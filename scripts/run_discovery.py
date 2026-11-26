"""
Run one discovery cycle from the command line (same as "Run Discovery Now" on the Dashboard).

    python scripts/run_discovery.py [--no-evaluate] [--prepare]

* Never deletes anything: new jobs are added, duplicates skipped, taken-down listings marked expired.
* Makes a backup first (storage/backups), so you can always go back.
* Respects Emergency Stop: refuses to run while automation is halted.
* By default it only finds and evaluates jobs. --prepare also drafts applications for eligible
  jobs above your match threshold; drafts still wait for your approval, nothing is sent.
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.db import AsyncSessionLocal, init_db  # noqa: E402
from backend.maintenance import backup  # noqa: E402
from backend.services.discovery_service import DiscoveryService  # noqa: E402
from backend.services.halt import AutomationHaltedError  # noqa: E402


async def main(evaluate: bool, prepare: bool) -> int:
    await init_db()
    m = backup.create("before-discovery")
    print(f"Backup saved: {m['name']}")
    try:
        async with AsyncSessionLocal() as db:
            r = await DiscoveryService.run_discovery(db, auto_evaluate=evaluate,
                                                     auto_prepare_applications=prepare, trigger="manual")
    except AutomationHaltedError as e:
        print(f"Not run: {e}")
        return 3
    print(f"Fetched {r.total_discovered}, new {r.new_saved}, duplicates {r.duplicates_skipped}, "
          f"expired {r.expired_marked}, eligible {r.eligible_count}, prepared {r.prepared_count}")
    for s in r.source_results:
        status = (f"skipped: {s.skipped_reason}" if s.skipped_reason else "ok") if s.ok else f"FAILED: {s.error}"
        print(f"  {s.source_name:<28} fetched {s.fetched:>4}  {status}")
    return 1 if r.source_results and all(not s.ok for s in r.source_results) else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--no-evaluate", action="store_true", help="only fetch and store jobs")
    p.add_argument("--prepare", action="store_true", help="also prepare drafts (they still need your approval)")
    a = p.parse_args()
    sys.exit(asyncio.run(main(not a.no_evaluate, a.prepare)))
