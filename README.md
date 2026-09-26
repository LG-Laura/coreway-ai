# Coreway AI Gateway

API para generar la ficha de un producto de una tienda. Corre con FastAPI, PostgreSQL y Redis, y se levanta entera con Docker.

El texto lo arma un adaptador local: no llama a un modelo de pago. El caso de uso no conoce ese adaptador. Le pide el texto a una interfaz, y al arrancar se elige qué implementación usar. Cambiar de proveedor es cambiar `AI_PROVIDER`, no el endpoint.

Además limita cuántos pedidos acepta cada cliente, corta las llamadas si el proveedor falla seguido, y anota cada ficha generada sin demorar la respuesta.

## Clonar y levantar

Hace falta [Docker Desktop](https://www.docker.com/products/docker-desktop/) abierto y en marcha. Git también.

```powershell
git clone https://github.com/LG-Laura/coreway-ai.git
cd coreway-ai
docker compose up --build
```

La primera vez descarga las imágenes y puede tardar un poco. Cuando los tres servicios están arriba:

- http://localhost:8000/health comprueba la API, Postgres y Redis
- http://localhost:8000/docs muestra los endpoints y deja probarlos desde el navegador
- http://localhost:8000/api/v1/info devuelve el nombre del servicio

Para frenarlo: `Ctrl+C` en esa terminal, o `docker compose down` en otra.

`.env.example` lista las variables. Con `docker compose` no hace falta copiarlo: el compose ya se las pasa al contenedor. La clave `coreway` es solo la de la base local.

## Pedir una ficha

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/products/descriptions `
  -ContentType "application/json" `
  -Headers @{ "X-Client-Id" = "tienda-demo" } `
  -Body '{"name":"Zapatillas Urban","category":"calzado","attributes":["livianas","blancas"],"tone":"claro"}'
```

La respuesta trae la descripción y quién la escribió:

```json
{
  "description": "Zapatillas Urban es un producto de calzado. Se destaca por livianas, blancas. La ficha está escrita en tono claro.",
  "provider": "local",
  "model": "local-catalog-v1"
}
```

`X-Client-Id` identifica al cliente para la cuota. Si no se manda, se usa la IP. Un nombre vacío responde `422` y no llama al adaptador.

Cada ficha que sale bien queda anotada. Las últimas se leen en http://localhost:8000/api/v1/products/events

## Cuota y pausa del proveedor

Cada cliente tiene 10 pedidos por minuto. El que sigue responde `429` con `Cuota excedida para este cliente.` `/health` y `/docs` no consumen esa cuota.

Si el proveedor falla 3 veces seguidas, durante 15 segundos los pedidos nuevos responden `503` y no lo vuelven a llamar. En local se puede forzar el fallo con el header `X-Debug-Provider-Failure: true`.

## Prueba de carga

Con la API ya corriendo, en otra terminal dentro de la carpeta del proyecto:

```powershell
pip install -r scripts/requirements.txt
python scripts/load_test.py
```

Hace tres pasadas:

1. Latencia, con un cliente distinto por pedido.
2. Cuota, muchos pedidos del mismo cliente.
3. Circuito, tres fallos y después una ráfaga.

La última deja el proveedor en pausa unos 15 segundos. Pasado ese tiempo vuelve a aceptar fichas.

## Cómo está organizado

| Carpeta | Qué hay |
|---|---|
| `app/api` | Rutas HTTP. Traducen el JSON y nada más. |
| `app/services` | El caso de uso de la ficha. |
| `app/domain` | El pedido, la interfaz del proveedor y los eventos. |
| `app/adapters` | El adaptador local, los reintentos y el circuit breaker. |
| `app/middleware` | La cuota por cliente y el log JSON con la latencia. |
| `app/infrastructure` | Postgres, Redis y la bitácora de fichas. |
| `scripts` | El simulador de tráfico. |
