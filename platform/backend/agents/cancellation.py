from collections.abc import Callable

CancellationCheck = Callable[[], bool]


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
