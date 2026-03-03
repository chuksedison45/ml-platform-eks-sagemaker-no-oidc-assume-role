\
#!/usr/bin/env python3
"""
Train & deploy a **Factorization Machines** recommendation model on MovieLens ratings using
SageMaker built-in FM algorithm, using **boto3** (SDK-agnostic for training/deploy).

Key constraint: FM training supports only `recordIO-protobuf` format. (AWS docs)
We use `sagemaker.amazon.common.write_spmatrix_to_sparse_tensor` to write RecordIO.

Tested with: sagemaker==2.256.1 (latest v2 before SDK v3).

Inputs:
- MovieLens ratings.csv in S3 (columns: userId, movieId, rating)

Outputs:
- Endpoint name
"""
from __future__ import annotations

import argparse
import os
import tempfile
import uuid
from typing import Tuple

import boto3
import numpy as np
import pandas as pd
from scipy import sparse


def get_image_uri(region: str) -> str:
    try:
        from sagemaker import image_uris
        return image_uris.retrieve(framework="factorization-machines", region=region, version="1")
    except Exception:
        raise RuntimeError(
            "Could not resolve FM image URI. Install SageMaker SDK v2 helper:\n"
            "  pip install 'sagemaker==2.256.1'\n"
        )


def write_recordio(path: str, X: sparse.csr_matrix, y: np.ndarray) -> None:
    try:
        from sagemaker.amazon.common import write_spmatrix_to_sparse_tensor
    except Exception as e:
        raise RuntimeError(
            "RecordIO writer not available. Install SageMaker SDK v2:\n"
            "  pip install 'sagemaker==2.256.1'\n"
            "and SciPy:\n"
            "  pip install scipy\n"
        ) from e
    write_spmatrix_to_sparse_tensor(path, X, y)


def load_csv_s3(s3_uri: str, s3_client) -> pd.DataFrame:
    assert s3_uri.startswith("s3://")
    bucket, key = s3_uri[5:].split("/", 1)
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(obj["Body"])


def build_sparse(df: pd.DataFrame, max_rows: int, seed: int) -> Tuple[sparse.csr_matrix, np.ndarray]:
    df = df[["userId", "movieId", "rating"]].copy()
    if max_rows and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=seed)

    user_ids = df["userId"].astype(int).unique()
    item_ids = df["movieId"].astype(int).unique()
    u_map = {u: i for i, u in enumerate(user_ids)}
    i_map = {m: i for i, m in enumerate(item_ids)}

    n = len(df)
    n_users = len(user_ids)
    dim = n_users + len(item_ids)

    rows = np.arange(n)
    cols_user = df["userId"].map(u_map).to_numpy()
    cols_item = df["movieId"].map(i_map).to_numpy() + n_users
    data = np.ones(n, dtype=np.float32)

    X_user = sparse.csr_matrix((data, (rows, cols_user)), shape=(n, dim))
    X_item = sparse.csr_matrix((data, (rows, cols_item)), shape=(n, dim))
    X = X_user + X_item
    y = df["rating"].astype(np.float32).to_numpy()
    return X, y


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
    ap.add_argument("--prefix", default="datasets/processed/recs")
    ap.add_argument("--ratings-s3", required=True)
    ap.add_argument("--max-rows", type=int, default=200000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train-instance-type", default="ml.m5.xlarge")
    ap.add_argument("--endpoint-instance-type", default="ml.m5.large")
    ap.add_argument("--endpoint-name", default="recs-fm-endpoint")
    args = ap.parse_args()

    boto_sess = boto3.session.Session(region_name=args.region)
    s3 = boto_sess.client("s3")
    sm = boto_sess.client("sagemaker")

    df = load_csv_s3(args.ratings_s3, s3)
    X, y = build_sparse(df, args.max_rows, args.seed)

    n = X.shape[0]
    idx = np.arange(n)
    np.random.seed(args.seed)
    np.random.shuffle(idx)
    split = int(0.8 * n)
    tr, va = idx[:split], idx[split:]

    X_tr, y_tr = X[tr], y[tr]
    X_va, y_va = X[va], y[va]

    with tempfile.TemporaryDirectory() as td:
        train_rec = os.path.join(td, "train.rec")
        val_rec = os.path.join(td, "validation.rec")
        write_recordio(train_rec, X_tr, y_tr)
        write_recordio(val_rec, X_va, y_va)

        s3_train = s3_upload_file(train_rec, args.artifact_bucket, f"{args.prefix}/train/train.rec", s3)
        s3_val = s3_upload_file(val_rec, args.artifact_bucket, f"{args.prefix}/validation/validation.rec", s3)

    image_uri = get_image_uri(args.region)
    job_name = f"recs-fm-{uuid.uuid4().hex[:8]}"
    output_path = f"s3://{args.artifact_bucket}/{args.prefix}/output"

    sm.create_training_job(
        TrainingJobName=job_name,
        AlgorithmSpecification={"TrainingImage": image_uri, "TrainingInputMode": "File"},
        RoleArn=args.role_arn,
        InputDataConfig=[
            {"ChannelName": "train", "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": s3_train, "S3DataDistributionType": "FullyReplicated"}}, "ContentType": "application/x-recordio-protobuf"},
            {"ChannelName": "validation", "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": s3_val, "S3DataDistributionType": "FullyReplicated"}}, "ContentType": "application/x-recordio-protobuf"},
        ],
        OutputDataConfig={"S3OutputPath": output_path},
        ResourceConfig={"InstanceType": args.train_instance_type, "InstanceCount": 1, "VolumeSizeInGB": 30},
        StoppingCondition={"MaxRuntimeInSeconds": 3600},
        HyperParameters={
            "feature_dim": str(X.shape[1]),
            "predictor_type": "regressor",
            "mini_batch_size": "1000",
            "num_factors": "64",
            "epochs": "10",
            "clip_gradient": "5.0",
            "learning_rate": "0.05",
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
