\
#!/usr/bin/env python3
"""
Train & deploy a **DeepAR** forecasting model using UCI ElectricityLoadDiagrams20112014, using **boto3**.

Inputs:
- S3 URI to LD2011_2014.txt (after extraction)

DeepAR expects JSON lines:
{"start":"YYYY-MM-DD HH:MM:SS","target":[...]} for each time series.

This script:
- Loads the dataset
- selects first N series columns (default 20)
- trims length for fast demo
- writes train/test JSON lines
- CreateTrainingJob -> CreateModel -> CreateEndpoint

Requirements:
- boto3
- pandas/numpy
- sagemaker==2.* only for image_uris helper (optional but recommended)
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import uuid

import boto3
import numpy as np
import pandas as pd


def get_image_uri(region: str) -> str:
    try:
        from sagemaker import image_uris
        return image_uris.retrieve(framework="forecasting-deepar", region=region, version="1")
    except Exception:
        raise RuntimeError(
            "Could not resolve DeepAR image URI. Install SageMaker SDK v2 helper:\n"
            "  pip install 'sagemaker==2.256.1'\n"
        )


def load_csv_s3(s3_uri: str, s3_client) -> pd.DataFrame:
    assert s3_uri.startswith("s3://")
    bucket, key = s3_uri[5:].split("/", 1)
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(obj["Body"], sep=";", decimal=",")


def make_jsonl(df: pd.DataFrame, start_ts: str, out_path: str, max_series: int, max_len: int):
    time_col = df.columns[0]
    series_cols = df.columns[1:1 + max_series]
    if max_len and len(df) > max_len:
        df = df.iloc[-max_len:].copy()

    with open(out_path, "w", encoding="utf-8") as f:
        for c in series_cols:
            target = df[c].fillna(0.0).astype(float).to_list()
            f.write(json.dumps({"start": start_ts, "target": target}) + "\n")


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
    ap.add_argument("--role-arn", required=True)
    ap.add_argument("--artifact-bucket", required=True)
    ap.add_argument("--prefix", default="datasets/processed/forecast")
    ap.add_argument("--electricity-s3", required=True)
    ap.add_argument("--max-series", type=int, default=20)
    ap.add_argument("--max-len", type=int, default=2000)
    ap.add_argument("--freq", default="H")
    ap.add_argument("--train-instance-type", default="ml.m5.xlarge")
    ap.add_argument("--endpoint-instance-type", default="ml.m5.large")
    ap.add_argument("--endpoint-name", default="forecast-deepar-endpoint")
    args = ap.parse_args()

    boto_sess = boto3.session.Session(region_name=args.region)
    s3 = boto_sess.client("s3")
    sm = boto_sess.client("sagemaker")

    df = load_csv_s3(args.electricity_s3, s3)
    try:
        dt0 = pd.to_datetime(df.iloc[0, 0])
        start_ts = dt0.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        start_ts = "2011-01-01 00:00:00"

    split = int(0.8 * len(df))
    df_tr = df.iloc[:split].copy()
    df_te = df.iloc[split:].copy()

    with tempfile.TemporaryDirectory() as td:
        train_path = os.path.join(td, "train.json")
        test_path = os.path.join(td, "test.json")
        make_jsonl(df_tr, start_ts, train_path, args.max_series, args.max_len)
        make_jsonl(df_te, start_ts, test_path, args.max_series, args.max_len)

        s3_train = s3_upload_file(train_path, args.artifact_bucket, f"{args.prefix}/train/train.json", s3)
        s3_test = s3_upload_file(test_path, args.artifact_bucket, f"{args.prefix}/test/test.json", s3)

    image_uri = get_image_uri(args.region)
    job_name = f"forecast-deepar-{uuid.uuid4().hex[:8]}"
    output_path = f"s3://{args.artifact_bucket}/{args.prefix}/output"

    sm.create_training_job(
        TrainingJobName=job_name,
        AlgorithmSpecification={"TrainingImage": image_uri, "TrainingInputMode": "File"},
        RoleArn=args.role_arn,
        InputDataConfig=[
            {
                "ChannelName": "train",
                "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": s3_train, "S3DataDistributionType": "FullyReplicated"}},
                "ContentType": "json",
            },
            {
                "ChannelName": "test",
                "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": s3_test, "S3DataDistributionType": "FullyReplicated"}},
                "ContentType": "json",
            },
            ],
        OutputDataConfig={"S3OutputPath": output_path},
        ResourceConfig={"InstanceType": args.train_instance_type, "InstanceCount": 1, "VolumeSizeInGB": 30},
        StoppingCondition={"MaxRuntimeInSeconds": 3600},
        HyperParameters={
            "time_freq": args.freq,
            "context_length": "72",
            "prediction_length": "24",
            "epochs": "5",
            "mini_batch_size": "64",
            "learning_rate": "0.001",
            "num_cells": "40",
            "num_layers": "2",
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
