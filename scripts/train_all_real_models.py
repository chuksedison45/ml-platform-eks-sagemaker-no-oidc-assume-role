\
#!/usr/bin/env python3
"""
One-command orchestrator to train and deploy all 3 real endpoints.

It assumes you've already uploaded/extracted datasets into S3 with:
  scripts/upload_datasets_to_s3.py --extract

You must provide:
- SageMaker execution role ARN
- Dataset bucket
- Region
- S3 URIs to:
  - IEEE train_transaction.csv
  - MovieLens ratings.csv
  - Electricity LD2011_2014.txt

Outputs:
- fraud endpoint name
- recs endpoint name
- forecast endpoint name

Then paste endpoint names into:
- k8s/base/fraud/configmap.yaml
- k8s/base/recs/configmap.yaml
- k8s/base/forecast/configmap.yaml
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def run(cmd):
    print("\n>>>", " ".join(cmd))
    subprocess.check_call(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--role-arn", required=True)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--ieee-train-s3", required=True)
    ap.add_argument("--movielens-ratings-s3", required=True)
    ap.add_argument("--electricity-ld-s3", required=True)

    ap.add_argument("--fraud-endpoint", default="fraud-xgb-endpoint")
    ap.add_argument("--recs-endpoint", default="recs-fm-endpoint")
    ap.add_argument("--forecast-endpoint", default="forecast-deepar-endpoint")
    args = ap.parse_args()

    run([sys.executable, "scripts/train_fraud_xgboost.py",
         "--region", args.region, "--role-arn", args.role_arn,
         "--artifact-bucket", args.bucket, "--train-s3", args.ieee_train_s3,
         "--endpoint-name", args.fraud_endpoint])

    run([sys.executable, "scripts/train_recs_factorization_machines.py",
         "--region", args.region, "--role-arn", args.role_arn,
         "--artifact-bucket", args.bucket, "--ratings-s3", args.movielens_ratings_s3,
         "--endpoint-name", args.recs_endpoint])

    run([sys.executable, "scripts/train_forecast_deepar.py",
         "--region", args.region, "--role-arn", args.role_arn,
         "--artifact-bucket", args.bucket, "--electricity-s3", args.electricity_ld_s3,
         "--endpoint-name", args.forecast_endpoint])

    print("\nDone. Update Kubernetes ConfigMaps with the three endpoint names.")


if __name__ == "__main__":
    main()
