"""Ingest scoring worker. Run beside uvicorn when AURAVANCE_REDIS_URL is set.

    python -m app.workers.scoring_worker
"""

from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.core.db import init_db
from app.services.scoring_jobs import process_score_job, scoring_offloaded

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("auravance.scoring_worker")


def main() -> None:
    if not scoring_offloaded():
        raise SystemExit("AURAVANCE_REDIS_URL is not set; ingest already scores inline.")
    init_db()
    import redis

    client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        # Default socket_timeout is 5s, which aborts BRPOP before Redis returns an empty pop.
        socket_timeout=None,
    )
    logger.info("Scoring worker listening on %s", settings.scoring_queue)
    while True:
        try:
            item = client.brpop(settings.scoring_queue, timeout=5)
        except Exception as exc:
            logger.warning("Redis read failed: %s", exc)
            time.sleep(1)
            continue
        if item is None:
            continue
        _queue, asset_id = item
        try:
            process_score_job(asset_id)
        except Exception:
            logger.exception("Scoring failed for %s", asset_id)


if __name__ == "__main__":
    main()
