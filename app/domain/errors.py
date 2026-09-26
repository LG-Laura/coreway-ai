class AIUnavailable(Exception):
    """El proveedor no puede completar el pedido ahora.

    La levanta el adaptador resiliente, no el caso de uso. El router
    la traduce a HTTP 503.
    """

    def __init__(self, detail: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds
