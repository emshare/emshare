"""HttpStatusError.retryable 边界覆盖。"""

import pytest

from em.core.errors import HttpStatusError


@pytest.mark.parametrize(
    "code,expected",
    [
        (500, True),
        (502, True),
        (503, True),
        (599, True),
        (403, True),
        (429, True),
        (400, False),
        (401, False),
        (404, False),
        (418, False),
        (200, False),
        (301, False),
        (302, False),
    ],
)
def test_retryable(code: int, expected: bool) -> None:
    assert HttpStatusError(code).retryable is expected


def test_message_contains_status() -> None:
    e = HttpStatusError(503, "Service Unavailable")
    assert "503" in str(e)
    assert "Service Unavailable" in str(e)
