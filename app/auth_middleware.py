from fastapi import Request

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from starlette.responses import (
    JSONResponse,
)

from app.auth import (
    COOKIE_NAME,
    decode_access_token,
    get_user_by_id,
)

from app.observability import (
    log_event,
)


# ============================================================
# PUBLIC ROUTES
# ============================================================

PUBLIC_EXACT_PATHS = {
    "/",
    "/health",
    "/openapi.json",
    "/auth/login",
}

PUBLIC_PREFIXES = (
    "/docs",
    "/redoc",
)


def is_public_path(
    path: str,
) -> bool:

    if path in PUBLIC_EXACT_PATHS:
        return True

    return any(
        path.startswith(
            prefix
        )
        for prefix
        in PUBLIC_PREFIXES
    )


# ============================================================
# ROLE RULES
# ============================================================

def requires_admin(
    method: str,
    path: str,
) -> bool:

    method = (
        method.upper()
    )

    if path.startswith(
        "/auth/users"
    ):
        return True

    if (
        path
        ==
        "/knowledge/upload"
    ):
        return True

    if (
        path.startswith(
            "/knowledge/"
        )
        and
        method
        in {
            "PUT",
            "PATCH",
            "DELETE",
        }
    ):
        return True

    return False


# ============================================================
# TOKEN EXTRACTION
# ============================================================

def extract_token(
    request: Request,
) -> str | None:

    authorization = (
        request.headers.get(
            "Authorization",
            "",
        )
    )

    if (
        authorization
        .lower()
        .startswith(
            "bearer "
        )
    ):
        return (
            authorization[
                7:
            ]
            .strip()
        )

    return request.cookies.get(
        COOKIE_NAME
    )


# ============================================================
# MIDDLEWARE
# ============================================================

class AuthMiddleware(
    BaseHTTPMiddleware
):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):

        path = (
            request.url.path
        )

        method = (
            request.method.upper()
        )

        # CORS preflight requests must be allowed through.
        if method == "OPTIONS":
            return await call_next(
                request
            )

        if is_public_path(
            path
        ):
            return await call_next(
                request
            )

        token = extract_token(
            request
        )

        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "detail":
                        "Authentication required."
                },
            )

        payload = decode_access_token(
            token
        )

        if not payload:
            return JSONResponse(
                status_code=401,
                content={
                    "detail":
                        "Session expired or token is invalid."
                },
            )

        try:
            user_id = int(
                payload["sub"]
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return JSONResponse(
                status_code=401,
                content={
                    "detail":
                        "Invalid authentication token."
                },
            )

        user = get_user_by_id(
            user_id
        )

        if (
            not user
            or
            not user.get(
                "is_active"
            )
        ):
            return JSONResponse(
                status_code=401,
                content={
                    "detail":
                        "User account is inactive or unavailable."
                },
            )

        request.state.user = (
            user
        )

        if (
            requires_admin(
                method,
                path,
            )
            and
            user.get(
                "role"
            )
            !=
            "admin"
        ):
            log_event(
                "security_access_denied",
                {
                    "user_id":
                        user["id"],

                    "email":
                        user["email"],

                    "role":
                        user["role"],

                    "method":
                        method,

                    "path":
                        path,
                },
            )

            return JSONResponse(
                status_code=403,
                content={
                    "detail":
                        "Administrator role required."
                },
            )

        response = await call_next(
            request
        )

        # Audit consequential / mutating requests.
        if method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            if path not in {
                "/auth/login"
            }:
                log_event(
                    "security_api_action",
                    {
                        "user_id":
                            user["id"],

                        "email":
                            user["email"],

                        "role":
                            user["role"],

                        "method":
                            method,

                        "path":
                            path,

                        "status_code":
                            response.status_code,
                    },
                )

        return response
