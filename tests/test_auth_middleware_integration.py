from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import app.auth_middleware as auth_middleware


def build_test_app(
    monkeypatch,
    *,
    role: str = "admin",
    active: bool = True,
):
    """
    Small FastAPI app using the REAL AuthMiddleware.

    We mock only token decoding and user lookup so this test does not need
    PostgreSQL or real JWT secrets.
    """

    monkeypatch.setattr(
        auth_middleware,
        "decode_access_token",
        lambda token: (
            {
                "sub": "99",
                "email": "test@example.com",
                "role": role,
            }
            if token == "good-token"
            else None
        ),
    )

    monkeypatch.setattr(
        auth_middleware,
        "get_user_by_id",
        lambda user_id: {
            "id": user_id,
            "email": "test@example.com",
            "role": role,
            "is_active": active,
        },
    )

    monkeypatch.setattr(
        auth_middleware,
        "log_event",
        lambda *args, **kwargs: None,
    )

    app = FastAPI()

    app.add_middleware(
        auth_middleware.AuthMiddleware
    )

    @app.get("/health")
    def health():
        return {
            "status": "ok"
        }

    @app.post("/workflow/start")
    def workflow_start(
        request: Request,
    ):
        return {
            "ok": True,
            "user_role":
                request.state.user[
                    "role"
                ],
        }

    @app.delete(
        "/knowledge/123"
    )
    def delete_knowledge():
        return {
            "deleted": True
        }

    return TestClient(
        app
    )


def test_public_health_endpoint_does_not_require_login(
    monkeypatch,
):
    client = build_test_app(
        monkeypatch
    )

    response = client.get(
        "/health"
    )

    assert response.status_code == 200


def test_protected_workflow_requires_authentication(
    monkeypatch,
):
    client = build_test_app(
        monkeypatch
    )

    response = client.post(
        "/workflow/start"
    )

    assert response.status_code == 401

    assert (
        response.json()[
            "detail"
        ]
        ==
        "Authentication required."
    )


def test_valid_bearer_token_allows_protected_route(
    monkeypatch,
):
    client = build_test_app(
        monkeypatch,
        role="operator",
    )

    response = client.post(
        "/workflow/start",
        headers={
            "Authorization":
                "Bearer good-token"
        },
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "user_role"
        ]
        ==
        "operator"
    )


def test_operator_cannot_delete_knowledge(
    monkeypatch,
):
    client = build_test_app(
        monkeypatch,
        role="operator",
    )

    response = client.delete(
        "/knowledge/123",
        headers={
            "Authorization":
                "Bearer good-token"
        },
    )

    assert response.status_code == 403

    assert (
        response.json()[
            "detail"
        ]
        ==
        "Administrator role required."
    )


def test_admin_can_reach_delete_knowledge_route(
    monkeypatch,
):
    client = build_test_app(
        monkeypatch,
        role="admin",
    )

    response = client.delete(
        "/knowledge/123",
        headers={
            "Authorization":
                "Bearer good-token"
        },
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "deleted"
        ]
        is True
    )


def test_inactive_account_is_rejected(
    monkeypatch,
):
    client = build_test_app(
        monkeypatch,
        role="admin",
        active=False,
    )

    response = client.post(
        "/workflow/start",
        headers={
            "Authorization":
                "Bearer good-token"
        },
    )

    assert response.status_code == 401
