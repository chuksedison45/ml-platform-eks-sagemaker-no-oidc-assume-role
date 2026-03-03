\
from __future__ import annotations

import os
from typing import Any, Dict

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "gateway"
    service_version: str = "1.0.0"
    # Internal service URLs (Kubernetes DNS)
    fraud_url: str = "http://fraud.fraud.svc.cluster.local"
    recs_url: str = "http://recs.recs.svc.cluster.local"
    forecast_url: str = "http://forecast.forecast.svc.cluster.local"
    http_timeout_seconds: int = 2

    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
app = FastAPI(title=settings.service_name, version=settings.service_version)


async def _get_json(url: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name, "version": settings.service_version}


@app.get("/status")
async def status():
    # Operational surface: health for each team service (+ versions)
    results = {}
    for team, base in {
        "fraud": settings.fraud_url,
        "recs": settings.recs_url,
        "forecast": settings.forecast_url,
    }.items():
        try:
            results[team] = await _get_json(f"{base}/health")
        except Exception as e:
            results[team] = {"status": "down", "error": f"{type(e).__name__}: {e}"}
    return results


@app.post("/predict/{team}")
async def predict(team: str, payload: Dict[str, Any]):
    routes = {
        "fraud": settings.fraud_url,
        "recs": settings.recs_url,
        "forecast": settings.forecast_url,
    }
    if team not in routes:
        raise HTTPException(status_code=404, detail=f"Unknown team: {team}")

    try:
        return await _post_json(f"{routes[team]}/predict", payload)
    except httpx.HTTPStatusError as e:
        # Forward service errors cleanly
        return JSONResponse(status_code=e.response.status_code, content={"error": e.response.text})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {type(e).__name__}: {e}")
