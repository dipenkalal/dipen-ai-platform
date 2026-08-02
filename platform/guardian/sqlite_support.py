from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


@contextmanager
def managed_connection(
    *args: Any,
    **kwargs: Any,
) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(*args, **kwargs)

    try:
        with connection:
            yield connection
    finally:
        connection.close()
