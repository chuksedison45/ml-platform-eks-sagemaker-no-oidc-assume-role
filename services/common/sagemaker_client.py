import os
import json
import boto3
from botocore.config import Config


def make_sm_runtime(region: str | None = None):
    region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-west-2"
    return boto3.client(
        "sagemaker-runtime",
        region_name=region,
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )


def _read_body(resp) -> str:
    body = resp.get("Body")
    if body is None:
        return ""
    data = body.read()
    if isinstance(data, (bytes, bytearray)):
        return data.decode("utf-8", errors="replace")
    return str(data)


def invoke_endpoint_raw(sm_runtime, endpoint_name: str, body: bytes, content_type: str, accept: str = "application/json"):
    """Low-level invoke with explicit ContentType (needed for XGBoost CSV, RecordIO, etc.)."""
    resp = sm_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        Body=body,
        ContentType=content_type,
        Accept=accept,
    )
    status = resp.get("ResponseMetadata", {}).get("HTTPStatusCode", 200)
    text = _read_body(resp)
    return status, text, resp


def invoke_endpoint_json(sm_runtime, endpoint_name: str, payload: dict, accept: str = "application/json"):
    """Convenience helper for JSON-based algorithms (DeepAR/FM JSON formats)."""
    body = json.dumps(payload).encode("utf-8")
    return invoke_endpoint_raw(sm_runtime, endpoint_name, body, content_type="application/json", accept=accept)
