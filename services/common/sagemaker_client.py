\
import json
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config


def make_sm_runtime(region: str, timeout_seconds: int):
    cfg = Config(read_timeout=timeout_seconds, connect_timeout=timeout_seconds, retries={"max_attempts": 2})
    return boto3.client("sagemaker-runtime", region_name=region, config=cfg)


def invoke_endpoint(sm_runtime, endpoint_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = sm_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Accept="application/json",
        Body=json.dumps(payload).encode("utf-8"),
    )
    body = resp["Body"].read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}
