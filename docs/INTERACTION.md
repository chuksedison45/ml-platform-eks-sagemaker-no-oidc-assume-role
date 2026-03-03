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


## Sample request bodies

### Fraud (XGBoost)
Send either a feature vector or raw CSV string.

```json
{"features": [0, 0, 0, 0, 0]}
```

Or:

```json
{"csv": "0,0,0,0,0"}
```

### Recs (Factorization Machines)
Factorization Machines expects the SageMaker FM JSON format.

```json
{"features": [0, 1, 0, 0, 1]}
```

(We wrap it to: `{"instances":[{"features":[...]}]}`.)

Optional compact one-hot (only if `RECS_NUM_USERS` and `RECS_NUM_ITEMS` are configured):

```json
{"userId": 42, "movieId": 7}
```

### Forecast (DeepAR)
DeepAR expects `instances` with `start` and `target`.

```json
{
  "start": "2011-01-01 00:00:00",
  "target": [100, 101, 102, 103, 104, 105],
  "num_samples": 50,
  "output_types": ["mean", "quantiles"],
  "quantiles": ["0.5", "0.9"]
}
```
