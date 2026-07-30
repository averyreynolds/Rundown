"""Tests for `app.core.logging` secret redaction.

CLAUDE.md hard rule 3 names logs explicitly as a place API keys must never
appear. These tests assert redaction happens on the fully-formatted log
line -- including text that only exists because it was embedded inside a
caught exception's `str()` -- not just on a literal, intentionally-logged
field value.
"""

import logging
import sys

import pytest

from app.core.logging import SecretRedactingFormatter, configure_logging


def _make_record(msg: str, *, exc_info: object = None) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,  # type: ignore[arg-type]
    )


def test_formatter_redacts_a_known_secret_value_from_the_message() -> None:
    formatter = SecretRedactingFormatter(secrets=["super-secret-value"])
    record = _make_record("API call failed: super-secret-value")

    formatted = formatter.format(record)

    assert "super-secret-value" not in formatted
    assert "***REDACTED***" in formatted


def test_formatter_redacts_a_secret_embedded_in_an_exception_traceback() -> None:
    """A secret that leaks via a stringified exception, not a logged field, is still caught."""
    formatter = SecretRedactingFormatter(secrets=["sk-ant-super-secret"])

    try:
        raise RuntimeError("upstream call failed with key sk-ant-super-secret")
    except RuntimeError:
        record = _make_record("unexpected provider error", exc_info=sys.exc_info())

    formatted = formatter.format(record)

    assert "sk-ant-super-secret" not in formatted
    assert "***REDACTED***" in formatted


def test_formatter_is_unaffected_when_no_secrets_are_present() -> None:
    formatter = SecretRedactingFormatter(secrets=["some-secret"])
    record = _make_record("nothing sensitive here")

    formatted = formatter.format(record)

    assert formatted.endswith("nothing sensitive here")


def test_configure_logging_end_to_end_never_emits_the_raw_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Integration: a logger configured via `configure_logging()` never prints the raw secret."""
    fake_secret = "fake-anthropic-key-abc123"
    configure_logging([fake_secret], log_level="ERROR")
    logger = logging.getLogger("rundown.test.logging")

    try:
        raise RuntimeError(f"provider error, key={fake_secret}")
    except RuntimeError:
        logger.exception("caught a provider error")

    captured = capsys.readouterr()

    assert fake_secret not in captured.err
    assert fake_secret not in captured.out
    assert "***REDACTED***" in captured.err
