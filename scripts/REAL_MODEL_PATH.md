# Real Model Path (SageMaker Training → Endpoint)

This folder contains scripts to train and deploy *real* models (not mocks).

Models:
- Fraud: XGBoost (binary classification) trained from IEEE-CIS transaction data
- Recs: Factorization Machines (regression) trained on MovieLens ratings
- Forecast: DeepAR (probabilistic forecasting) trained on Electricity consumption series

These scripts are designed to be **reproducible and demo-friendly**:
- they sample data by default to keep training fast and low-cost
- they write train/val/test artifacts to S3 under `datasets/processed/...`
- they output the endpoint names you should paste into Kubernetes ConfigMaps

Install local deps:
```bash
pip install -r scripts/requirements-train.txt
```

> Note: SageMaker Python SDK 3.x introduces breaking changes. These training scripts use boto3 and only require `sagemaker==2.256.1` for helper utilities (image_uris + RecordIO writer for FM).
