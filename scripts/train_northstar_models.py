"""Train local XGBoost and LSTM artifacts from datasets already in this repo."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def run(script: str) -> None:
    command = [sys.executable, str(BACKEND_DIR / "scripts" / script)]
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.check_call(command, cwd=BACKEND_DIR)


def main() -> None:
    run("train_xgboost_models.py")
    try:
        run("train_sequence_models.py")
    except subprocess.CalledProcessError:
        print(
            "LSTM training skipped or failed. Install the optional extra and retry: pip install -e '.[sequence]'",
            flush=True,
        )
    run("evaluate_detection_delta.py")
    print(json.dumps({"status": "ok", "next": "restart uvicorn, then python scripts/replay_telemetry.py --transport mqtt"}, indent=2))


if __name__ == "__main__":
    main()
