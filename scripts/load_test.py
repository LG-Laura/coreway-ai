"""Tres ráfagas contra el gateway local.

La cuota es por cliente. El circuit breaker es del proveedor y lo
comparten todos. Por eso latencia y circuito usan un cliente distinto
en cada pedido: si no, a los 10 pedidos la cuota tapa el resto.

Uso, con la API ya levantada:

    pip install -r scripts/requirements.txt
    python scripts/load_test.py
"""

import argparse
import asyncio
import math
import time
import uuid
from collections import Counter
from dataclasses import dataclass

import httpx

PRODUCT = {
    "name": "Zapatillas Urban",
    "category": "calzado",
    "attributes": ["livianas", "blancas"],
    "tone": "claro",
}


@dataclass(frozen=True)
class Outcome:
    status: int
    latency_ms: float
    server_ms: float | None
    detail: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula tráfico contra el gateway local.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--scenario",
        choices=("all", "latency", "quota", "circuit"),
        default="all",
    )
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=30)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests y --concurrency tienen que ser mayores a 0")
    asyncio.run(run(args.base_url.rstrip("/"), args.scenario, args.requests, args.concurrency))


async def run(base_url: str, scenario: str, requests: int, concurrency: int) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        if not await api_is_up(client):
            print(f"La API no responde en {base_url}. Levantala con: docker compose up --build")
            return
        if scenario in ("all", "latency"):
            await latency_scenario(client, requests, concurrency)
        if scenario in ("all", "quota"):
            await quota_scenario(client, requests, concurrency)
        if scenario in ("all", "circuit"):
            await circuit_scenario(client, requests, concurrency)
            print("El proveedor queda en pausa unos 15 segundos. Después vuelve a aceptar fichas.")


async def api_is_up(client: httpx.AsyncClient) -> bool:
    try:
        response = await client.get("/health")
    except httpx.HTTPError:
        return False
    return response.status_code == 200


async def latency_scenario(client: httpx.AsyncClient, requests: int, concurrency: int) -> None:
    stamp = uuid.uuid4().hex[:8]
    rows = await burst(
        client,
        requests,
        concurrency,
        lambda i: {"X-Client-Id": f"lat-{stamp}-{i}"},
    )
    print(f"\nlatencia  pedidos={requests}  concurrencia={concurrency}  un cliente por pedido")
    report(rows)
    server = [row.server_ms for row in rows if row.server_ms is not None and row.status == 200]
    client_ms = [row.latency_ms for row in rows if row.status == 200]
    if client_ms and server:
        print(
            "  en los 200, el header X-Response-Time-Ms es el tiempo del servidor; "
            "la otra cifra incluye el viaje hasta tu máquina"
        )
        print(f"  servidor ms  {_line(server)}")
        print(f"  cliente ms   {_line(client_ms)}")


async def quota_scenario(client: httpx.AsyncClient, requests: int, concurrency: int) -> None:
    total = max(requests, 11)
    client_id = f"cuota-{uuid.uuid4().hex[:8]}"
    rows = await burst(
        client,
        total,
        min(concurrency, total),
        lambda _: {"X-Client-Id": client_id},
    )
    counts = Counter(row.status for row in rows)
    print(f"\ncuota  cliente={client_id}  pedidos={total}  juntos")
    report(rows)
    print(f"  aceptados={counts[200]}  rechazados={counts[429]}  (el tope configurado es 10 por minuto)")
    _print_server("200", rows, 200)
    _print_server("429", rows, 429)


async def circuit_scenario(client: httpx.AsyncClient, requests: int, concurrency: int) -> None:
    client_id = f"circuito-{uuid.uuid4().hex[:8]}"
    failures = [
        await shoot(client, {"X-Client-Id": client_id, "X-Debug-Provider-Failure": "true"})
        for _ in range(3)
    ]
    probe = await shoot(client, {"X-Client-Id": f"{client_id}-probe"})
    followers = max(min(requests, 15), 5)
    opened = await burst(
        client,
        followers,
        min(concurrency, followers),
        lambda i: {"X-Client-Id": f"{client_id}-{i}"},
    )
    print("\ncircuito  3 fallos seguidos, un pedido normal y después una ráfaga")
    print("  fallos simulados")
    report(failures)
    print("  pedido siguiente, sin simular fallo")
    report([probe])
    print("  ráfaga con el circuito abierto")
    report(opened)
    print("  tiempo del servidor")
    _print_server("fallo con reintento", failures, 503)
    _print_server("circuito abierto", [probe], 503)


async def burst(client, count: int, concurrency: int, headers_for) -> list[Outcome]:
    semaphore = asyncio.Semaphore(concurrency)

    async def one(index: int) -> Outcome:
        async with semaphore:
            return await shoot(client, headers_for(index))

    return list(await asyncio.gather(*(one(index) for index in range(count))))


async def shoot(client: httpx.AsyncClient, headers: dict[str, str]) -> Outcome:
    started = time.perf_counter()
    try:
        response = await client.post("/api/v1/products/descriptions", json=PRODUCT, headers=headers)
    except httpx.HTTPError as exc:
        return Outcome(0, _elapsed(started), None, str(exc))
    server_raw = response.headers.get("X-Response-Time-Ms")
    server_ms = float(server_raw) if server_raw else None
    detail = None
    if response.status_code >= 400:
        try:
            parsed = response.json().get("detail")
        except ValueError:
            parsed = None
        if isinstance(parsed, str):
            detail = parsed
    return Outcome(response.status_code, _elapsed(started), server_ms, detail)


def report(rows: list[Outcome]) -> None:
    counts = Counter(row.status for row in rows)
    pieces = [f"{status}={counts[status]}" for status in sorted(counts)]
    print(f"  estados  {'  '.join(pieces)}")
    details = Counter(row.detail for row in rows if row.detail)
    for detail, amount in details.items():
        print(f"  {amount} x {detail}")


def _print_server(label: str, rows: list[Outcome], status: int) -> None:
    values = [row.server_ms for row in rows if row.status == status and row.server_ms is not None]
    if values:
        print(f"  {label} ms  {_line(values)}")


def _line(values: list[float]) -> str:
    return (
        f"min={_num(min(values))}  p50={_num(_percentile(values, 50))}  "
        f"p95={_num(_percentile(values, 95))}  max={_num(max(values))}"
    )


def _percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    rank = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return ordered[min(rank, len(ordered) - 1)]


def _elapsed(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def _num(value: float) -> str:
    return f"{value:.1f}"


if __name__ == "__main__":
    main()
