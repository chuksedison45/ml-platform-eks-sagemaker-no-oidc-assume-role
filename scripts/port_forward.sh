\
#!/usr/bin/env bash
set -euo pipefail

echo "Port-forwarding Gateway (platform/gateway) → http://localhost:8080"
kubectl -n platform port-forward svc/gateway 8080:80 >/tmp/gateway_pf.log 2>&1 &
GW_PID=$!

echo "Port-forwarding Dashboard (platform/dashboard) → http://localhost:3000"
kubectl -n platform port-forward svc/dashboard 3000:80 >/tmp/dashboard_pf.log 2>&1 &
UI_PID=$!

echo
echo "PIDs: gateway=$GW_PID, dashboard=$UI_PID"
echo "Press Ctrl+C to stop."

trap 'kill $GW_PID $UI_PID 2>/dev/null || true' EXIT
while true; do sleep 1; done
