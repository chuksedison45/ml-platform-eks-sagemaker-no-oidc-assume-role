\
#!/usr/bin/env python3
"""
Create simple **mock** SageMaker endpoints for Fraud/Recs/Forecast so the platform works end-to-end.

Why mock?
- You can demo multi-endpoint routing + health + failure handling without training full models.
- Replace these later with real training pipelines.

This script:
1) Builds a tiny inference script per endpoint (fraud/recs/forecast)
2) Packages it as a SageMaker SKLearn model artifact
3) Creates SageMaker Models + EndpointConfigs + Endpoints

Requirements:
  pip install sagemaker boto3

Usage:
  python3 scripts/create_mock_sagemaker_endpoints.py \
    --region us-west-2 \
    --prefix internal-ml-platform \
    --role-arn arn:aws:iam::<acct>:role/<SageMakerExecutionRole> \
    --instance-type ml.m5.large
"""
from __future__ import annotations

import argparse
import json
import os
import tarfile
import tempfile
from pathlib import Path
from typing import Dict

import boto3
import sagemaker
from sagemaker.image_uris import retrieve
from sagemaker.sklearn.model import SKLearnModel


FRAUD_CODE = r