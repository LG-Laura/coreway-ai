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

## Prueba de carga

En otra terminal, con la API ya corriendo:

```powershell
pip install -r scripts/requirements.txt
python scripts/load_test.py
```

Hace tres pasadas contra http://localhost:8000: latencia, cuota (10 por minuto por cliente) y circuit breaker. La última deja el proveedor en pausa unos 15 segundos.
