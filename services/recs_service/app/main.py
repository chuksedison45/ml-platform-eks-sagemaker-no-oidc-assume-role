from __future__ import annotations

import time
import json
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from services.common.settings import Settings
from services.common.sagemaker_client import make_sm_runtime, invoke_endpoint_raw


settings = Settings(service_name="recs-service")
app = FastAPI(title=settings.service_name, version=settings.service_version)

_sm = make_sm_runtime(settings.aws_region, settings.sagemaker_timeout_seconds)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name, "version": settings.service_version}


@app.get("/ready")
def ready():
    if not settings.sagemaker_endpoint:
        return JSONResponse(status_code=503, content={"status": "not-ready", "reason": "SAGEMAKER_ENDPOINT not set"})
    return {"status": "ready", "endpoint": settings.sagemaker_endpoint}


@app.post("/predict")
def predict(payload: Dict[str, Any]):
    if not settings.sagemaker_endpoint:
        raise HTTPException(status_code=503, detail="SAGEMAKER_ENDPOINT not set")

    # Factorization Machines supports application/json for inference.
    # Expected format: {"instances":[{"features":[...]}]}
    req: Dict[str, Any]

    if isinstance(payload, dict) and "instances" in payload:
        req = payload
    elif isinstance(payload, dict) and isinstance(payload.get("features"), list):
        req = {"instances": [{"features": payload["features"]}]}
    elif isinstance(payload, dict) and ("userId" in payload and "movieId" in payload):
        # Optional compact one-hot encoding (requires small dims).
        # feature vector = [one-hot user | one-hot item]
        try:
            n_users = int(os.getenv("RECS_NUM_USERS", "0"))
            n_items = int(os.getenv("RECS_NUM_ITEMS", "0"))
            if n_users <= 0 or n_items <= 0:
                raise ValueError("RECS_NUM_USERS/RECS_NUM_ITEMS not set")
            uid = int(payload["userId"])
            mid = int(payload["movieId"])
            if uid < 0 or uid >= n_users or mid < 0 or mid >= n_items:
                raise ValueError("userId/movieId out of configured range")
            vec = [0.0] * (n_users + n_items)
            vec[uid] = 1.0
            vec[n_users + mid] = 1.0
            req = {"instances": [{"features": vec}]}
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Recs expects {'features':[...]} or {'instances':[{'features':[...]}]}. "
                    "To use userId/movieId, set RECS_NUM_USERS and RECS_NUM_ITEMS. "
                    f"({e})"
                ),
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Recs expects {'features':[...]} or {'instances':[{'features':[...]}]} (FM JSON format).",
        )

    try:
        out = invoke_endpoint_raw(
            _sm,
            settings.sagemaker_endpoint,
            json.dumps(req),
            content_type="application/json",
            accept="application/json",
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=504, detail=f"SageMaker invoke failed: {type(e).__name__}: {e}")


