from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from app.errors import AppError

mutation_lock = Lock()


@contextmanager
def exclusive_mutation() -> Iterator[None]:
    if not mutation_lock.acquire(blocking=False):
        raise AppError("operation_in_progress", "Another write is in progress. Try again shortly.", 409)
    try:
        yield
    finally:
        mutation_lock.release()
