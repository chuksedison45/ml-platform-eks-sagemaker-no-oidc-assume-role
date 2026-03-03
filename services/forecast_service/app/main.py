from __future__ import annotations

import time
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from services.common.settings import Settings
from services.common.sagemaker_client import make_sm_runtime, invoke_endpoint_raw


settings = Settings(service_name="forecast-service")
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

    # DeepAR expects JSON request with "instances" and optional "configuration".
    req: Dict[str, Any]
    if isinstance(payload, dict) and "instances" in payload:
        req = payload
    elif isinstance(payload, dict) and ("start" in payload and "target" in payload):
        inst = {"start": payload["start"], "target": payload["target"]}
        if "cat" in payload:
            inst["cat"] = payload["cat"]
        if "dynamic_feat" in payload:
            inst["dynamic_feat"] = payload["dynamic_feat"]

        config = payload.get("configuration", {})
        for k in ("num_samples", "output_types", "quantiles"):
            if k in payload and k not in config:
                config[k] = payload[k]
        req = {"instances": [inst]}
        if config:
            req["configuration"] = config
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Forecast expects DeepAR JSON: "
                "{'instances':[{'start':..,'target':[...]}], 'configuration':{...}} "
                "or simplified {'start':..,'target':[...]}."
            ),
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


