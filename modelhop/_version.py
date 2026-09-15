from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

_FALLBACK = "0.0.0"


def get_version() -> str:
    try:
        return _pkg_version("modelhop")
    except PackageNotFoundError:
        return _FALLBACK
