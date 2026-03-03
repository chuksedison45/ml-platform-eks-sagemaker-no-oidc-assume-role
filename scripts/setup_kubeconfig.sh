\
#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:-}"
REGION="${2:-${AWS_REGION:-us-west-2}}"

if [[ -z "$CLUSTER_NAME" ]]; then
  echo "Usage: $0 <cluster-name> [region]"
  exit 1
fi

aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$REGION"
kubectl config current-context
kubectl get nodes
