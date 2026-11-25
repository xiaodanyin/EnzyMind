# Functional Site Query Service

## Port: 18916

## API endpoints
- `/health` - Health check
- `/api/query/features` - Retrieve annotated functional sites

## Examples

```bash
curl -X POST http://localhost:18916/api/query/features \
  -H "Content-Type: application/json" \
  -d '{"query": "P12345"}'
```
