import base64
import os
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent.parent

CREDENTIALS_PATH = (
    BASE_DIR / "credentials.json"
)

TOKEN_PATH = (
    BASE_DIR / "token.json"
)


# ============================================================
# GMAIL PERMISSIONS
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]


# ============================================================
# AUTHENTICATION
# ============================================================

def get_gmail_credentials() -> Credentials:
    """
    Load or create OAuth credentials for Gmail.

    First run:
        opens browser for user authorization

    Later runs:
        reuses token.json
    """

    credentials = None

    # --------------------------------------------------------
    # Existing login token
    # --------------------------------------------------------

    if TOKEN_PATH.exists():

        credentials = (
            Credentials
            .from_authorized_user_file(
                str(TOKEN_PATH),
                SCOPES,
            )
        )


    # --------------------------------------------------------
    # Token missing or expired
    # --------------------------------------------------------

    if (
        not credentials
        or not credentials.valid
    ):

        # ----------------------------------------------------
        # Refresh existing token
        # ----------------------------------------------------

        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
        ):

            credentials.refresh(
                Request()
            )

        # ----------------------------------------------------
        # First-time login
        # ----------------------------------------------------

        else:

            if not CREDENTIALS_PATH.exists():

                raise FileNotFoundError(
                    "credentials.json was not found "
                    f"at {CREDENTIALS_PATH}"
                )


            flow = (
                InstalledAppFlow
                .from_client_secrets_file(
                    str(
                        CREDENTIALS_PATH
                    ),
                    SCOPES,
                )
            )


            credentials = (
                flow.run_local_server(
                    port=0
                )
            )


        # ----------------------------------------------------
        # Save access + refresh token
        # ----------------------------------------------------

        TOKEN_PATH.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )


    return credentials


# ============================================================
# BUILD GMAIL SERVICE
# ============================================================

def get_gmail_service():
    """
    Return authenticated Gmail API service.
    """

    credentials = (
        get_gmail_credentials()
    )


    service = build(
        "gmail",
        "v1",
        credentials=credentials,
    )


    return service


# ============================================================
# TEST CONNECTION
# ============================================================

def test_gmail_connection() -> dict:
    """
    Confirm OAuth works without sending email.

    gmail.send scope does not give us general
    mailbox-read permission, so this test simply
    confirms that an authenticated service can
    be created successfully.
    """

    try:

        service = (
            get_gmail_service()
        )


        if service:

            return {
                "success": True,
                "message": (
                    "Gmail OAuth authentication "
                    "completed successfully."
                ),
            }


        return {
            "success": False,
            "error": (
                "Could not create Gmail service."
            ),
        }


    except Exception as error:

        return {
            "success": False,
            "error": str(error),
        }


# ============================================================
# CREATE MIME MESSAGE
# ============================================================

def create_email_message(
    to_email: str,
    subject: str,
    body: str,
) -> dict:
    """
    Build an RFC-compliant email message
    and convert it to Gmail's base64URL format.
    """

    message = EmailMessage()

    message["To"] = to_email
    message["Subject"] = subject

    message.set_content(
        body
    )


    encoded_message = (
        base64
        .urlsafe_b64encode(
            message.as_bytes()
        )
        .decode()
    )


    return {
        "raw": encoded_message
    }


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(
    to_email: str,
    subject: str,
    body: str,
) -> dict:
    """
    Send a real email through Gmail.

    IMPORTANT:
    This function performs a real external action.

    It should only be called AFTER
    human approval in LangGraph.
    """

    try:

        service = (
            get_gmail_service()
        )


        gmail_message = (
            create_email_message(
                to_email=to_email,
                subject=subject,
                body=body,
            )
        )


        result = (
            service
            .users()
            .messages()
            .send(
                userId="me",
                body=gmail_message,
            )
            .execute()
        )


        return {
            "success": True,

            "message_id":
                result.get(
                    "id"
                ),

            "thread_id":
                result.get(
                    "threadId"
                ),

            "to_email":
                to_email,

            "subject":
                subject,
        }


    except HttpError as error:

        return {
            "success": False,

            "error":
                f"Gmail API error: "
                f"{str(error)}",
        }


    except Exception as error:

        return {
            "success": False,
            "error": str(error),
        }