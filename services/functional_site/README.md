# Functional Site Service - Functional Site Query Microservice

## Port: 18916

## API Endpoints
- `/health` - Health check
- `/api/query/features` - Query functional sites

## Usage Examples

```bash
curl -X POST http://localhost:18916/api/query/features \
  -H "Content-Type: application/json" \
  -d '{"query": "P12345"}'
```
