from collections.abc import Iterable


def yota() -> Iterable[int]:
    i = 0
    while True:
        yield i
        i += 1
