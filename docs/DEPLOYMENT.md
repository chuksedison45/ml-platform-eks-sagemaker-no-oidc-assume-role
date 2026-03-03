# Deployment Guide (Detailed)

This is the step-by-step approach you can follow for your presentation and reproducibility scoring.

## Phase 1 — Bootstrap remote state (S3 + DynamoDB)
1. Choose a globally-unique bucket name (e.g. `edison-internal-ml-tfstate-123456789012`)
2. Run:
   ```bash
   cd terraform/bootstrap
   terraform init
   terraform apply \
     -var="region=us-west-2" \
     -var="state_bucket_name=<YOUR_BUCKET>" \
     -var="lock_table_name=terraform-locks"
   ```

3. Edit `terraform/platform/backend.tf` and set:
   - `bucket = "<YOUR_BUCKET>"`
   - `dynamodb_table = "terraform-locks"`

## Phase 2 — Provision EKS + ECR + IAM + dataset bucket
1. Run:
   ```bash
   cd terraform/platform
   terraform init
   terraform apply \
     -var="region=us-west-2" \
     -var="project_name=internal-ml-platform" \
     -var="cluster_name=internal-ml-platform" \
     -var="github_repo=<org>/<repo>"
   ```

2. Copy outputs:
   - `datasets_bucket`
   - `ecr_repo_urls`
   - `irsa_role_arns` (fraud/recs/forecast)
   - `github_deploy_role_arn` (for GitHub Actions OIDC)

## Phase 3 — Configure Kubernetes manifests
1. Update **IRSA role ARNs** in:
   - `k8s/overlays/dev/patches/irsa_roles.yaml`

2. Update **SageMaker endpoint names** in:
   - `k8s/base/fraud/configmap.yaml`
   - `k8s/base/recs/configmap.yaml`
   - `k8s/base/forecast/configmap.yaml`

## Phase 4 — Create SageMaker endpoints (mock for demo)
1. Create/identify a SageMaker execution role ARN (has `AmazonSageMakerFullAccess` or minimal model+endpoint perms).
2. Run:
   ```bash
   pip install sagemaker boto3
   python3 scripts/create_mock_sagemaker_endpoints.py \
     --region us-west-2 \
     --prefix internal-ml-platform \
     --role-arn <SAGEMAKER_EXEC_ROLE_ARN>
   ```

3. Paste endpoint names into the ConfigMaps above.

## Phase 5 — Deploy to EKS
1. Configure kubeconfig:
   ```bash
   ./scripts/setup_kubeconfig.sh internal-ml-platform us-west-2
   ```

2. Apply kustomize overlay:
   ```bash
   kubectl apply -k k8s/overlays/dev
   ```

3. Wait/verify:
   ```bash
   kubectl -n platform get pods
   kubectl -n platform get svc gateway dashboard
   ```

## Phase 6 — Verify functionality
Port-forward locally:
```bash
./scripts/port_forward.sh
```
Then:
- `GET http://localhost:8080/status`
- `POST http://localhost:8080/predict/fraud` body `{"TransactionID": 1}`
- `POST http://localhost:8080/predict/recs` body `{"userId": 42, "k": 5}`
- `POST http://localhost:8080/predict/forecast` body `{"start":"2024-01-01","horizon":24,"base":100}`

## CI/CD — GitHub Actions
This repo includes workflows:
- `.github/workflows/deploy.yml` builds/pushes images and deploys to EKS
- `.github/workflows/terraform.yml` applies Terraform (manual)

CI/CD without OIDC:
- Create an **Access Key** for the Terraform-created IAM user `${project}-github-actions`
- Add GitHub Secrets:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `ECR_REGISTRY`
  - `ECR_REPO_FRAUD`, `ECR_REPO_RECS`, `ECR_REPO_FORECAST`, `ECR_REPO_GATEWAY`, `ECR_REPO_DASHBOARD`


## Kubernetes Secrets automation (B2)
In CI/CD the workflow creates `aws-credentials` Secrets in the `fraud`, `recs`, and `forecast` namespaces using GitHub Secrets.
For local deploys:
```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
./scripts/create_k8s_secrets_from_env.sh
```

## CI/CD assume-role (no OIDC)

### 1) Create access keys for the bootstrap user
Terraform creates IAM user: `<project>-github-actions`.
Create an **Access Key** for it in AWS Console and store in GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### 2) Set the deploy role ARN
Terraform output:
- `github_deploy_role_arn`

Store it in GitHub Secrets:
- `AWS_DEPLOY_ROLE_ARN`

GitHub Actions will use the bootstrap user's keys to assume this role at runtime. (Supported by `aws-actions/configure-aws-credentials`.) 

### 3) Create access keys for pods (SageMaker invoke)
Terraform creates IAM user: `<project>-sagemaker-invoke`.
Create access keys and store in GitHub Secrets:
- `POD_AWS_ACCESS_KEY_ID`
- `POD_AWS_SECRET_ACCESS_KEY`

These are used to create the Kubernetes Secret `aws-credentials` in `fraud`, `recs`, `forecast`.
