import os

from datetime import datetime
from typing import Literal

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
)

from fastapi.responses import (
    JSONResponse,
)

from pydantic import (
    BaseModel,
    Field,
)

from app.auth import (
    COOKIE_NAME,
    TOKEN_HOURS,
    create_access_token,
    create_user,
    ensure_initial_admin,
    get_user_by_email,
    list_users,
    set_user_active,
    update_last_login,
    verify_password,
)

from app.observability import (
    log_event,
)


router = APIRouter(
    prefix="/auth",
    tags=[
        "Authentication"
    ],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class LoginRequest(
    BaseModel
):
    email: str = Field(
        min_length=3,
        max_length=320,
    )

    password: str = Field(
        min_length=1,
        max_length=512,
    )


class CreateUserRequest(
    BaseModel
):
    email: str = Field(
        min_length=3,
        max_length=320,
    )

    password: str = Field(
        min_length=10,
        max_length=512,
    )

    role: Literal[
        "admin",
        "operator",
    ]


class UserActiveRequest(
    BaseModel
):
    is_active: bool


# ============================================================
# SERIALIZATION
# ============================================================

def serialize_user(
    user: dict,
) -> dict:

    def serialize_date(
        value,
    ):
        if isinstance(
            value,
            datetime,
        ):
            return value.isoformat()

        return value

    return {
        "id":
            user.get(
                "id"
            ),

        "email":
            user.get(
                "email"
            ),

        "role":
            user.get(
                "role"
            ),

        "is_active":
            user.get(
                "is_active"
            ),

        "created_at":
            serialize_date(
                user.get(
                    "created_at"
                )
            ),

        "last_login_at":
            serialize_date(
                user.get(
                    "last_login_at"
                )
            ),
    }


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/login"
)
def login(
    request: LoginRequest,
):

    ensure_initial_admin()

    user = get_user_by_email(
        request.email
    )

    if (
        not user
        or
        not user.get(
            "is_active"
        )
        or
        not verify_password(
            request.password,
            user.get(
                "password_hash",
                "",
            ),
        )
    ):
        log_event(
            "security_login_failed",
            {
                "email":
                    request.email
                    .strip()
                    .lower()
            },
        )

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid email or password."
            ),
        )

    token, expires_at = (
        create_access_token(
            user
        )
    )

    update_last_login(
        user["id"]
    )

    response = JSONResponse(
        {
            "success":
                True,

            "user":
                serialize_user(
                    user
                ),

            "expires_at":
                expires_at
                .isoformat(),
        }
    )

    secure_cookie = (
        os.getenv(
            "AUTH_COOKIE_SECURE",
            "false",
        )
        .strip()
        .lower()
        ==
        "true"
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=(
            TOKEN_HOURS
            *
            60
            *
            60
        ),
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )

    log_event(
        "security_login_succeeded",
        {
            "user_id":
                user["id"],

            "email":
                user["email"],

            "role":
                user["role"],
        },
    )

    return response


# ============================================================
# LOGOUT
# ============================================================

@router.post(
    "/logout"
)
def logout(
    request: Request,
):

    user = getattr(
        request.state,
        "user",
        None,
    )

    response = JSONResponse(
        {
            "success":
                True
        }
    )

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )

    if user:
        log_event(
            "security_logout",
            {
                "user_id":
                    user.get(
                        "id"
                    ),

                "email":
                    user.get(
                        "email"
                    ),
            },
        )

    return response


# ============================================================
# CURRENT USER
# ============================================================

@router.get(
    "/me"
)
def me(
    request: Request,
):

    user = getattr(
        request.state,
        "user",
        None,
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication required."
            ),
        )

    return {
        "authenticated":
            True,

        "user":
            serialize_user(
                user
            ),
    }


# ============================================================
# CREATE USER — ADMIN ONLY
# ============================================================

@router.post(
    "/users"
)
def create_application_user(
    body: CreateUserRequest,
    request: Request,
):

    actor = (
        request.state.user
    )

    try:
        user = create_user(
            email=body.email,
            password=body.password,
            role=body.role,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(
                error
            ),
        )

    except Exception as error:

        message = str(
            error
        )

        if (
            "duplicate"
            in
            message.lower()
            or
            "unique"
            in
            message.lower()
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "A user with this email already exists."
                ),
            )

        raise HTTPException(
            status_code=500,
            detail=message,
        )

    log_event(
        "security_user_created",
        {
            "actor_user_id":
                actor["id"],

            "actor_email":
                actor["email"],

            "created_user_id":
                user["id"],

            "created_email":
                user["email"],

            "created_role":
                user["role"],
        },
    )

    return {
        "success":
            True,

        "user":
            serialize_user(
                user
            ),
    }


# ============================================================
# LIST USERS — ADMIN ONLY
# ============================================================

@router.get(
    "/users"
)
def get_application_users():

    return {
        "users": [
            serialize_user(
                user
            )
            for user
            in list_users()
        ]
    }


# ============================================================
# ENABLE / DISABLE USER — ADMIN ONLY
# ============================================================

@router.patch(
    "/users/{user_id}/active"
)
def update_user_active_state(
    user_id: int,
    body: UserActiveRequest,
    request: Request,
):

    actor = (
        request.state.user
    )

    if (
        actor["id"]
        ==
        user_id
        and
        body.is_active
        is
        False
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "You cannot deactivate your own active session."
            ),
        )

    user = set_user_active(
        user_id=user_id,
        is_active=body.is_active,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail=(
                "User not found."
            ),
        )

    log_event(
        "security_user_active_changed",
        {
            "actor_user_id":
                actor["id"],

            "target_user_id":
                user_id,

            "is_active":
                body.is_active,
        },
    )

    return {
        "success":
            True,

        "user":
            serialize_user(
                user
            ),
    }
