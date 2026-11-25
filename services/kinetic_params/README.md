# Reported Kinetic Parameters Service

## Port: 18917

## API endpoints
- `/health` - Health check
- `/api/query/kinetics` - Retrieve reported kinetic parameters

## Examples

```bash
curl -X POST http://localhost:18917/api/query/kinetics \
  -H "Content-Type: application/json" \
  -d '{"query": "P12345"}'
```
