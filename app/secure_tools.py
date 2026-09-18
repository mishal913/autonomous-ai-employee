"""
Secure tool wrappers V2.

The wrappers keep the same signatures used by workflow.py while emitting
severity-aware security observability.
"""

from __future__ import annotations

from app.observability import (
    log_event,
)

from app.rag import (
    semantic_search as raw_semantic_search,
)

from app.security_guardrails import (
    secure_rag_results,
    secure_web_search_response,
    validate_outbound_email,
)

from app.tools import (
    get_email_draft,
    search_web as raw_search_web,
    send_approved_email_draft as raw_send_approved_email_draft,
)


# ============================================================
# EVENT HELPER
# ============================================================

def _log_security_summary(
    *,
    source_type: str,
    summary: dict,
    query_preview: str,
) -> None:

    if source_type == "web":

        log_event(
            "security_web_evidence_scanned",
            {
                "query_preview":
                    query_preview,

                **summary,
            },
        )

        high_items = summary.get(
            "high_risk_sources",
            0,
        )

        warning_items = summary.get(
            "warning_sources",
            0,
        )

    else:

        log_event(
            "security_rag_evidence_scanned",
            {
                "query_preview":
                    query_preview,

                **summary,
            },
        )

        high_items = summary.get(
            "high_risk_chunks",
            0,
        )

        warning_items = summary.get(
            "warning_chunks",
            0,
        )

    if (
        summary.get(
            "high_confidence_detections",
            0,
        )
        >
        0
    ):

        log_event(
            "security_prompt_injection_blocked",
            {
                "source_type":
                    source_type,

                "high_risk_items":
                    high_items,

                "high_confidence_detections":
                    summary.get(
                        "high_confidence_detections",
                        0,
                    ),

                "categories":
                    summary.get(
                        "high_categories",
                        [],
                    ),
            },
        )

        # Keep legacy event name so any current UI/analysis that already
        # expects it continues to work.
        log_event(
            "security_prompt_injection_detected",
            {
                "source_type":
                    source_type,

                "severity":
                    "high",

                "suspicious_items":
                    high_items,

                "detections":
                    summary.get(
                        "high_confidence_detections",
                        0,
                    ),

                "categories":
                    summary.get(
                        "high_categories",
                        [],
                    ),
            },
        )

    if (
        summary.get(
            "warning_detections",
            0,
        )
        >
        0
    ):

        log_event(
            "security_prompt_injection_warning",
            {
                "source_type":
                    source_type,

                "warning_items":
                    warning_items,

                "warning_detections":
                    summary.get(
                        "warning_detections",
                        0,
                    ),

                "categories":
                    summary.get(
                        "warning_categories",
                        [],
                    ),
            },
        )


# ============================================================
# WEB
# ============================================================

def search_web(
    query: str,
    max_results: int = 5,
) -> dict:

    response = raw_search_web(
        query=query,
        max_results=max_results,
    )

    if not response.get(
        "success"
    ):

        return response

    secured, summary = (
        secure_web_search_response(
            response
        )
    )

    _log_security_summary(
        source_type="web",
        summary=summary,
        query_preview=str(
            query
        )[:180],
    )

    return secured


# ============================================================
# RAG
# ============================================================

def semantic_search(
    query: str,
    limit: int = 5,
) -> dict:

    response = raw_semantic_search(
        query=query,
        limit=limit,
    )

    if not response.get(
        "success"
    ):

        return response

    safe_results, summary = (
        secure_rag_results(
            response.get(
                "results",
                [],
            )
        )
    )

    secured = dict(
        response
    )

    secured[
        "results"
    ] = safe_results

    secured[
        "_security"
    ] = summary

    _log_security_summary(
        source_type="rag",
        summary=summary,
        query_preview=str(
            query
        )[:180],
    )

    return secured


# ============================================================
# GMAIL ACTION
# ============================================================

def send_approved_email_draft(
    draft_id: int,
) -> dict:

    draft_result = get_email_draft(
        draft_id
    )

    if (
        not draft_result.get(
            "success"
        )
        or
        not draft_result.get(
            "found"
        )
    ):

        log_event(
            "security_email_action_blocked",
            {
                "draft_id":
                    draft_id,

                "reason":
                    (
                        "Draft could not be "
                        "loaded for validation."
                    ),
            },
        )

        return {
            "success":
                False,

            "draft_id":
                draft_id,

            "error":
                (
                    "Email action blocked because "
                    "the draft could not be validated."
                ),
        }

    draft_status = str(
        draft_result.get(
            "status",
            "",
        )
    ).lower()

    validation = (
        validate_outbound_email(
            recipient_email=str(
                draft_result.get(
                    "recipient_email",
                    "",
                )
            ),
            subject=str(
                draft_result.get(
                    "subject",
                    "",
                )
            ),
            body=str(
                draft_result.get(
                    "body",
                    "",
                )
            ),
            approval_status=draft_status,
        )
    )

    if not validation[
        "allowed"
    ]:

        log_event(
            "security_email_action_blocked",
            {
                "draft_id":
                    draft_id,

                "problems":
                    validation[
                        "problems"
                    ],
            },
        )

        return {
            "success":
                False,

            "draft_id":
                draft_id,

            "error":
                (
                    "Email action blocked by "
                    "security validation."
                ),

            "security_problems":
                validation[
                    "problems"
                ],
        }

    recipient = str(
        draft_result.get(
            "recipient_email",
            "",
        )
    )

    recipient_domain = (
        recipient
        .split(
            "@"
        )[-1]
        .lower()
        if "@" in recipient
        else ""
    )

    log_event(
        "security_email_action_validated",
        {
            "draft_id":
                draft_id,

            "recipient_domain":
                recipient_domain,
        },
    )

    return (
        raw_send_approved_email_draft(
            draft_id
        )
    )
