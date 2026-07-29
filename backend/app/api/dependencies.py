"""Request-scoped dependencies shared across API routers."""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings

_BEARER_PREFIX = "Bearer "


def require_api_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Gate a route behind the shared-secret bearer token.

    This is the backend's actual access-control layer (see the backend
    scaffold plan's Key Technical Decisions): CORS only governs whether a
    *browser* lets calling JavaScript read a cross-origin response, it does
    nothing to stop a non-browser client from reaching the backend directly.
    Applied to every router except ``/health``, ``/docs``, ``/openapi.json``,
    and ``/redoc``.

    Raises:
        HTTPException: 401 if the ``Authorization`` header is missing,
            malformed, or does not match the configured bearer token.
    """
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_token = authorization.removeprefix(_BEARER_PREFIX)
    expected_token = settings.api_bearer_token.get_secret_value()

    # Constant-time comparison: an ordinary `!=` leaks timing information
    # proportional to the number of matching leading characters.
    if not hmac.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
