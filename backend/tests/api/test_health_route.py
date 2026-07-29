"""Integration tests for `/health`, the bearer-token access-control gate, and CORS.

U1 ships no real feature router yet (those arrive in U4-U8), so the
bearer-token scenarios attach one throwaway protected route to the real
`app` object using the exact same `require_api_token` dependency every
future router will be protected by -- this proves the access-control
mechanism itself, not a reimplementation of it.
"""

from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.api.dependencies import require_api_token
from app.main import app

_TEST_PROTECTED_PATH = "/__test/protected"


def _ensure_dummy_protected_route_registered() -> None:
    if any(getattr(route, "path", None) == _TEST_PROTECTED_PATH for route in app.routes):
        return

    dummy_router = APIRouter()

    @dummy_router.get(_TEST_PROTECTED_PATH)
    async def _protected_ping() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(dummy_router, dependencies=[Depends(require_api_token)])


_ensure_dummy_protected_route_registered()

client = TestClient(app)


def test_health_returns_200_ok_without_a_bearer_token() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_response_shape_is_a_simple_status_payload() -> None:
    response = client.get("/health")

    body = response.json()
    assert isinstance(body, dict)
    assert "status" in body


def test_protected_route_without_authorization_header_returns_401() -> None:
    response = client.get(_TEST_PROTECTED_PATH)

    assert response.status_code == 401


def test_protected_route_with_malformed_authorization_header_returns_401() -> None:
    response = client.get(_TEST_PROTECTED_PATH, headers={"Authorization": "not-a-bearer-token"})

    assert response.status_code == 401


def test_protected_route_with_wrong_bearer_token_returns_401() -> None:
    response = client.get(_TEST_PROTECTED_PATH, headers={"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401


def test_protected_route_with_correct_bearer_token_returns_200(
    auth_headers: dict[str, str],
) -> None:
    response = client.get(_TEST_PROTECTED_PATH, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs_and_openapi_are_reachable_without_a_bearer_token() -> None:
    docs_response = client.get("/docs")
    openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200


def test_cors_preflight_from_configured_frontend_origin_succeeds() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_from_an_unconfigured_origin_is_rejected() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
