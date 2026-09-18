from pathlib import Path
from typing import Literal
from app.live_api import (
    router as live_workflow_router,
)
from app.knowledge_api import (
    router as knowledge_admin_router,
)
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from app.auth_api import (
    router as auth_router,
)

from app.auth_middleware import (
    AuthMiddleware,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from pydantic import (
    BaseModel,
    Field,
)

from app.ai import (
    ask_ai,
    research_company,
    research_company_web,
    run_agent,
)

from app.database import (
    create_tables,
    test_connection,
)

from app.rag import (
    delete_knowledge_document,
    ingest_document,
    list_knowledge_documents,
    semantic_search,
)

from app.workflow import (
    get_company_workflow_status,
    resume_company_workflow,
    run_company_workflow,
)

from app.observability import (
    get_observability_summary,
    get_recent_events,
    get_task_trace,
)

from app.tools import (
    get_email_draft,
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Autonomous AI Employee",

    description=(
        "AI-powered business-development "
        "employee with live research, RAG, "
        "LangGraph workflows, human approval, "
        "Gmail actions, evaluation and "
        "observability."
    ),

    version="1.2.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    AuthMiddleware
)

app.include_router(
    auth_router
)
app.include_router(
    live_workflow_router
)
app.include_router(
    knowledge_admin_router
)
app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event(
    "startup"
)
def startup_event():

    print(
        "\n[APP] Starting Autonomous AI Employee"
    )

    create_tables()

    print(
        "[APP] Database tables checked"
    )


# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(
    BaseModel
):

    message: str


class AgentRequest(
    BaseModel
):

    message: str


class CompanyRequest(
    BaseModel
):

    company_name: str


class WorkflowRequest(
    BaseModel
):

    objective: str

    company_name: str

    recipient_email: str


class ApprovalDecisionRequest(
    BaseModel
):

    decision: Literal[
        "approve",
        "reject",
    ]

    comment: str = ""


class KnowledgeSearchRequest(
    BaseModel
):

    query: str = Field(
        min_length=1,
        max_length=2000,
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {

        "name":
            "Autonomous AI Employee",

        "status":
            "running",

        "version":
            "1.2.0",

        "features": [

            "LLM reasoning",

            "live web research",

            "PostgreSQL business memory",

            "LangGraph workflows",

            "persistent checkpoints",

            "human approval",

            "Gmail sending",

            "private RAG knowledge",

            "pgvector semantic search",

            "RAG evaluation",

            "structured observability",

            "frontend document upload",

            "email review before approval",
        ],
    }


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health"
)
def health():

    try:

        database = (
            test_connection()
        )

        return {

            "status":
                "healthy",

            "database":
                database,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,

            detail=(
                "Database health check failed: "
                f"{error}"
            ),
        )


# ============================================================
# CHAT
# ============================================================

@app.post(
    "/chat"
)
def chat(
    request: ChatRequest,
):

    try:

        response = ask_ai(
            request.message
        )

        return {

            "success":
                True,

            "response":
                response,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# COMPANY RESEARCH
# ============================================================

@app.post(
    "/research-company"
)
def company_research(
    request: CompanyRequest,
):

    try:

        result = (
            research_company(
                request.company_name
            )
        )

        return {

            "success":
                True,

            "company":
                request.company_name,

            "result":
                result,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# WEB RESEARCH
# ============================================================

@app.post(
    "/web-research"
)
def web_company_research(
    request: CompanyRequest,
):

    try:

        return (
            research_company_web(
                request.company_name
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# TOOL AGENT
# ============================================================

@app.post(
    "/agent"
)
def agent(
    request: AgentRequest,
):

    try:

        return run_agent(
            request.message
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# START WORKFLOW
# ============================================================

@app.post(
    "/workflow"
)
def start_workflow(
    request: WorkflowRequest,
):

    try:

        return (
            run_company_workflow(

                objective=
                    request.objective,

                company_name=
                    request.company_name,

                recipient_email=
                    request.recipient_email,
            )
        )

    except Exception as error:

        print(
            "WORKFLOW ERROR:",
            repr(error),
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# WORKFLOW STATUS
# ============================================================

@app.get(
    "/workflow/{task_id}"
)
def workflow_status(
    task_id: int,
):

    try:

        thread_id = (
            f"task-{task_id}"
        )

        result = (
            get_company_workflow_status(
                thread_id
            )
        )

        if not result.get(
            "found"
        ):

            raise HTTPException(
                status_code=404,

                detail=(
                    f"Workflow task "
                    f"{task_id} "
                    "was not found."
                ),
            )

        return result

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# APPROVE / REJECT
# ============================================================

@app.post(
    "/workflow/{task_id}/decision"
)
def workflow_decision(
    task_id: int,
    request: ApprovalDecisionRequest,
):

    try:

        thread_id = (
            f"task-{task_id}"
        )

        return (
            resume_company_workflow(

                thread_id=
                    thread_id,

                decision=
                    request.decision,

                comment=
                    request.comment,
            )
        )

    except Exception as error:

        print(
            "WORKFLOW DECISION ERROR:",
            repr(error),
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# EMAIL DRAFT REVIEW
# ============================================================

@app.get(
    "/email-drafts/{draft_id}"
)
def email_draft_review(
    draft_id: int,
):

    try:

        result = (
            get_email_draft(
                draft_id
            )
        )

        if not result.get(
            "success"
        ):

            raise HTTPException(
                status_code=500,

                detail=result.get(
                    "error",
                    "Could not retrieve email draft.",
                ),
            )

        if not result.get(
            "found"
        ):

            raise HTTPException(
                status_code=404,

                detail=(
                    f"Email draft "
                    f"{draft_id} "
                    "was not found."
                ),
            )

        return result

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# KNOWLEDGE UPLOAD
# ============================================================

@app.post(
    "/knowledge/upload"
)
async def upload_knowledge_document(
    file: UploadFile = File(...),
):

    try:

        if not file.filename:

            raise HTTPException(
                status_code=400,

                detail=(
                    "Uploaded file has "
                    "no filename."
                ),
            )

        safe_filename = (
            Path(
                file.filename
            ).name
        )

        extension = (
            Path(
                safe_filename
            )
            .suffix
            .lower()
        )

        allowed_extensions = {
            ".pdf",
            ".txt",
            ".md",
        }

        if (
            extension
            not in
            allowed_extensions
        ):

            raise HTTPException(
                status_code=400,

                detail=(
                    "Supported file types are "
                    "PDF, TXT and Markdown."
                ),
            )

        upload_directory = (
            Path(
                "knowledge"
            )
            /
            "uploads"
        )

        upload_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            upload_directory
            /
            safe_filename
        )

        contents = (
            await file.read()
        )

        max_size = (
            10
            *
            1024
            *
            1024
        )

        if not contents:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        if (
            len(contents)
            >
            max_size
        ):

            raise HTTPException(
                status_code=400,

                detail=(
                    "File exceeds "
                    "the 10 MB limit."
                ),
            )

        destination.write_bytes(
            contents
        )

        result = (
            ingest_document(
                str(
                    destination
                )
            )
        )

        if not result.get(
            "success"
        ):

            raise HTTPException(
                status_code=500,

                detail=result.get(
                    "error",
                    "Document indexing failed.",
                ),
            )

        return {

            "message":
                (
                    "Document uploaded and "
                    "indexed successfully."
                ),

            **result,
        }

    except HTTPException:

        raise

    except Exception as error:

        print(
            "KNOWLEDGE UPLOAD ERROR:",
            repr(error),
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

    finally:

        await file.close()


# ============================================================
# KNOWLEDGE LIST
# ============================================================

@app.get(
    "/knowledge"
)
def knowledge_documents():

    result = (
        list_knowledge_documents()
    )

    if not result.get(
        "success"
    ):

        raise HTTPException(
            status_code=500,

            detail=result.get(
                "error",
                "Could not list documents.",
            ),
        )

    return result


# ============================================================
# KNOWLEDGE SEARCH
# ============================================================

@app.post(
    "/knowledge/search"
)
def knowledge_search(
    request: KnowledgeSearchRequest,
):

    result = (
        semantic_search(

            query=
                request.query,

            limit=
                request.limit,
        )
    )

    if not result.get(
        "success"
    ):

        raise HTTPException(
            status_code=500,

            detail=result.get(
                "error",
                "Semantic search failed.",
            ),
        )

    return result


# ============================================================
# KNOWLEDGE DELETE
# ============================================================

@app.delete(
    "/knowledge/{document_id}"
)
def remove_knowledge_document(
    document_id: int,
):

    result = (
        delete_knowledge_document(
            document_id
        )
    )

    if not result.get(
        "success"
    ):

        raise HTTPException(
            status_code=404,

            detail=result.get(
                "error",
                "Knowledge document not found.",
            ),
        )

    return result


# ============================================================
# OBSERVABILITY SUMMARY
# ============================================================

@app.get(
    "/observability/summary"
)
def observability_summary():

    try:

        return (
            get_observability_summary()
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# OBSERVABILITY EVENTS
# ============================================================

@app.get(
    "/observability/events"
)
def observability_events(

    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
):

    try:

        events = (
            get_recent_events(
                limit=limit
            )
        )

        return {

            "count":
                len(events),

            "limit":
                limit,

            "events":
                events,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# ONE TASK TRACE
# ============================================================

@app.get(
    "/observability/tasks/{task_id}"
)
def observability_task_trace(
    task_id: int,
):

    try:

        trace = (
            get_task_trace(
                task_id
            )
        )

        if not trace.get(
            "found"
        ):

            raise HTTPException(
                status_code=404,

                detail=(
                    "No observability "
                    f"events found for task "
                    f"{task_id}."
                ),
            )

        return trace

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )