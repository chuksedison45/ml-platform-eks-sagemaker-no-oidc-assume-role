from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from services.common.settings import Settings
from services.common.sagemaker_client import make_sm_runtime, invoke_endpoint


settings = Settings(service_name="fraud-service")
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

    try:
        out = invoke_endpoint(_sm, settings.sagemaker_endpoint, payload)
        return out
    except Exception as e:
        # Failure path demo: propagate a clean error
        raise HTTPException(status_code=504, detail=f"SageMaker invoke failed: {type(e).__name__}: {e}")
