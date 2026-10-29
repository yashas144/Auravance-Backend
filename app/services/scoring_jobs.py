"""Queue ingest-time scoring so the API process does not run models on the write path.

When AURAVANCE_REDIS_URL is set, ingest enqueues asset ids and
`python -m app.workers.scoring_worker` scores them. Otherwise scoring stays
inline so pytest and a laptop without Redis still raise alerts.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client = None


def scoring_offloaded() -> bool:
    return bool((settings.redis_url or "").strip())


def _redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    import redis

    _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def reset_scoring_client() -> None:
    global _redis_client
    _redis_client = None


def schedule_ingest_scoring(asset_id: str) -> None:
    if scoring_offloaded():
        try:
            _redis().lpush(settings.scoring_queue, asset_id)
            return
        except Exception as exc:
            logger.warning("Scoring queue unavailable; scoring inline. %s", exc)
    _score_inline(asset_id)


def process_score_job(asset_id: str) -> None:
    _score_inline(asset_id)


def _score_inline(asset_id: str) -> None:
    from app.services.telemetry import telemetry_service

    telemetry_service.score_ingest_alerts(asset_id)
