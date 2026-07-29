"""Application logging setup with secret redaction.

CLAUDE.md hard rule 3 names logs explicitly as a place API keys must never
appear. This module redacts by *value*, not just by field name: a
stringified exception raised by a provider SDK or httpx could embed a raw
API key or ``Authorization`` header even when nothing intentionally logged
the settings object itself. Redaction is applied to the fully-formatted log
line -- message, interpolated args, and exception traceback alike -- so it
catches a leaked secret regardless of where in the record it surfaces.
"""

import logging
from collections.abc import Sequence
from typing import Literal

_REDACTED_PLACEHOLDER = "***REDACTED***"


class SecretRedactingFormatter(logging.Formatter):
    """Formatter that scrubs known secret literals from the final log line."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        validate: bool = True,
        *,
        secrets: Sequence[str] = (),
    ) -> None:
        super().__init__(fmt, datefmt, style, validate)
        # Longest-first so a secret that happens to be a substring of
        # another configured secret is never left partially redacted.
        self._secrets: list[str] = sorted({s for s in secrets if s}, key=len, reverse=True)

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for secret in self._secrets:
            formatted = formatted.replace(secret, _REDACTED_PLACEHOLDER)
        return formatted


def configure_logging(secrets: Sequence[str], *, log_level: str = "INFO") -> None:
    """Configure the root logger with secret redaction.

    Call once at application startup (``app/main.py``), after ``Settings()``
    has been constructed, passing every literal secret value the process
    holds (``settings.secret_values()``) so they're scrubbed from every log
    line regardless of which logger or module emits it.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Replace any existing handlers so repeated calls (e.g. the app factory
    # running more than once within a test session) don't stack duplicate
    # handlers and double-emit every line.
    for existing_handler in list(root_logger.handlers):
        root_logger.removeHandler(existing_handler)

    handler = logging.StreamHandler()
    handler.setFormatter(
        SecretRedactingFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            secrets=secrets,
        )
    )
    root_logger.addHandler(handler)
