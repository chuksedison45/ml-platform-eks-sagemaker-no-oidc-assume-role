#!/usr/bin/env bash
set -euo pipefail

# Prefer POD_* vars (matches GitHub Secrets naming), fallback to AWS_* for convenience
AWS_ACCESS_KEY_ID="${POD_AWS_ACCESS_KEY_ID:-${AWS_ACCESS_KEY_ID:-}}"
AWS_SECRET_ACCESS_KEY="${POD_AWS_SECRET_ACCESS_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"
AWS_SESSION_TOKEN="${POD_AWS_SESSION_TOKEN:-${AWS_SESSION_TOKEN:-}}"

if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" ]]; then
  echo "Set POD_AWS_ACCESS_KEY_ID/POD_AWS_SECRET_ACCESS_KEY (or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)."
  exit 1
fi

for ns in fraud recs forecast; do
  echo "Applying Secret aws-credentials in namespace: $ns"
  kubectl -n "$ns" create secret generic aws-credentials     --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"     --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"     --from-literal=AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN"     --dry-run=client -o yaml | kubectl apply -f -
done
