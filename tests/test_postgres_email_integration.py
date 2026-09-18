"""
Stage 4C — PostgreSQL-backed integration tests.

These tests use the SAME PostgreSQL server/database connection as the app,
but create a TEMPORARY ISOLATED SCHEMA.

They do not use your normal application tables.

The schema is dropped after the test session.
Gmail is always mocked.
"""

from __future__ import annotations

import uuid

import pytest

from sqlalchemy import (
    create_engine,
    event,
)
from sqlalchemy.orm import (
    sessionmaker,
)

import app.database as database
import app.gmail_client as gmail_client
import app.tools as tools

from app.models import (
    EmailDraft,
)


@pytest.fixture(
    scope="module"
)
def isolated_postgres():
    """
    Build a temporary PostgreSQL schema and bind app.tools.SessionLocal
    to that isolated schema for this module.
    """

    production_engine = getattr(
        database,
        "engine",
        None,
    )

    if production_engine is None:
        pytest.skip(
            "app.database.engine was not found."
        )

    schema_name = (
        "stage4c_"
        +
        uuid.uuid4().hex[:12]
    )

    # Create schema using the app's existing PostgreSQL connection.
    try:
        with production_engine.begin() as connection:
            connection.exec_driver_sql(
                f'CREATE SCHEMA "{schema_name}"'
            )
    except Exception as error:
        pytest.skip(
            "Could not create isolated PostgreSQL test schema. "
            f"Reason: {error}"
        )

    test_engine = create_engine(
        production_engine.url,
        pool_pre_ping=True,
    )

    @event.listens_for(
        test_engine,
        "connect",
    )
    def set_search_path(
        dbapi_connection,
        connection_record,
    ):
        cursor = (
            dbapi_connection.cursor()
        )

        cursor.execute(
            f'SET search_path TO "{schema_name}", public'
        )

        cursor.close()

    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    try:
        # Create ONLY the EmailDraft table needed by these tests.
        EmailDraft.__table__.create(
            bind=test_engine,
            checkfirst=False,
        )

        yield {
            "schema_name":
                schema_name,

            "engine":
                test_engine,

            "SessionLocal":
                TestSessionLocal,
        }

    finally:
        test_engine.dispose()

        with production_engine.begin() as connection:
            connection.exec_driver_sql(
                f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'
            )


@pytest.fixture
def isolated_tools_session(
    monkeypatch,
    isolated_postgres,
):
    """
    Redirect the real app.tools functions to the isolated test schema.
    """

    TestSessionLocal = (
        isolated_postgres[
            "SessionLocal"
        ]
    )

    monkeypatch.setattr(
        tools,
        "SessionLocal",
        TestSessionLocal,
    )

    return TestSessionLocal


def test_save_and_get_email_draft_round_trip(
    isolated_tools_session,
):
    saved = tools.save_email_draft(
        company_name=
            "Stage 4C Test Company",

        recipient_email=
            "person@example.com",

        subject=
            "AI automation opportunity",

        body=
            "Hello from the isolated database test.",
    )

    assert saved[
        "success"
    ] is True

    draft_id = saved[
        "draft_id"
    ]

    loaded = tools.get_email_draft(
        draft_id
    )

    assert loaded[
        "success"
    ] is True

    assert loaded[
        "found"
    ] is True

    assert loaded[
        "status"
    ] == "draft"

    assert (
        loaded[
            "recipient_email"
        ]
        ==
        "person@example.com"
    )


def test_email_status_persists_in_postgresql(
    isolated_tools_session,
):
    saved = tools.save_email_draft(
        company_name=
            "Approval Persistence Test",

        recipient_email=
            "person@example.com",

        subject=
            "Approval test",

        body=
            "Hello",
    )

    draft_id = saved[
        "draft_id"
    ]

    updated = (
        tools.update_email_draft_status(
            draft_id=draft_id,
            status="approved",
        )
    )

    assert updated[
        "success"
    ] is True

    loaded = tools.get_email_draft(
        draft_id
    )

    assert loaded[
        "status"
    ] == "approved"


def test_approved_send_persists_gmail_metadata_without_real_gmail(
    monkeypatch,
    isolated_tools_session,
):
    gmail_calls = []

    def fake_send_email(
        *,
        to_email,
        subject,
        body,
    ):
        gmail_calls.append(
            {
                "to_email":
                    to_email,

                "subject":
                    subject,

                "body":
                    body,
            }
        )

        return {
            "gmail_message_id":
                "mock-message-123",

            "gmail_thread_id":
                "mock-thread-456",
        }

    monkeypatch.setattr(
        gmail_client,
        "send_email",
        fake_send_email,
    )

    saved = tools.save_email_draft(
        company_name=
            "Safe Gmail Test",

        recipient_email=
            "person@example.com",

        subject=
            "Approved outreach",

        body=
            "This message is never sent to real Gmail.",
    )

    draft_id = saved[
        "draft_id"
    ]

    approved = (
        tools.update_email_draft_status(
            draft_id=draft_id,
            status="approved",
        )
    )

    assert approved[
        "success"
    ] is True

    result = (
        tools.send_approved_email_draft(
            draft_id
        )
    )

    assert result[
        "success"
    ] is True

    assert len(
        gmail_calls
    ) == 1

    assert (
        result[
            "gmail_message_id"
        ]
        ==
        "mock-message-123"
    )

    loaded = tools.get_email_draft(
        draft_id
    )

    assert loaded[
        "status"
    ] == "sent"

    assert (
        loaded[
            "gmail_message_id"
        ]
        ==
        "mock-message-123"
    )


def test_duplicate_send_is_idempotent_and_does_not_call_gmail_twice(
    monkeypatch,
    isolated_tools_session,
):
    gmail_calls = []

    def fake_send_email(
        *,
        to_email,
        subject,
        body,
    ):
        gmail_calls.append(
            to_email
        )

        return {
            "gmail_message_id":
                "mock-idempotent-message",

            "gmail_thread_id":
                "mock-idempotent-thread",
        }

    monkeypatch.setattr(
        gmail_client,
        "send_email",
        fake_send_email,
    )

    saved = tools.save_email_draft(
        company_name=
            "Idempotency Test Company",

        recipient_email=
            "person@example.com",

        subject=
            "Idempotency test",

        body=
            "This is a mocked message.",
    )

    draft_id = saved[
        "draft_id"
    ]

    tools.update_email_draft_status(
        draft_id=draft_id,
        status="approved",
    )

    first = (
        tools.send_approved_email_draft(
            draft_id
        )
    )

    second = (
        tools.send_approved_email_draft(
            draft_id
        )
    )

    assert first[
        "success"
    ] is True

    assert second[
        "success"
    ] is True

    assert second[
        "already_sent"
    ] is True

    # This is the important assertion:
    # the external Gmail function ran exactly once.
    assert len(
        gmail_calls
    ) == 1

    assert (
        second[
            "gmail_message_id"
        ]
        ==
        "mock-idempotent-message"
    )
