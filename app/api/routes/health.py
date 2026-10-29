from fastapi import APIRouter

from app.core.database import storage_dialect
from app.services.scoring_jobs import scoring_offloaded

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "storage": storage_dialect(),
        "scoring": "worker" if scoring_offloaded() else "inline",
    }
