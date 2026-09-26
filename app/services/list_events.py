from app.infrastructure.events import DescriptionEventLog


class ListDescriptionEvents:
    def __init__(self, store: DescriptionEventLog) -> None:
        self._store = store

    async def execute(self, limit: int) -> list[dict[str, object]]:
        return await self._store.recent(limit)
