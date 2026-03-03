# services/common/sagemaker_client.py
import os
import json
import boto3
from botocore.config import Config

def make_sm_runtime(region: str | None = None):
    region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-west-2"
    # reasonable retry defaults
    cfg = Config(retries={"max_attempts": 3, "mode": "standard"})
    return boto3.client("sagemaker-runtime", region_name=region, config=cfg)

def _read_body(resp) -> str:
    body = resp.get("Body")
    if body is None:
        return ""
    data = body.read()
    if isinstance(data, (bytes, bytearray)):
        return data.decode("utf-8", errors="replace")
    return str(data)

def invoke_endpoint_raw(sm_runtime, endpoint_name: str, body: bytes, content_type: str, accept: str = "application/json"):
    """
    Invoke SageMaker endpoint with explicit content-type/body (for XGBoost CSV, RecordIO, etc.)
    Returns (status_code, response_text, raw_response_dict)
    """
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
    """
    Invoke endpoint sending JSON (for DeepAR, FM JSON endpoints, etc.)
    """
    body = json.dumps(payload).encode("utf-8")
    return invoke_endpoint_raw(sm_runtime, endpoint_name, body, content_type="application/json", accept=accept)
