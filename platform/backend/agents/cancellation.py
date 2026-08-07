from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

CancellationCheck = Callable[[], bool]

_current_cancellation_check: ContextVar[CancellationCheck | None] = ContextVar(
    "dap_current_cancellation_check",
    default=None,
)


class CooperativeCancellationRequested(RuntimeError):
    """Raised when a bounded runtime observes a cooperative cancel request."""

    def __init__(self, boundary: str) -> None:
        self.boundary = boundary
        super().__init__(
            f"Cooperative cancellation requested at boundary: {boundary}."
        )


def raise_if_cancellation_requested(
    cancellation_check: CancellationCheck | None,
    *,
    boundary: str,
) -> None:
    if cancellation_check is not None and cancellation_check():
        raise CooperativeCancellationRequested(boundary)


def raise_if_current_cancellation_requested(*, boundary: str) -> None:
    raise_if_cancellation_requested(
        _current_cancellation_check.get(),
        boundary=boundary,
    )


@contextmanager
def cancellation_scope(
    cancellation_check: CancellationCheck | None,
) -> Iterator[None]:
    token: Token[CancellationCheck | None] = _current_cancellation_check.set(
        cancellation_check
    )
    try:
        yield
    finally:
        _current_cancellation_check.reset(token)
