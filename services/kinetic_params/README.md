# Kinetic Params Service - Kinetic Parameters Query Microservice

## Port: 18917

## API Endpoints
- `/health` - Health check
- `/api/query/kinetics` - Query kinetic parameters

## Usage Examples

```bash
curl -X POST http://localhost:18917/api/query/kinetics \
  -H "Content-Type: application/json" \
  -d '{"query": "P12345"}'
```
