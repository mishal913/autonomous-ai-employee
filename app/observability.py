import json
import threading
import time

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


LOG_DIRECTORY = Path("logs")
LOG_FILE = LOG_DIRECTORY / "agent_events.jsonl"

_log_lock = threading.Lock()


# ============================================================
# BASIC HELPERS
# ============================================================

def ensure_log_directory() -> None:
    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


def utc_timestamp() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def make_json_safe(value):
    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            make_json_safe(item)
            for item in value
        ]

    return str(value)


# ============================================================
# EVENT WRITING
# ============================================================

def log_event(
    event_type: str,
    data: dict | None = None,
) -> dict:
    ensure_log_directory()

    event = {
        "timestamp": utc_timestamp(),
        "event_type": event_type,
        "data": make_json_safe(
            data or {}
        ),
    }

    line = json.dumps(
        event,
        ensure_ascii=False,
    )

    with _log_lock:
        with LOG_FILE.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                line + "\n"
            )

    return event


# ============================================================
# OPERATION TIMER
# ============================================================

@contextmanager
def track_operation(
    operation_name: str,
    metadata: dict | None = None,
):
    metadata = metadata or {}

    start_time = time.perf_counter()

    log_event(
        "operation_started",
        {
            "operation": operation_name,
            **metadata,
        },
    )

    try:
        yield

    except Exception as error:
        duration_ms = (
            time.perf_counter()
            - start_time
        ) * 1000

        log_event(
            "operation_failed",
            {
                "operation": operation_name,
                "duration_ms": round(
                    duration_ms,
                    2,
                ),
                "error_type": type(error).__name__,
                "error": str(error),
                **metadata,
            },
        )

        raise

    else:
        duration_ms = (
            time.perf_counter()
            - start_time
        ) * 1000

        log_event(
            "operation_completed",
            {
                "operation": operation_name,
                "duration_ms": round(
                    duration_ms,
                    2,
                ),
                **metadata,
            },
        )


# ============================================================
# EVENT READING
# ============================================================

def read_events() -> list[dict]:
    if not LOG_FILE.exists():
        return []

    events = []

    with LOG_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(event, dict):
                events.append(event)

    return events


def get_recent_events(
    limit: int = 50,
) -> list[dict]:
    limit = max(
        1,
        min(int(limit), 500),
    )

    events = read_events()

    return events[-limit:]


def get_task_events(
    task_id: int,
) -> list[dict]:
    result = []

    for event in read_events():
        data = event.get(
            "data",
            {},
        )

        try:
            event_task_id = int(
                data.get("task_id")
            )
        except (TypeError, ValueError):
            continue

        if event_task_id == int(task_id):
            result.append(event)

    return result


# ============================================================
# SUMMARY
# ============================================================

def summarize_operations(
    events: list[dict],
) -> dict:
    started = defaultdict(int)
    completed = defaultdict(int)
    failures = defaultdict(int)
    durations = defaultdict(list)

    for event in events:
        event_type = event.get(
            "event_type"
        )

        data = event.get(
            "data",
            {},
        )

        operation = data.get(
            "operation"
        )

        if not operation:
            continue

        if event_type == "operation_started":
            started[operation] += 1

        elif event_type == "operation_completed":
            completed[operation] += 1

            value = data.get(
                "duration_ms"
            )

            if value is not None:
                try:
                    durations[operation].append(
                        float(value)
                    )
                except (TypeError, ValueError):
                    pass

        elif event_type == "operation_failed":
            failures[operation] += 1

    names = set(started)
    names.update(completed)
    names.update(failures)

    result = {}

    for name in sorted(names):
        values = durations[name]

        result[name] = {
            "runs": started[name],
            "completed": completed[name],
            "failures": failures[name],
            "average_duration_ms": (
                round(mean(values), 2)
                if values
                else None
            ),
            "minimum_duration_ms": (
                round(min(values), 2)
                if values
                else None
            ),
            "maximum_duration_ms": (
                round(max(values), 2)
                if values
                else None
            ),
        }

    return result


def get_observability_summary() -> dict:
    events = read_events()

    event_counts = defaultdict(int)
    task_ids = set()

    for event in events:
        event_counts[
            event.get(
                "event_type",
                "unknown",
            )
        ] += 1

        data = event.get(
            "data",
            {},
        )

        try:
            task_ids.add(
                int(data.get("task_id"))
            )
        except (TypeError, ValueError):
            pass

    return {
        "log_file": str(LOG_FILE),
        "total_events": len(events),
        "tasks_observed": len(task_ids),
        "task_ids": sorted(task_ids),
        "event_counts": dict(event_counts),
        "operations": summarize_operations(events),
    }


# ============================================================
# LIVE WORKFLOW TRACE
# ============================================================

STEP_DEFINITIONS = [
    {
        "step": 1,
        "key": "memory",
        "label": "Business memory",
        "nodes": {"check_memory"},
        "operations": {"workflow_check_memory"},
    },
    {
        "step": 2,
        "key": "web_research",
        "label": "Live web research",
        "nodes": {"research"},
        "operations": {"workflow_web_research"},
    },
    {
        "step": 3,
        "key": "rag",
        "label": "Private knowledge retrieval",
        "nodes": {"retrieve_internal_knowledge"},
        "operations": {"workflow_rag_retrieval"},
    },
    {
        "step": 4,
        "key": "analysis",
        "label": "Mistral analysis",
        "nodes": {"analyze"},
        "operations": {"workflow_llm_analysis"},
    },
    {
        "step": 5,
        "key": "scoring",
        "label": "Lead scoring",
        "nodes": {"score"},
        "operations": {"workflow_lead_scoring"},
    },
    {
        "step": 6,
        "key": "draft",
        "label": "Lead save and outreach draft",
        "nodes": {
            "draft_email",
            "save_lead",
            "save_email",
        },
        "operations": {
            "workflow_email_drafting",
            "workflow_save_lead",
            "workflow_save_email_draft",
        },
    },
    {
        "step": 7,
        "key": "approval",
        "label": "Human approval",
        "nodes": {
            "approval",
            "approved_action",
            "rejected_action",
        },
        "operations": {
            "workflow_mark_email_approved",
            "workflow_mark_email_rejected",
        },
    },
    {
        "step": 8,
        "key": "gmail",
        "label": "Gmail action",
        "nodes": {"send_email", "complete"},
        "operations": {
            "workflow_gmail_send",
            "workflow_complete_task",
        },
    },
]


NODE_TO_STEP = {}
for definition in STEP_DEFINITIONS:
    for node in definition["nodes"]:
        NODE_TO_STEP[node] = definition["step"]


OPERATION_TO_STEP = {}
for definition in STEP_DEFINITIONS:
    for operation in definition["operations"]:
        OPERATION_TO_STEP[operation] = definition["step"]


def _new_steps() -> list[dict]:
    return [
        {
            "step": definition["step"],
            "key": definition["key"],
            "label": definition["label"],
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "details": {},
        }
        for definition in STEP_DEFINITIONS
    ]


def _step_by_number(
    steps: list[dict],
    number: int,
) -> dict:
    return steps[number - 1]


def _set_step_started(
    step: dict,
    timestamp: str | None,
):
    if not step.get("started_at"):
        step["started_at"] = timestamp

    if step.get("status") == "pending":
        step["status"] = "running"


def _set_step_completed(
    step: dict,
    timestamp: str | None,
):
    step["status"] = "completed"
    step["completed_at"] = timestamp


def get_task_trace(
    task_id: int,
) -> dict:
    events = get_task_events(
        task_id
    )

    if not events:
        return {
            "found": False,
            "task_id": task_id,
            "status": "queued",
            "current_step": 0,
            "current_node": None,
            "steps": _new_steps(),
        }

    steps = _new_steps()

    status = "running"
    current_node = None
    current_step = 0

    company_name = None
    thread_id = None

    memory_result = {
        "existing_memory_found": None,
    }

    web_research = {
        "query": None,
        "results_count": None,
        "sources": [],
    }

    rag_sources = []

    score_breakdown = {
        "industry_fit": None,
        "company_size_fit": None,
        "ai_need": None,
        "growth_signal": None,
        "contact_potential": None,
    }

    recommended_services = []

    lead_score = None
    rating = None
    draft_id = None
    approval_status = None
    email_send_status = None
    errors = []

    operation_start_times = {}

    for event in events:
        timestamp = event.get(
            "timestamp"
        )

        event_type = event.get(
            "event_type",
            "",
        )

        data = event.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            continue

        if not company_name and data.get("company_name"):
            company_name = data.get("company_name")

        if not thread_id and data.get("thread_id"):
            thread_id = data.get("thread_id")

        if event_type == "workflow_created":
            status = "queued"

        if event_type == "workflow_started":
            status = "running"

        if event_type == "workflow_node_started":
            node = data.get("node")
            step_number = NODE_TO_STEP.get(node)

            if step_number:
                current_node = node
                current_step = step_number

                step = _step_by_number(
                    steps,
                    step_number,
                )

                _set_step_started(
                    step,
                    timestamp,
                )

        if event_type == "workflow_node_completed":
            node = data.get("node")
            step_number = NODE_TO_STEP.get(node)

            if step_number:
                step = _step_by_number(
                    steps,
                    step_number,
                )

                # Step 6 and 7 contain multiple internal nodes, so
                # only mark them completed at their terminal node.
                terminal = True

                if step_number == 6:
                    terminal = node in {
                        "save_email",
                        "save_lead",
                    }

                if step_number == 7:
                    terminal = node in {
                        "approved_action",
                        "rejected_action",
                    }

                if terminal:
                    _set_step_completed(
                        step,
                        timestamp,
                    )

            if node == "check_memory":
                memory_result[
                    "existing_memory_found"
                ] = data.get(
                    "existing_memory_found"
                )

        if event_type == "operation_started":
            operation = data.get("operation")
            step_number = OPERATION_TO_STEP.get(operation)

            if step_number:
                _set_step_started(
                    _step_by_number(
                        steps,
                        step_number,
                    ),
                    timestamp,
                )

            if operation:
                operation_start_times[operation] = timestamp

        if event_type == "operation_completed":
            operation = data.get("operation")
            step_number = OPERATION_TO_STEP.get(operation)

            if step_number:
                step = _step_by_number(
                    steps,
                    step_number,
                )

                duration = data.get(
                    "duration_ms"
                )

                if duration is not None:
                    try:
                        existing = step.get(
                            "duration_ms"
                        ) or 0.0

                        step["duration_ms"] = round(
                            existing + float(duration),
                            2,
                        )
                    except (TypeError, ValueError):
                        pass

        if event_type == "operation_failed":
            operation = data.get("operation")
            step_number = OPERATION_TO_STEP.get(operation)

            if step_number:
                _step_by_number(
                    steps,
                    step_number,
                )["status"] = "failed"

            errors.append(
                {
                    "timestamp": timestamp,
                    "operation": operation,
                    "error_type": data.get("error_type"),
                    "error": data.get("error"),
                }
            )

        if event_type == "web_research_completed":
            web_research = {
                "query": data.get("query"),
                "results_count": data.get("results_count"),
                "sources": data.get("sources", []),
            }

        if event_type == "workflow_internal_knowledge_retrieved":
            rag_sources = data.get(
                "sources",
                [],
            )

        if event_type == "llm_analysis_validated":
            scores = data.get(
                "scores",
                {},
            )

            if isinstance(scores, dict):
                score_breakdown.update(scores)

            services = data.get(
                "recommended_services",
                [],
            )

            if isinstance(services, list):
                recommended_services = services

        if event_type == "lead_scored":
            lead_score = data.get(
                "lead_score"
            )

            rating = data.get(
                "rating"
            )

            scores = data.get(
                "scores",
                {},
            )

            if isinstance(scores, dict):
                score_breakdown.update(scores)

        if event_type == "email_draft_saved":
            draft_id = data.get(
                "draft_id"
            )

        if event_type == "workflow_awaiting_human_approval":
            status = "awaiting_approval"
            current_step = 7
            current_node = "approval"

            approval_step = _step_by_number(
                steps,
                7,
            )

            _set_step_started(
                approval_step,
                timestamp,
            )

        if event_type == "human_approval_decision":
            approval_status = data.get(
                "decision"
            )

        if event_type == "gmail_send_completed":
            email_send_status = "sent"

        if event_type == "gmail_send_failed":
            email_send_status = "failed"

        if event_type == "workflow_completed":
            status = "completed"

            # Mark every step before the terminal position as complete.
            if email_send_status == "sent":
                current_step = 8
                current_node = "complete"

                for step in steps:
                    if step["status"] != "skipped":
                        step["status"] = "completed"

            elif approval_status in {"rejected", "reject"}:
                current_step = 7
                current_node = "rejected_action"
                _step_by_number(steps, 8)["status"] = "skipped"

        if event_type in {
            "workflow_failed",
            "workflow_resume_failed",
        }:
            status = "failed"

            errors.append(
                {
                    "timestamp": timestamp,
                    "event_type": event_type,
                    "error_type": data.get("error_type"),
                    "error": data.get("error"),
                }
            )

    if status == "completed" and lead_score is not None:
        try:
            low_score = float(lead_score) < 60
        except (TypeError, ValueError):
            low_score = False

        if low_score:
            current_step = 5
            current_node = "complete"

            for step_number in (6, 7, 8):
                _step_by_number(
                    steps,
                    step_number,
                )["status"] = "skipped"

    if status == "running" and current_step:
        for step in steps:
            if step["step"] < current_step and step["status"] == "pending":
                step["status"] = "completed"

    return {
        "found": True,
        "task_id": task_id,
        "thread_id": thread_id,
        "company_name": company_name,
        "status": status,
        "current_step": current_step,
        "current_node": current_node,
        "steps": steps,
        "memory": memory_result,
        "web_research": web_research,
        "rag_sources": rag_sources,
        "score_breakdown": score_breakdown,
        "lead_score": lead_score,
        "rating": rating,
        "recommended_services": recommended_services,
        "draft_id": draft_id,
        "approval_status": approval_status,
        "email_send_status": email_send_status,
        "errors": errors,
        "event_count": len(events),
        "operations": summarize_operations(events),
        "events": events,
    }
