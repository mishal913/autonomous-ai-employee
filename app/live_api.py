from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.live_runner import (
    is_background_workflow_running,
    start_background_workflow,
)
from app.observability import get_task_trace
from app.tools import (
    get_agent_task,
    get_email_draft,
)
from app.workflow import get_company_workflow_status


router = APIRouter(
    tags=["Live Workflow"],
)


class LiveWorkflowRequest(BaseModel):
    objective: str = Field(
        min_length=3,
        max_length=4000,
    )

    company_name: str = Field(
        min_length=1,
        max_length=300,
    )

    recipient_email: str = Field(
        min_length=3,
        max_length=320,
    )


@router.post(
    "/workflow/start",
)
def start_live_workflow(
    request: LiveWorkflowRequest,
):
    """
    Start LangGraph in the background and return task_id immediately.
    """

    try:
        return start_background_workflow(
            objective=request.objective,
            company_name=request.company_name,
            recipient_email=request.recipient_email,
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@router.get(
    "/workflow/{task_id}/live",
)
def get_live_workflow(
    task_id: int,
):
    """
    Return the latest real execution state for one workflow.

    The frontend can poll this every ~1 second.
    """

    task = get_agent_task(
        task_id
    )

    if not task.get("success"):
        raise HTTPException(
            status_code=500,
            detail=task.get(
                "error",
                "Could not read agent task.",
            ),
        )

    if not task.get("found"):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Agent task {task_id} was not found."
            ),
        )

    thread_id = f"task-{task_id}"

    trace = get_task_trace(
        task_id
    )

    graph_state = {
        "found": False,
    }

    try:
        graph_state = get_company_workflow_status(
            thread_id
        )
    except Exception:
        # During the first milliseconds the graph may not have
        # produced its first checkpoint yet. The trace still gives
        # us queued/running state.
        pass

    draft_id = (
        graph_state.get("draft_id")
        or
        trace.get("draft_id")
    )

    email_draft = None

    if draft_id:
        draft_result = get_email_draft(
            int(draft_id)
        )

        if (
            draft_result.get("success")
            and
            draft_result.get("found")
        ):
            email_draft = draft_result

    status = (
        task.get("status")
        or
        trace.get("status")
        or
        graph_state.get("status")
        or
        "running"
    )

    # AgentTask is authoritative for awaiting approval/completion.
    if task.get("status") in {
        "queued",
        "running",
        "awaiting_approval",
        "completed",
        "failed",
    }:
        status = task.get("status")

    return {
        "success": True,
        "task_id": task_id,
        "thread_id": thread_id,
        "status": status,
        "background_running": is_background_workflow_running(
            task_id
        ),
        "task": task,
        "trace": trace,
        "workflow": graph_state,
        "email_draft": email_draft,
    }
