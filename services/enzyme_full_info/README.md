# Enzyme Full Info Service - Complete Enzyme Information Microservice

## Port: 18915

## API Endpoints
- `/health` - Health check
- `/api/query/enzyme-full-info` - Query complete enzyme information

## Installation & Running

```bash
cd enzyme_full_info
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Usage Example

```bash
curl -X POST http://localhost:18915/api/query/enzyme-full-info \
  -H "Content-Type: application/json" \
  -d '{"uniprot_id": "P12345"}'
```

## Tests

```bash
pytest tests/ -v
```
