# Coreway AI Gateway

Gateway de IA para e-commerce. La API corre con FastAPI y usa PostgreSQL y Redis.

## Arranque

Docker Desktop tiene que estar abierto.

```powershell
docker compose up --build
```

Cuando levanta:

- http://localhost:8000/health
- http://localhost:8000/api/v1/info
- http://localhost:8000/docs
