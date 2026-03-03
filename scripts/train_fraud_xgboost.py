\
#!/usr/bin/env python3
"""
Train & deploy a **real** Fraud model using SageMaker built-in XGBoost, using **boto3** (SDK-agnostic).

Why boto3?
- SageMaker Python SDK v3 removed Estimator/Model/Predictor APIs. Using boto3 keeps this script stable.

Input:
- IEEE-CIS Kaggle: train_transaction.csv containing 'isFraud' label.

Pipeline:
1) Download CSV from S3
2) Numeric-only preprocessing (drop object cols, fill NaNs)
3) Sample rows for cost control
4) Write training CSV in SageMaker format: label in first column, no header (per docs)
5) Upload train/validation to S3
6) CreateTrainingJob (XGBoost algorithm image)
7) CreateModel -> CreateEndpointConfig -> CreateEndpoint

Requirements:
- boto3
- pandas/numpy
- sagemaker==2.* only for image_uris helper (optional but recommended)

Docs: SageMaker CSV label must be first column and no header. (See Common Data Formats for Training)
"""
from __future__ import annotations

import argparse
import time
import uuid
from typing import Tuple

import boto3
import numpy as np
import pandas as pd


def get_image_uri(region: str, version: str = "1.7-1") -> str:
    # Try SageMaker helper first
    try:
        from sagemaker import image_uris
        return image_uris.retrieve(framework="xgboost", region=region, version=version)
    except Exception:
        raise RuntimeError(
            "Could not resolve XGBoost image URI. Install SageMaker SDK v2 helper:\n"
            "  pip install 'sagemaker==2.256.1'\n"
            "or provide your own image URI mapping."
        )


def load_csv_s3(s3_uri: str, s3_client) -> pd.DataFrame:
    assert s3_uri.startswith("s3://")
    bucket, key = s3_uri[5:].split("/", 1)
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(obj["Body"])


def preprocess(df: pd.DataFrame, sample: int, seed: int) -> Tuple[pd.DataFrame, pd.Series]:
    if "isFraud" not in df.columns:
        raise ValueError("Expected 'isFraud' column in IEEE train_transaction.csv")
    y = df["isFraud"].astype(int)
    X = df.drop(columns=["isFraud"])
    X = X.select_dtypes(include=[np.number]).copy()
    X = X.fillna(0.0)
    if sample and len(X) > sample:
        X = X.sample(n=sample, random_state=seed)
        y = y.loc[X.index]
    return X, y


def to_sagemaker_csv(X: pd.DataFrame, y: pd.Series, out_path: str) -> None:
    out = pd.concat([y.reset_index(drop=True), X.reset_index(drop=True)], axis=1)
    out.to_csv(out_path, header=False, index=False)


def s3_upload_file(path: str, bucket: str, key: str, s3_client) -> str:
    s3_client.upload_file(path, bucket, key)
    return f"s3://{bucket}/{key}"


def wait_training(sm, job_name: str):
    waiter = sm.get_waiter("training_job_completed_or_stopped")
    waiter.wait(TrainingJobName=job_name)


def wait_endpoint(sm, endpoint_name: str):
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(EndpointName=endpoint_name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--role-arn", required=True, help="SageMaker execution role ARN")
    ap.add_argument("--artifact-bucket", required=True, help="Bucket for processed + model artifacts")
    ap.add_argument("--prefix", default="datasets/processed/fraud")
    ap.add_argument("--train-s3", required=True, help="S3 URI to train_transaction.csv")
    ap.add_argument("--sample", type=int, default=200000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train-instance-type", default="ml.m5.xlarge")
    ap.add_argument("--endpoint-instance-type", default="ml.m5.large")
    ap.add_argument("--endpoint-name", default="fraud-xgb-endpoint")
    args = ap.parse_args()

    boto_sess = boto3.session.Session(region_name=args.region)
    s3 = boto_sess.client("s3")
    sm = boto_sess.client("sagemaker")

    df = load_csv_s3(args.train_s3, s3)
    X, y = preprocess(df, args.sample, args.seed)

    # train/val split
    idx = np.arange(len(X))
    np.random.seed(args.seed)
    np.random.shuffle(idx)
    split = int(0.8 * len(idx))
    tr_idx, va_idx = idx[:split], idx[split:]

    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        train_path = os.path.join(td, "train.csv")
        val_path = os.path.join(td, "validation.csv")
        to_sagemaker_csv(X.iloc[tr_idx], y.iloc[tr_idx], train_path)
        to_sagemaker_csv(X.iloc[va_idx], y.iloc[va_idx], val_path)

        s3_train = s3_upload_file(train_path, args.artifact_bucket, f"{args.prefix}/train/train.csv", s3)
        s3_val = s3_upload_file(val_path, args.artifact_bucket, f"{args.prefix}/validation/validation.csv", s3)

    image_uri = get_image_uri(args.region, version="1.7-1")
    job_name = f"fraud-xgb-{uuid.uuid4().hex[:8]}"
    output_path = f"s3://{args.artifact_bucket}/{args.prefix}/output"

    sm.create_training_job(
        TrainingJobName=job_name,
        AlgorithmSpecification={"TrainingImage": image_uri, "TrainingInputMode": "File"},
        RoleArn=args.role_arn,
        InputDataConfig=[
            {"ChannelName": "train", "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": s3_train, "S3DataDistributionType": "FullyReplicated"}}, "ContentType": "text/csv"},
            {"ChannelName": "validation", "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": s3_val, "S3DataDistributionType": "FullyReplicated"}}, "ContentType": "text/csv"},
        ],
        OutputDataConfig={"S3OutputPath": output_path},
        ResourceConfig={"InstanceType": args.train_instance_type, "InstanceCount": 1, "VolumeSizeInGB": 30},
        StoppingCondition={"MaxRuntimeInSeconds": 3600},
        HyperParameters={
            "objective": "binary:logistic",
            "num_round": "200",
            "max_depth": "6",
            "eta": "0.2",
            "subsample": "0.8",
            "eval_metric": "auc",
        },
    )
    print(f"TrainingJob: {job_name}")
    wait_training(sm, job_name)

    model_data = f"{output_path}/{job_name}/output/model.tar.gz"
    model_name = f"{job_name}-model"
    sm.create_model(
        ModelName=model_name,
        ExecutionRoleArn=args.role_arn,
        PrimaryContainer={"Image": image_uri, "ModelDataUrl": model_data},
    )

    epc_name = f"{job_name}-epc"
    sm.create_endpoint_config(
        EndpointConfigName=epc_name,
        ProductionVariants=[{
            "VariantName": "AllTraffic",
            "ModelName": model_name,
            "InitialInstanceCount": 1,
            "InstanceType": args.endpoint_instance_type,
            "InitialVariantWeight": 1.0,
        }],
    )

    # Create or update endpoint
    try:
        sm.describe_endpoint(EndpointName=args.endpoint_name)
        sm.update_endpoint(EndpointName=args.endpoint_name, EndpointConfigName=epc_name)
        print(f"Updating existing endpoint: {args.endpoint_name}")
    except sm.exceptions.ClientError:
        sm.create_endpoint(EndpointName=args.endpoint_name, EndpointConfigName=epc_name)
        print(f"Creating endpoint: {args.endpoint_name}")

    wait_endpoint(sm, args.endpoint_name)
    print(args.endpoint_name)


if __name__ == "__main__":
    main()
