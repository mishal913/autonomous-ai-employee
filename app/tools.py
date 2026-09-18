import json
import os

from datetime import datetime

from dotenv import load_dotenv

from openai import OpenAI

from sqlalchemy import (
    select,
)

from tavily import TavilyClient

from app.database import (
    SessionLocal,
)

from app.models import (
    Company,
    Lead,
    EmailDraft,
    AgentTask,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

TAVILY_API_KEY = os.getenv(
    "TAVILY_API_KEY"
)

XKIRO_API_KEY = os.getenv(
    "XKIRO_API_KEY"
)

XKIRO_BASE_URL = os.getenv(
    "XKIRO_BASE_URL",
    "https://api.xkiro.com/v1",
)

XKIRO_MODEL = os.getenv(
    "XKIRO_MODEL",
    "mistralai/mistral-large-2512",
)


# ============================================================
# LAZY CLIENTS
# ============================================================

_llm_client = None

_tavily_client = None


def get_tool_llm_client():

    global _llm_client

    if _llm_client is None:

        if not XKIRO_API_KEY:

            raise RuntimeError(
                "XKIRO_API_KEY is missing "
                "from .env"
            )

        _llm_client = OpenAI(
            api_key=XKIRO_API_KEY,
            base_url=XKIRO_BASE_URL,
        )

    return _llm_client


def get_tavily_client():

    global _tavily_client

    if _tavily_client is None:

        if not TAVILY_API_KEY:

            raise RuntimeError(
                "TAVILY_API_KEY is missing "
                "from .env"
            )

        _tavily_client = (
            TavilyClient(
                api_key=TAVILY_API_KEY
            )
        )

    return _tavily_client


# ============================================================
# COMPANY PROFILE
# ============================================================

def get_company_profile(
    company_name: str,
) -> dict:
    """
    Retrieve a company profile from PostgreSQL.

    This is business memory, not live web research.
    """

    company_name = (
        company_name
        .strip()
    )

    if not company_name:

        return {
            "success": False,
            "error": (
                "company_name cannot be empty."
            ),
        }

    db = SessionLocal()

    try:

        company = (
            db.execute(
                select(
                    Company
                )
                .where(
                    Company.name
                    ==
                    company_name
                )
            )
            .scalars()
            .first()
        )

        if not company:

            return {
                "success":
                    True,

                "found":
                    False,

                "company_name":
                    company_name,
            }

        return {
            "success":
                True,

            "found":
                True,

            "company_id":
                company.id,

            "company_name":
                company.name,

            "profile":
                company.profile,

            "created_at":
                (
                    company.created_at
                    .isoformat()
                    if company.created_at
                    else None
                ),
        }

    except Exception as error:

        return {
            "success": False,
            "found": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# LIVE WEB SEARCH
# ============================================================

def search_web(
    query: str,
    max_results: int = 5,
) -> dict:
    """
    Search the live web using Tavily.
    """

    query = (
        query
        .strip()
    )

    if not query:

        return {
            "success": False,
            "error": (
                "Search query cannot be empty."
            ),
        }

    max_results = max(
        1,
        min(
            int(max_results),
            10,
        ),
    )

    try:

        client = (
            get_tavily_client()
        )

        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
        )

        results = (
            response.get(
                "results",
                []
            )
            if isinstance(
                response,
                dict,
            )
            else []
        )

        return {
            "success":
                True,

            "query":
                query,

            "results":
                results,
        }

    except Exception as error:

        print(
            "[TOOLS] WEB SEARCH ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "query": query,
            "error": str(error),
        }


# ============================================================
# DETERMINISTIC LEAD SCORING
# ============================================================

def calculate_lead_score(
    industry_fit: int,
    company_size_fit: int,
    ai_need: int,
    growth_signal: int,
    contact_potential: int,
) -> dict:
    """
    Deterministic scoring.

    Each category:
        0 - 20

    Total:
        0 - 100

    The LLM provides the individual assessments.
    Python calculates the final score.
    """

    scores = {
        "industry_fit":
            industry_fit,

        "company_size_fit":
            company_size_fit,

        "ai_need":
            ai_need,

        "growth_signal":
            growth_signal,

        "contact_potential":
            contact_potential,
    }

    for name, value in scores.items():

        if not isinstance(
            value,
            int,
        ):

            return {
                "success": False,
                "error": (
                    f"{name} must be an integer."
                ),
            }

        if not 0 <= value <= 20:

            return {
                "success": False,
                "error": (
                    f"{name} must be "
                    "between 0 and 20."
                ),
            }

    total_score = sum(
        scores.values()
    )

    if total_score >= 80:

        rating = (
            "Excellent lead"
        )

    elif total_score >= 60:

        rating = (
            "Good lead"
        )

    elif total_score >= 40:

        rating = (
            "Moderate lead"
        )

    else:

        rating = (
            "Weak lead"
        )

    return {
        "success":
            True,

        "scores":
            scores,

        "total_score":
            total_score,

        "rating":
            rating,
    }


# ============================================================
# DRAFT OUTREACH EMAIL
# ============================================================

def draft_outreach_email(
    company_name: str,
    reason_for_contact: str,
    value_proposition: str,
    lead_score: int,
) -> dict:
    """
    Generate an outreach email.

    This function only DRAFTS the email.

    It does NOT send it.

    Sending requires:
        saved draft
        ↓
        human approval
        ↓
        Gmail action
    """

    try:

        client = (
            get_tool_llm_client()
        )

        prompt = f"""
Write a professional B2B outreach email.

PROSPECT:
{company_name}

REASON FOR CONTACT:
{reason_for_contact}

OUR RELEVANT VALUE PROPOSITION:
{value_proposition}

LEAD SCORE:
{lead_score}/100

Return exactly one JSON object:

{{
  "subject": "email subject",
  "body": "email body"
}}

Rules:

1. Keep the email concise.
2. Do not invent facts.
3. Do not invent employee names.
4. Do not invent prices.
5. Do not claim a partnership exists.
6. Do not claim the prospect has a problem unless
   it is supported by the supplied reason.
7. Avoid exaggerated sales language.
8. End with a simple invitation to discuss.
9. Do not include markdown.
10. Return only JSON.
"""

        response = (
            client
            .chat
            .completions
            .create(
                model=XKIRO_MODEL,

                messages=[
                    {
                        "role":
                            "system",

                        "content":
                            (
                                "You write concise, "
                                "evidence-based B2B "
                                "outreach emails."
                            ),
                    },

                    {
                        "role":
                            "user",

                        "content":
                            prompt,
                    },
                ],

                response_format={
                    "type":
                        "json_object"
                },

                max_tokens=700,
            )
        )

        content = (
            response
            .choices[0]
            .message
            .content
            or ""
        )

        data = json.loads(
            content
        )

        subject = str(
            data.get(
                "subject",
                "",
            )
        ).strip()

        body = str(
            data.get(
                "body",
                "",
            )
        ).strip()

        if not subject:

            raise ValueError(
                "Model returned no email subject."
            )

        if not body:

            raise ValueError(
                "Model returned no email body."
            )

        return {
            "success":
                True,

            "subject":
                subject,

            "body":
                body,
        }

    except Exception as error:

        print(
            "[TOOLS] EMAIL DRAFT ERROR:",
            repr(error)
        )

        # ----------------------------------------------------
        # SAFE FALLBACK
        #
        # If the LLM temporarily fails, we still produce
        # a basic draft rather than killing the workflow.
        # ----------------------------------------------------

        fallback_subject = (
            f"AI workflow opportunities "
            f"for {company_name}"
        )

        fallback_body = (
            f"Hello,\n\n"
            f"I’m reaching out regarding {company_name}. "
            f"{reason_for_contact}\n\n"
            f"Our team works on {value_proposition}. "
            f"I thought there may be value in exploring "
            f"whether this could support your current "
            f"workflows.\n\n"
            f"If this is relevant, I would be happy to "
            f"discuss it further.\n\n"
            f"Best regards"
        )

        return {
            "success":
                True,

            "subject":
                fallback_subject,

            "body":
                fallback_body,

            "fallback_used":
                True,

            "generation_error":
                str(error),
        }


# ============================================================
# SAVE LEAD
# ============================================================

def save_lead(
    company_name: str,
    lead_score: int,
    rating: str,
    research_summary: str,
) -> dict:

    db = SessionLocal()

    try:

        lead = Lead(

            company_name=
                company_name,

            lead_score=
                lead_score,

            rating=
                rating,

            research_summary=
                research_summary,
        )

        db.add(
            lead
        )

        db.commit()

        db.refresh(
            lead
        )

        return {
            "success":
                True,

            "lead_id":
                lead.id,

            "company_name":
                lead.company_name,

            "lead_score":
                lead.lead_score,

            "rating":
                lead.rating,
        }

    except Exception as error:

        db.rollback()

        print(
            "[TOOLS] SAVE LEAD ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# GET SAVED LEAD
# ============================================================

def get_saved_lead(
    company_name: str,
) -> dict:
    """
    Get the latest saved lead for a company.

    IMPORTANT:
    There is intentionally NO lead.contacted field.

    Email delivery state is stored in EmailDraft:
        draft
        approved
        rejected
        sending
        sent
        send_failed
    """

    company_name = (
        company_name
        .strip()
    )

    if not company_name:

        return {
            "success": False,
            "found": False,
            "error": (
                "company_name cannot be empty."
            ),
        }

    db = SessionLocal()

    try:

        lead = (
            db.execute(
                select(
                    Lead
                )
                .where(
                    Lead.company_name
                    ==
                    company_name
                )
                .order_by(
                    Lead.created_at
                    .desc()
                )
                .limit(1)
            )
            .scalars()
            .first()
        )

        if not lead:

            return {
                "success":
                    True,

                "found":
                    False,

                "company_name":
                    company_name,
            }

        return {
            "success":
                True,

            "found":
                True,

            "lead_id":
                lead.id,

            "company_name":
                lead.company_name,

            "lead_score":
                lead.lead_score,

            "rating":
                lead.rating,

            "research_summary":
                lead.research_summary,

            "created_at":
                (
                    lead.created_at
                    .isoformat()
                    if lead.created_at
                    else None
                ),
        }

    except Exception as error:

        print(
            "[TOOLS] GET LEAD ERROR:",
            repr(error)
        )

        return {
            "success":
                False,

            "found":
                False,

            "error":
                str(error),
        }

    finally:

        db.close()


# ============================================================
# CREATE AGENT TASK
# ============================================================

def create_agent_task(
    objective: str,
) -> dict:

    db = SessionLocal()

    try:

        task = AgentTask(

            objective=
                objective,

            status=
                "running",
        )

        db.add(
            task
        )

        db.commit()

        db.refresh(
            task
        )

        return {
            "success":
                True,

            "task_id":
                task.id,

            "status":
                task.status,
        }

    except Exception as error:

        db.rollback()

        print(
            "[TOOLS] CREATE TASK ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# UPDATE AGENT TASK STATUS
# ============================================================

def update_agent_task_status(
    task_id: int,
    status: str,
) -> dict:

    db = SessionLocal()

    try:

        task = db.get(
            AgentTask,
            task_id,
        )

        if not task:

            return {
                "success":
                    False,

                "error":
                    (
                        f"Agent task "
                        f"{task_id} "
                        "was not found."
                    ),
            }

        task.status = (
            status
        )

        db.commit()

        return {
            "success":
                True,

            "task_id":
                task.id,

            "status":
                task.status,
        }

    except Exception as error:

        db.rollback()

        return {
            "success": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# COMPLETE AGENT TASK
# ============================================================

def complete_agent_task(
    task_id: int,
    result: str,
) -> dict:

    db = SessionLocal()

    try:

        task = db.get(
            AgentTask,
            task_id,
        )

        if not task:

            return {
                "success": False,
                "error": (
                    f"Agent task "
                    f"{task_id} "
                    "was not found."
                ),
            }

        task.status = (
            "completed"
        )

        task.result = (
            result
        )

        task.error = None

        task.completed_at = (
            datetime.utcnow()
        )

        db.commit()

        return {
            "success":
                True,

            "task_id":
                task.id,

            "status":
                task.status,
        }

    except Exception as error:

        db.rollback()

        return {
            "success": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# FAIL AGENT TASK
# ============================================================

def fail_agent_task(
    task_id: int,
    error_message: str,
) -> dict:

    db = SessionLocal()

    try:

        task = db.get(
            AgentTask,
            task_id,
        )

        if not task:

            return {
                "success": False,
                "error": (
                    f"Agent task "
                    f"{task_id} "
                    "was not found."
                ),
            }

        task.status = (
            "failed"
        )

        task.error = (
            error_message
        )

        task.completed_at = (
            datetime.utcnow()
        )

        db.commit()

        return {
            "success":
                True,

            "task_id":
                task.id,

            "status":
                task.status,
        }

    except Exception as error:

        db.rollback()

        return {
            "success": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# GET AGENT TASK
# ============================================================

def get_agent_task(
    task_id: int,
) -> dict:

    db = SessionLocal()

    try:

        task = db.get(
            AgentTask,
            task_id,
        )

        if not task:

            return {
                "success":
                    True,

                "found":
                    False,

                "task_id":
                    task_id,
            }

        return {
            "success":
                True,

            "found":
                True,

            "task_id":
                task.id,

            "objective":
                task.objective,

            "status":
                task.status,

            "result":
                task.result,

            "error":
                task.error,

            "created_at":
                (
                    task.created_at
                    .isoformat()
                    if task.created_at
                    else None
                ),

            "completed_at":
                (
                    task.completed_at
                    .isoformat()
                    if task.completed_at
                    else None
                ),
        }

    except Exception as error:

        return {
            "success": False,
            "found": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# SAVE EMAIL DRAFT
# ============================================================

def save_email_draft(
    company_name: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> dict:

    db = SessionLocal()

    try:

        draft = EmailDraft(

            company_name=
                company_name,

            recipient_email=
                recipient_email,

            subject=
                subject,

            body=
                body,

            status=
                "draft",
        )

        db.add(
            draft
        )

        db.commit()

        db.refresh(
            draft
        )

        return {
            "success":
                True,

            "draft_id":
                draft.id,

            "status":
                draft.status,

            "company_name":
                draft.company_name,

            "recipient_email":
                draft.recipient_email,

            "subject":
                draft.subject,
        }

    except Exception as error:

        db.rollback()

        print(
            "[TOOLS] SAVE EMAIL ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# UPDATE EMAIL DRAFT STATUS
# ============================================================

def update_email_draft_status(
    draft_id: int,
    status: str,
) -> dict:

    allowed_statuses = {
        "draft",
        "approved",
        "rejected",
        "sending",
        "sent",
        "send_failed",
    }

    if status not in allowed_statuses:

        return {
            "success":
                False,

            "error":
                (
                    f"Invalid email status: "
                    f"{status}"
                ),
        }

    db = SessionLocal()

    try:

        draft = db.get(
            EmailDraft,
            draft_id,
        )

        if not draft:

            return {
                "success":
                    False,

                "error":
                    (
                        f"Email draft "
                        f"{draft_id} "
                        "was not found."
                    ),
            }

        draft.status = (
            status
        )

        db.commit()

        return {
            "success":
                True,

            "draft_id":
                draft.id,

            "status":
                draft.status,
        }

    except Exception as error:

        db.rollback()

        return {
            "success": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# GET EMAIL DRAFT
# ============================================================

def get_email_draft(
    draft_id: int,
) -> dict:

    db = SessionLocal()

    try:

        draft = db.get(
            EmailDraft,
            draft_id,
        )

        if not draft:

            return {
                "success":
                    True,

                "found":
                    False,

                "draft_id":
                    draft_id,
            }

        return {
            "success":
                True,

            "found":
                True,

            "draft_id":
                draft.id,

            "company_name":
                draft.company_name,

            "recipient_email":
                draft.recipient_email,

            "subject":
                draft.subject,

            "body":
                draft.body,

            "status":
                draft.status,

            "gmail_message_id":
                draft.gmail_message_id,

            "gmail_thread_id":
                draft.gmail_thread_id,

            "sent_at":
                (
                    draft.sent_at
                    .isoformat()
                    if draft.sent_at
                    else None
                ),

            "send_error":
                draft.send_error,

            "created_at":
                (
                    draft.created_at
                    .isoformat()
                    if draft.created_at
                    else None
                ),
        }

    except Exception as error:

        return {
            "success": False,
            "found": False,
            "error": str(error),
        }

    finally:

        db.close()


# ============================================================
# SEND HUMAN-APPROVED EMAIL
# ============================================================

def send_approved_email_draft(
    draft_id: int,
) -> dict:
    """
    Execute the real Gmail side effect.

    Safety rules:

    1. Draft must exist.
    2. Draft must be human approved.
    3. Draft must have recipient.
    4. Draft cannot already have been sent.
    5. Database is marked `sending` before Gmail call.
    """

    # Import locally to keep Gmail dependency separate
    # until we actually need to send.
    from app.gmail_client import (
        send_email,
    )

    db = SessionLocal()

    try:

        draft = db.get(
            EmailDraft,
            draft_id,
        )

        # ----------------------------------------------------
        # EXISTS?
        # ----------------------------------------------------

        if not draft:

            return {
                "success":
                    False,

                "error":
                    (
                        f"Email draft "
                        f"{draft_id} "
                        "was not found."
                    ),
            }

        # ----------------------------------------------------
        # DUPLICATE SEND PROTECTION
        # ----------------------------------------------------

        if (
            draft.status
            ==
            "sent"
            or
            draft.gmail_message_id
        ):

            return {
                "success":
                    True,

                "already_sent":
                    True,

                "draft_id":
                    draft.id,

                "status":
                    "sent",

                "gmail_message_id":
                    draft.gmail_message_id,

                "gmail_thread_id":
                    draft.gmail_thread_id,

                "sent_at":
                    (
                        draft.sent_at
                        .isoformat()
                        if draft.sent_at
                        else None
                    ),
            }

        # ----------------------------------------------------
        # HUMAN APPROVAL REQUIRED
        # ----------------------------------------------------

        if draft.status != "approved":

            return {
                "success":
                    False,

                "error":
                    (
                        "Email cannot be sent because "
                        f"draft status is '{draft.status}'. "
                        "Human approval is required."
                    ),
            }

        # ----------------------------------------------------
        # RECIPIENT REQUIRED
        # ----------------------------------------------------

        if not draft.recipient_email:

            return {
                "success":
                    False,

                "error":
                    (
                        "Email draft has no "
                        "recipient address."
                    ),
            }

        # ----------------------------------------------------
        # MARK AS SENDING BEFORE EXTERNAL ACTION
        # ----------------------------------------------------

        draft.status = (
            "sending"
        )

        draft.send_error = None

        db.commit()

        # ----------------------------------------------------
        # REAL GMAIL CALL
        # ----------------------------------------------------

        try:

            gmail_result = send_email(

                to_email=
                    draft.recipient_email,

                subject=
                    draft.subject,

                body=
                    draft.body,
            )

        except Exception as error:

            draft.status = (
                "send_failed"
            )

            draft.send_error = (
                str(error)
            )

            db.commit()

            return {
                "success":
                    False,

                "draft_id":
                    draft.id,

                "status":
                    "send_failed",

                "error":
                    str(error),
            }

        # ----------------------------------------------------
        # HANDLE DIFFERENT GMAIL HELPER RETURN SHAPES
        # ----------------------------------------------------

        if not isinstance(
            gmail_result,
            dict,
        ):

            gmail_result = {}

        gmail_message_id = (
            gmail_result.get(
                "gmail_message_id"
            )
            or
            gmail_result.get(
                "id"
            )
        )

        gmail_thread_id = (
            gmail_result.get(
                "gmail_thread_id"
            )
            or
            gmail_result.get(
                "threadId"
            )
        )

        # ----------------------------------------------------
        # SAVE SUCCESS
        # ----------------------------------------------------

        sent_at = (
            datetime.utcnow()
        )

        draft.status = (
            "sent"
        )

        draft.gmail_message_id = (
            gmail_message_id
        )

        draft.gmail_thread_id = (
            gmail_thread_id
        )

        draft.sent_at = (
            sent_at
        )

        draft.send_error = None

        db.commit()

        return {
            "success":
                True,

            "already_sent":
                False,

            "draft_id":
                draft.id,

            "status":
                "sent",

            "recipient_email":
                draft.recipient_email,

            "gmail_message_id":
                gmail_message_id,

            "gmail_thread_id":
                gmail_thread_id,

            "sent_at":
                sent_at.isoformat(),
        }

    except Exception as error:

        db.rollback()

        print(
            "[TOOLS] SEND EMAIL ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": str(error),
        }

    finally:

        db.close()