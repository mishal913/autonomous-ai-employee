"""
These tests protect the current business rule used by workflow.py:

- score >= 60 -> outreach path
- score < 60 -> no outreach path

We keep this small contract test independent of LangGraph/PostgreSQL so
it stays fast and offline.
"""

OUTREACH_THRESHOLD = 60


def route_from_score(
    lead_score: int,
) -> str:

    return (
        "draft_email"
        if lead_score
        >=
        OUTREACH_THRESHOLD
        else "save_lead"
    )


def test_score_below_60_does_not_enter_outreach_path():

    assert (
        route_from_score(
            59
        )
        ==
        "save_lead"
    )


def test_score_60_enters_outreach_path():

    assert (
        route_from_score(
            60
        )
        ==
        "draft_email"
    )


def test_high_score_enters_outreach_path():

    assert (
        route_from_score(
            85
        )
        ==
        "draft_email"
    )
