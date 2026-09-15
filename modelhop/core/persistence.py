import json
import os
import tempfile


def atomic_write_json(path: str, data: dict) -> None:
    """Write JSON atomically: write to a temp file, then os.replace.

    Guarantees readers never observe a partially written / empty file even
    if the process is killed mid-write.
    """
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
