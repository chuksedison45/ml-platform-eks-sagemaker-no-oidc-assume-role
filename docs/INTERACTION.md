# Interaction Guide (UI + API)

## Gateway API (single entry point)
Base URL:
- If using port-forward: `http://localhost:8080`
- If using LoadBalancer: `http://<gateway-lb-dns>`

Endpoints:
- `GET /health` → gateway health
- `GET /status` → returns per-team health summaries
- `POST /predict/fraud` → forwards to fraud service → SageMaker endpoint
- `POST /predict/recs` → forwards to recs service → SageMaker endpoint
- `POST /predict/forecast` → forwards to forecast service → SageMaker endpoint

Example cURL (port-forward):
```bash
curl -s http://localhost:8080/status | jq

curl -s -X POST http://localhost:8080/predict/fraud \
  -H 'Content-Type: application/json' \
  -d '{"TransactionID": 1, "example": 1}' | jq

curl -s -X POST http://localhost:8080/predict/recs \
  -H 'Content-Type: application/json' \
  -d '{"userId": 42, "k": 5}' | jq

curl -s -X POST http://localhost:8080/predict/forecast \
  -H 'Content-Type: application/json' \
  -d '{"start":"2011-01-01","horizon":24,"base":100}' | jq
```

## Team services (direct)
Each team service supports:
- `GET /health`
- `GET /ready` (returns 503 if endpoint not configured)
- `POST /predict`

You can access them from within the cluster DNS or by port-forwarding:
```bash
kubectl -n fraud port-forward svc/fraud 8081:80
curl -s http://localhost:8081/ready
```

## Ops Dashboard
Base URL:
- If using port-forward: `http://localhost:3000`
- If using LoadBalancer: `http://<dashboard-lb-dns>`

Features:
- **Live polling** every 5 seconds (calls `GET /status` on Gateway)
- Health table showing ownership, service version, status
- **Test request interface** to send payloads through the gateway
