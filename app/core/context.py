from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
simulate_provider_failure: ContextVar[bool] = ContextVar("simulate_provider_failure", default=False)
