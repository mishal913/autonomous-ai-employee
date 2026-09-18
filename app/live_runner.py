from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from app.observability import log_event
from app.workflow import (
    create_company_workflow_task,
    execute_company_workflow_task,
)


# ============================================================
# SIMPLE IN-PROCESS BACKGROUND EXECUTOR
# ============================================================
#
# Good for local development and this portfolio project.
# Later, for production deployment, replace this with a durable
# worker queue such as Celery/RQ/Dramatiq if needed.
# ============================================================

_executor = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="ai-employee-workflow",
)

_running_futures = {}
_running_lock = Lock()


def _remove_finished_task(
    task_id: int,
):
    with _running_lock:
        _running_futures.pop(
            task_id,
            None,
        )


def _execute_in_background(
    created: dict,
):
    task_id = created["task_id"]

    try:
        return execute_company_workflow_task(
            task_id=task_id,
            thread_id=created["thread_id"],
            objective=created["objective"],
            company_name=created["company_name"],
            recipient_email=created["recipient_email"],
        )

    except Exception as error:
        # execute_company_workflow_task already logs the workflow
        # failure and updates AgentTask. This event only records the
        # background-runner boundary.
        log_event(
            "background_workflow_failed",
            {
                "task_id": task_id,
                "thread_id": created["thread_id"],
                "company_name": created["company_name"],
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )

        raise


def start_background_workflow(
    objective: str,
    company_name: str,
    recipient_email: str,
) -> dict:
    """
    Create a workflow task immediately and execute LangGraph in
    a background worker thread.

    The caller gets task_id before Tavily/RAG/Mistral start, so
    the frontend can poll the live endpoint while work continues.
    """

    created = create_company_workflow_task(
        objective=objective,
        company_name=company_name,
        recipient_email=recipient_email,
    )

    task_id = created["task_id"]

    future = _executor.submit(
        _execute_in_background,
        created,
    )

    with _running_lock:
        _running_futures[
            task_id
        ] = future

    future.add_done_callback(
        lambda _future: _remove_finished_task(
            task_id
        )
    )

    return {
        "success": True,
        "task_id": task_id,
        "thread_id": created["thread_id"],
        "company_name": created["company_name"],
        "recipient_email": created["recipient_email"],
        "status": "queued",
        "message": (
            "Workflow accepted. Poll the live status endpoint "
            "using this task_id."
        ),
    }


def is_background_workflow_running(
    task_id: int,
) -> bool:
    with _running_lock:
        future = _running_futures.get(
            task_id
        )

    if future is None:
        return False

    return not future.done()
