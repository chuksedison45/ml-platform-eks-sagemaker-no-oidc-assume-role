from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from services.common.settings import Settings
from services.common.sagemaker_client import make_sm_runtime, invoke_endpoint_raw


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

    # Built-in XGBoost expects CSV (or LibSVM) for inference. We accept:
    #   {"csv": "0.1,1.2,3.4"}  OR  {"features": [0.1, 1.2, 3.4]}
    csv_str: Optional[str] = None
    if isinstance(payload, dict):
        if isinstance(payload.get("csv"), str):
            csv_str = payload["csv"]
        elif isinstance(payload.get("features"), list):
            try:
                csv_str = ",".join(str(float(x)) for x in payload["features"])
            except Exception:
                csv_str = None

    if not csv_str:
        raise HTTPException(
            status_code=400,
            detail="Fraud expects {'features':[...]} or {'csv':'0.1,2.3,...'}",
        )

    try:
        out = invoke_endpoint_raw(
            _sm,
            settings.sagemaker_endpoint,
            csv_str,
            content_type="text/csv",
            accept="text/csv",
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=504, detail=f"SageMaker invoke failed: {type(e).__name__}: {e}")


