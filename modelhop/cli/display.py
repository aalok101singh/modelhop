import os
import re
import shutil
import sys
from typing import Dict

from rich._emoji_codes import EMOJI as _EMOJI_CODES
from rich.console import Console

TIER_COLORS: Dict[str, str] = {"free": "green", "mid": "yellow", "premium": "red"}
TIER_EMOJI: Dict[str, str] = {"free": ":free:", "mid": ":warning:", "premium": ":crown:"}
TIER_LABEL_EMOJI: Dict[str, str] = {"free": "FREE", "mid": "MID", "premium": "PREMIUM"}

#: Maximum render width for CLI output. Terminals re-wrap already-printed
#: lines when the window is resized, which breaks box-drawing frames; capping
#: the width keeps frames intact across resizes (widening never disturbs
#: output, and only shrinking below the render width can). Narrower terminals
#: still get output fitted to their actual width. Override with MODELHOP_WIDTH.
DEFAULT_CONSOLE_WIDTH = 100


def console_width() -> int:
    """Effective render width: detected terminal width capped at 100."""
    override = os.environ.get("MODELHOP_WIDTH", "").strip()
    if override:
        try:
            if int(override) > 0:
                return int(override)
        except ValueError:
            pass
    try:
        detected = shutil.get_terminal_size().columns
    except OSError:
        detected = 80
    return max(20, min(detected or 80, DEFAULT_CONSOLE_WIDTH))


#: Matches only real rich shortcodes (`:frog:`), so stripping can never
#: corrupt lookalikes such as times (`12:30:45`) or URLs.
_EMOJI_STRIP_RE = re.compile(
    ":(" + "|".join(sorted((re.escape(k) for k in _EMOJI_CODES), key=len, reverse=True)) + "):"
)


def is_plain_output() -> bool:
    """True when output is piped/redirected (or plain mode is forced).

    Respects the NO_COLOR convention and MODELHOP_PLAIN=1. Plain mode keeps
    redirected output ASCII-safe in any shell/code page.
    """
    if os.environ.get("NO_COLOR") is not None:
        return True
    if os.environ.get("MODELHOP_PLAIN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    try:
        stream = sys.stdout
        return not (stream is not None and stream.isatty())
    except Exception:
        return True


def _build_ascii_table() -> dict:
    """Map box-drawing / block / braille chars to ASCII.

    Only decoration ranges are mapped (U+2500-U+259F boxes+blocks,
    U+2800-U+28FF braille spinners). User data (accents, dashes, CJK,
    emoji that survive stripping) passes through untouched as UTF-8.
    Our own chrome strings are kept ASCII-safe at the source instead.
    """
    table: dict = {}
    horizontals = set("─━┄┅┈┉╌╍═╸╺╼╾")
    verticals = set("│┃┆┇┊┋╎╏║╵╷╿")
    for code in range(0x2500, 0x2580):
        ch = chr(code)
        table[code] = "-" if ch in horizontals else ("|" if ch in verticals else "+")
    for code in range(0x2580, 0x25A0):
        table[code] = "#"
    for code in range(0x2800, 0x2900):
        table[code] = "*"
    return table


_BOX_TO_ASCII = _build_ascii_table()


class _AsciiSafeWriter:
    """Text-stream proxy transliterating decoration chars to ASCII.

    Resolves the wrapped stream lazily so module-level consoles keep
    following sys.stdout when runners (CliRunner/pytest) swap it.
    """

    def __init__(self, get_stream):
        self._get_stream = get_stream

    def write(self, text):
        return self._get_stream().write(text.translate(_BOX_TO_ASCII))

    def writelines(self, lines):
        return self._get_stream().writelines(line.translate(_BOX_TO_ASCII) for line in lines)

    def __getattr__(self, name):
        return getattr(self._get_stream(), name)


class PlainConsole(Console):
    """Console for piped output: no ANSI, ASCII frames, emoji codes stripped."""

    def __init__(self, *args, **kwargs):
        stream = kwargs.get("file", None)
        if stream is None:
            kwargs["file"] = _AsciiSafeWriter(lambda: sys.stdout)
        else:
            kwargs["file"] = _AsciiSafeWriter(lambda: stream)
        super().__init__(*args, **kwargs)

    def render_str(self, text, *args, **kwargs):
        if kwargs.get("markup", None) is not False:
            text = _EMOJI_STRIP_RE.sub("", text)
        kwargs["emoji"] = False
        kwargs["highlight"] = False
        return super().render_str(text, *args, **kwargs)

    def render(self, renderable, options=None):
        # Panel/Table titles, subtitles, captions and column headers are
        # converted via Text.from_markup internally, bypassing render_str,
        # so their shortcodes are sanitized here before delegating.
        # (Our call sites build these fresh on every print, so in-place
        # edits are safe; stripping is idempotent.)
        from rich.panel import Panel
        from rich.table import Table

        if isinstance(renderable, Panel):
            renderable.title = self._strip_chrome(renderable.title)
            renderable.subtitle = self._strip_chrome(renderable.subtitle)
        elif isinstance(renderable, Table):
            renderable.title = self._strip_chrome(renderable.title)
            renderable.caption = self._strip_chrome(renderable.caption)
            for column in renderable.columns:
                column.header = self._strip_chrome(column.header)
                column.footer = self._strip_chrome(column.footer)
        return super().render(renderable, options)

    @staticmethod
    def _strip_chrome(value):
        return _EMOJI_STRIP_RE.sub("", value) if isinstance(value, str) else value


def get_console(force_terminal: bool = False) -> Console:
    """Shared factory: every CLI surface renders at the same capped width."""
    width = console_width()
    if is_plain_output():
        # Piped/redirected: force_terminal must not leak ANSI into files or
        # pipes, and bytes must stay ASCII-safe in any shell code page.
        return PlainConsole(width=width)
    return Console(width=width, force_terminal=force_terminal)


def tier_color(tier_value: str) -> str:
    return TIER_COLORS.get(tier_value, "white")


def tier_emoji(tier_value: str) -> str:
    return TIER_EMOJI.get(tier_value, "")


def tier_label(tier_value: str) -> str:
    return TIER_LABEL_EMOJI.get(tier_value, tier_value.upper())
