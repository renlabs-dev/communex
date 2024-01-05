import queue
from contextlib import contextmanager
from typing import Any

class CommuneClient:
    max_connections: int
    wait_for_finalization: bool
    _connection_queue: queue.Queue[Any]

    @contextmanager
    def get_conn(self, timeout: float | None = None):
        yield None
