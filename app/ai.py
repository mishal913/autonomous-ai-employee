import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from app.tools import (
    # Business tools
    get_company_profile,
    search_web,
    calculate_lead_score,
    draft_outreach_email,

    # Lead memory
    save_lead,
    get_saved_lead,

    # Email memory
    save_email_draft,

    # Task infrastructure
    create_agent_task,
    complete_agent_task,
    fail_agent_task,
)


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)


XKIRO_BASE_URL = os.getenv(
    "XKIRO_BASE_URL",
    "https://api.xkiro.com/v1",
)


MODEL = os.getenv(
    "XKIRO_MODEL",
    "mistralai/mistral-large-2512",
)


# ============================================================
# 2. XKIRO CLIENT
# ============================================================

def get_client() -> OpenAI:
    """
    Create an OpenAI-compatible client
    connected to xKiro.
    """

    api_key = os.getenv("XKIRO_API_KEY")

    if not api_key:
        raise RuntimeError(
            f"XKIRO_API_KEY not found in {ENV_PATH}"
        )

    return OpenAI(
        api_key=api_key,
        base_url=XKIRO_BASE_URL,
        timeout=120.0,
        max_retries=2,
    )


# ============================================================
# 3. SIMPLE CHAT
# ============================================================

def ask_ai(message: str) -> str:
    """
    Simple model call.

    No tools.
    No database memory.
    """

    client = get_client()

    response = client.chat.completions.create(
        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI business research employee. "
                    "Answer clearly, accurately, and professionally. "
                    "Always answer in English unless another "
                    "language is explicitly requested."
                ),
            },

            {
                "role": "user",
                "content": message,
            },
        ],

        max_tokens=800,
    )

    return (
        response
        .choices[0]
        .message
        .content
        or ""
    )


# ============================================================
# 4. STRUCTURED COMPANY RESEARCH
# ============================================================

class CompanyResearch(BaseModel):

    company_name: str

    industry: str

    location: str

    summary: str

    lead_score: int = Field(
        ge=0,
        le=100,
    )

    recommended_action: str


# ============================================================
# 5. JSON PARSER
# ============================================================

def parse_json_response(
    content: str,
) -> dict:
    """
    Extract valid JSON from a model response.
    """

    content = content.strip()

    content = content.replace(
        "```json",
        "",
    )

    content = content.replace(
        "```",
        "",
    )

    content = content.strip()

    start = content.find("{")
    end = content.rfind("}")

    if start == -1 or end == -1:

        raise ValueError(
            "No JSON object found in model response."
        )

    json_text = content[
        start:end + 1
    ]

    return json.loads(
        json_text
    )


# ============================================================
# 6. STRUCTURED MODEL-ONLY COMPANY RESEARCH
# ============================================================

def research_company(
    company_name: str,
) -> CompanyResearch:
    """
    Analyze a company using model knowledge.

    This function does NOT perform live web search.
    """

    client = get_client()

    response = client.chat.completions.create(
        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are a business research analyst. "
                    "Always respond in English. "
                    "Return ONLY one valid JSON object. "
                    "Do not use markdown. "
                    "Do not include text outside the JSON. "
                    "Use exactly these fields: "
                    "company_name, industry, location, summary, "
                    "lead_score, recommended_action. "
                    "lead_score must be an integer from 0 to 100."
                ),
            },

            {
                "role": "user",
                "content": (
                    f"Analyze the company {company_name}. "
                    "Use your existing model knowledge only."
                ),
            },
        ],

        response_format={
            "type": "json_object"
        },

        max_tokens=500,
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:

        raise RuntimeError(
            "Model returned an empty response."
        )

    # --------------------------------------------------------
    # Try parsing JSON normally
    # --------------------------------------------------------

    try:

        data = parse_json_response(
            content
        )

    except Exception:

        # ----------------------------------------------------
        # Repair malformed JSON automatically
        # ----------------------------------------------------

        repair_response = (
            client
            .chat
            .completions
            .create(
                model=MODEL,

                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Repair malformed JSON. "
                            "Return ONLY valid JSON. "
                            "No markdown. "
                            "No explanation."
                        ),
                    },

                    {
                        "role": "user",
                        "content": content,
                    },
                ],

                response_format={
                    "type": "json_object"
                },

                max_tokens=500,
            )
        )

        repaired_content = (
            repair_response
            .choices[0]
            .message
            .content
        )

        if not repaired_content:

            raise RuntimeError(
                "JSON repair failed."
            )

        data = parse_json_response(
            repaired_content
        )

    return CompanyResearch(
        **data
    )


# ============================================================
# 7. TOOL DEFINITIONS
# ============================================================

TOOLS = [

    # ========================================================
    # TOOL 1 — INTERNAL COMPANY PROFILE
    # ========================================================

    {
        "type": "function",

        "function": {

            "name": "get_company_profile",

            "description": (
                "Retrieve company information from the "
                "internal company database."
            ),

            "parameters": {

                "type": "object",

                "properties": {

                    "company_name": {
                        "type": "string",
                    }
                },

                "required": [
                    "company_name"
                ],

                "additionalProperties": False,
            },
        },
    },


    # ========================================================
    # TOOL 2 — LIVE WEB SEARCH
    # ========================================================

    {
        "type": "function",

        "function": {

            "name": "search_web",

            "description": (
                "Search the live web for current public "
                "information such as company news, products, "
                "employees, funding, AI activity, technology, "
                "growth, competitors, or recent developments."
            ),

            "parameters": {

                "type": "object",

                "properties": {

                    "query": {
                        "type": "string",
                    },

                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                    },
                },

                "required": [
                    "query"
                ],

                "additionalProperties": False,
            },
        },
    },


    # ========================================================
    # TOOL 3 — LEAD SCORING
    # ========================================================

    {
        "type": "function",

        "function": {

            "name": "calculate_lead_score",

            "description": (
                "Calculate a transparent sales lead score "
                "after enough company evidence has been gathered. "
                "Each criterion is scored from 0 to 20."
            ),

            "parameters": {

                "type": "object",

                "properties": {

                    "industry_fit": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 20,
                    },

                    "company_size_fit": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 20,
                    },

                    "ai_need": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 20,
                    },

                    "growth_signal": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 20,
                    },

                    "contact_potential": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 20,
                    },
                },

                "required": [
                    "industry_fit",
                    "company_size_fit",
                    "ai_need",
                    "growth_signal",
                    "contact_potential",
                ],

                "additionalProperties": False,
            },
        },
    },


    # ========================================================
    # TOOL 4 — CREATE EMAIL DRAFT
    # ========================================================

    {
        "type": "function",

        "function": {

            "name": "draft_outreach_email",

            "description": (
                "Prepare a personalized business outreach "
                "email draft after researching and scoring "
                "a company. This never sends email."
            ),

            "parameters": {

                "type": "object",

                "properties": {

                    "company_name": {
                        "type": "string",
                    },

                    "reason_for_contact": {
                        "type": "string",
                    },

                    "value_proposition": {
                        "type": "string",
                    },

                    "lead_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },

                "required": [
                    "company_name",
                    "reason_for_contact",
                    "value_proposition",
                    "lead_score",
                ],

                "additionalProperties": False,
            },
        },
    },


    # ========================================================
    # TOOL 5 — SAVE LEAD
    # ========================================================

    {
        "type": "function",

        "function": {

            "name": "save_lead",

            "description": (
                "Save a researched and scored lead into "
                "PostgreSQL persistent memory. "
                "Use this when the user asks to save, "
                "store, or remember the lead."
            ),

            "parameters": {

                "type": "object",

                "properties": {

                    "company_name": {
                        "type": "string",
                    },

                    "lead_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },

                    "rating": {
                        "type": "string",
                    },

                    "research_summary": {
                        "type": "string",
                    },
                },

                "required": [
                    "company_name",
                    "lead_score",
                    "rating",
                    "research_summary",
                ],

                "additionalProperties": False,
            },
        },
    },


    # ========================================================
    # TOOL 6 — GET SAVED LEAD
    # ========================================================

    {
        "type": "function",

        "function": {

            "name": "get_saved_lead",

            "description": (
                "Retrieve previously saved company lead "
                "information from PostgreSQL memory. "
                "Use when the user asks what we already know "
                "about a company."
            ),

            "parameters": {

                "type": "object",

                "properties": {

                    "company_name": {
                        "type": "string",
                    }
                },

                "required": [
                    "company_name"
                ],

                "additionalProperties": False,
            },
        },
    },


    # ========================================================
    # TOOL 7 — SAVE EMAIL DRAFT
    # ========================================================

    {
        "type": "function",

        "function": {

            "name": "save_email_draft",

            "description": (
                "Save a generated outreach email draft "
                "into PostgreSQL persistent memory. "
                "This saves the draft only and never sends email."
            ),

            "parameters": {

                "type": "object",

                "properties": {

                    "company_name": {
                        "type": "string",
                    },

                    "subject": {
                        "type": "string",
                    },

                    "body": {
                        "type": "string",
                    },
                },

                "required": [
                    "company_name",
                    "subject",
                    "body",
                ],

                "additionalProperties": False,
            },
        },
    },
]


# ============================================================
# 8. AUTONOMOUS AI EMPLOYEE
# ============================================================

def run_agent(
    message: str,
) -> dict:
    """
    Main autonomous AI Employee.

    Task tracking happens automatically.

    The LLM does NOT decide whether task history
    should be stored.
    """

    client = get_client()


    # ========================================================
    # CREATE TASK AUTOMATICALLY
    # ========================================================

    task_info = create_agent_task(
        objective=message
    )

    if not task_info.get(
        "success"
    ):

        raise RuntimeError(
            f"Could not create PostgreSQL task: "
            f"{task_info}"
        )


    task_id = task_info[
        "task_id"
    ]


    print(
        f"\nCreated PostgreSQL task #{task_id}"
    )


    try:

        # ====================================================
        # CONVERSATION / AGENT STATE
        # ====================================================

        messages = [

            {
                "role": "system",

                "content": (
                    "You are an autonomous AI business "
                    "development employee. "

                    "Your responsibilities include researching "
                    "companies, qualifying sales leads, calculating "
                    "lead scores, preparing outreach drafts, and "
                    "using persistent business memory. "

                    "Use search_web whenever current or external "
                    "information is required. "

                    "Use get_company_profile when internal company "
                    "information is explicitly requested or useful. "

                    "Before calculating a lead score, gather enough "
                    "evidence about the company. "

                    "When the user asks whether a company is a good "
                    "prospect, use calculate_lead_score. "

                    "If outreach is requested, research and score "
                    "the company before calling draft_outreach_email. "

                    "Whenever an outreach draft is created, save it "
                    "using save_email_draft so it remains available "
                    "in PostgreSQL. "

                    "Use save_lead when the user asks to save, store, "
                    "or remember a researched lead. "

                    "Use get_saved_lead when the user asks what we "
                    "already know about a company from saved memory. "

                    "Never claim an email has been sent. "
                    "You currently only create and save drafts. "

                    "Never invent tool results. "

                    "Never claim to have searched the web unless "
                    "search_web was actually called. "

                    "Always answer in English unless the user "
                    "explicitly requests another language."
                ),
            },

            {
                "role": "user",
                "content": message,
            },
        ]


        # ====================================================
        # AGENT LOOP
        # ====================================================

        for step in range(10):

            print(
                f"\n========== "
                f"AGENT STEP {step + 1} "
                f"=========="
            )


            response = (
                client
                .chat
                .completions
                .create(
                    model=MODEL,

                    messages=messages,

                    tools=TOOLS,

                    tool_choice="auto",

                    max_tokens=1000,
                )
            )


            assistant_message = (
                response
                .choices[0]
                .message
            )


            # Save the model's decision/message
            # in temporary conversation state.

            messages.append(
                assistant_message.model_dump(
                    exclude_none=True
                )
            )


            # =================================================
            # NO TOOL CALL = TASK FINISHED
            # =================================================

            if not assistant_message.tool_calls:

                final_answer = (
                    assistant_message.content
                    or ""
                )


                # ---------------------------------------------
                # MARK TASK COMPLETED
                # ---------------------------------------------

                completion_result = (
                    complete_agent_task(
                        task_id=task_id,
                        result=final_answer,
                    )
                )


                if not completion_result.get(
                    "success"
                ):

                    print(
                        "WARNING: Could not mark "
                        "task completed:",
                        completion_result
                    )


                print(
                    f"Task #{task_id} "
                    f"marked completed"
                )


                return {
                    "task_id": task_id,
                    "status": "completed",
                    "response": final_answer,
                }


            # =================================================
            # EXECUTE TOOL CALLS
            # =================================================

            for tool_call in (
                assistant_message.tool_calls
            ):

                tool_name = (
                    tool_call
                    .function
                    .name
                )


                print(
                    "AI chose tool:",
                    tool_name
                )


                # =============================================
                # PARSE TOOL ARGUMENTS
                # =============================================

                try:

                    raw_arguments = (
                        tool_call
                        .function
                        .arguments
                    )


                    if isinstance(
                        raw_arguments,
                        dict,
                    ):

                        arguments = (
                            raw_arguments
                        )

                    else:

                        arguments = (
                            json.loads(
                                raw_arguments
                                or "{}"
                            )
                        )


                except Exception as error:

                    tool_result = {

                        "success": False,

                        "error": (
                            "Invalid tool arguments: "
                            f"{str(error)}"
                        ),
                    }


                    messages.append(
                        {
                            "role": "tool",

                            "tool_call_id": (
                                tool_call.id
                            ),

                            "content": json.dumps(
                                tool_result
                            ),
                        }
                    )


                    continue


                # =============================================
                # TOOL 1 — INTERNAL COMPANY PROFILE
                # =============================================

                if (
                    tool_name
                    == "get_company_profile"
                ):

                    company_name = (
                        arguments.get(
                            "company_name"
                        )
                    )


                    print(
                        "Internal company lookup:",
                        company_name
                    )


                    tool_result = (
                        get_company_profile(
                            company_name
                        )
                    )


                # =============================================
                # TOOL 2 — WEB SEARCH
                # =============================================

                elif (
                    tool_name
                    == "search_web"
                ):

                    query = (
                        arguments.get(
                            "query",
                            ""
                        )
                    )


                    max_results = (
                        arguments.get(
                            "max_results",
                            5
                        )
                    )


                    print(
                        "Web search query:",
                        query
                    )


                    tool_result = (
                        search_web(
                            query=query,
                            max_results=max_results,
                        )
                    )


                # =============================================
                # TOOL 3 — LEAD SCORING
                # =============================================

                elif (
                    tool_name
                    == "calculate_lead_score"
                ):

                    print(
                        "Calculating lead score..."
                    )


                    tool_result = (
                        calculate_lead_score(

                            industry_fit=(
                                arguments.get(
                                    "industry_fit"
                                )
                            ),

                            company_size_fit=(
                                arguments.get(
                                    "company_size_fit"
                                )
                            ),

                            ai_need=(
                                arguments.get(
                                    "ai_need"
                                )
                            ),

                            growth_signal=(
                                arguments.get(
                                    "growth_signal"
                                )
                            ),

                            contact_potential=(
                                arguments.get(
                                    "contact_potential"
                                )
                            ),
                        )
                    )


                # =============================================
                # TOOL 4 — DRAFT OUTREACH EMAIL
                # =============================================

                elif (
                    tool_name
                    == "draft_outreach_email"
                ):

                    print(
                        "Preparing outreach email..."
                    )


                    tool_result = (
                        draft_outreach_email(

                            company_name=(
                                arguments.get(
                                    "company_name"
                                )
                            ),

                            reason_for_contact=(
                                arguments.get(
                                    "reason_for_contact"
                                )
                            ),

                            value_proposition=(
                                arguments.get(
                                    "value_proposition"
                                )
                            ),

                            lead_score=(
                                arguments.get(
                                    "lead_score"
                                )
                            ),
                        )
                    )


                # =============================================
                # TOOL 5 — SAVE LEAD TO POSTGRESQL
                # =============================================

                elif (
                    tool_name
                    == "save_lead"
                ):

                    print(
                        "Saving lead to PostgreSQL..."
                    )


                    tool_result = (
                        save_lead(

                            company_name=(
                                arguments.get(
                                    "company_name"
                                )
                            ),

                            lead_score=(
                                arguments.get(
                                    "lead_score"
                                )
                            ),

                            rating=(
                                arguments.get(
                                    "rating"
                                )
                            ),

                            research_summary=(
                                arguments.get(
                                    "research_summary"
                                )
                            ),
                        )
                    )


                # =============================================
                # TOOL 6 — READ LEAD FROM POSTGRESQL
                # =============================================

                elif (
                    tool_name
                    == "get_saved_lead"
                ):

                    print(
                        "Reading lead from PostgreSQL..."
                    )


                    tool_result = (
                        get_saved_lead(

                            company_name=(
                                arguments.get(
                                    "company_name"
                                )
                            )
                        )
                    )


                # =============================================
                # TOOL 7 — SAVE EMAIL DRAFT
                # =============================================

                elif (
                    tool_name
                    == "save_email_draft"
                ):

                    print(
                        "Saving email draft "
                        "to PostgreSQL..."
                    )


                    tool_result = (
                        save_email_draft(

                            company_name=(
                                arguments.get(
                                    "company_name"
                                )
                            ),

                            subject=(
                                arguments.get(
                                    "subject"
                                )
                            ),

                            body=(
                                arguments.get(
                                    "body"
                                )
                            ),
                        )
                    )


                # =============================================
                # UNKNOWN TOOL
                # =============================================

                else:

                    tool_result = {

                        "success": False,

                        "error": (
                            f"Unknown tool: "
                            f"{tool_name}"
                        ),
                    }


                print(
                    "Tool completed:",
                    tool_name
                )


                # =============================================
                # RETURN TOOL RESULT TO MODEL
                # =============================================

                messages.append(
                    {
                        "role": "tool",

                        "tool_call_id": (
                            tool_call.id
                        ),

                        "content": json.dumps(
                            tool_result
                        ),
                    }
                )


        # ====================================================
        # LOOP LIMIT REACHED
        # ====================================================

        raise RuntimeError(
            "Agent exceeded maximum "
            "number of tool-call steps."
        )


    # ========================================================
    # TASK FAILED
    # ========================================================

    except Exception as error:

        fail_result = fail_agent_task(
            task_id=task_id,
            error_message=str(error),
        )


        if not fail_result.get(
            "success"
        ):

            print(
                "WARNING: Could not mark "
                "task failed:",
                fail_result
            )


        print(
            f"Task #{task_id} "
            f"marked failed"
        )


        raise


# ============================================================
# 9. GUARANTEED LIVE WEB RESEARCH
# ============================================================

def research_company_web(
    company_name: str,
) -> str:
    """
    Always performs live web search.

    Unlike run_agent(), this function
    does not let the AI decide whether
    web search is necessary.
    """

    query = (
        f"{company_name} company industry "
        f"location products services employees "
        f"funding recent developments "
        f"AI technology news"
    )


    search_results = (
        search_web(
            query=query,
            max_results=5,
        )
    )


    if not search_results.get(
        "success"
    ):

        raise RuntimeError(
            search_results.get(
                "error",
                "Web search failed."
            )
        )


    client = get_client()


    response = (
        client
        .chat
        .completions
        .create(
            model=MODEL,

            messages=[

                {
                    "role": "system",

                    "content": (
                        "You are a professional business "
                        "research analyst. "

                        "Use the supplied web evidence "
                        "for current factual claims. "

                        "Analyze the company's industry, "
                        "location, products, company size, "
                        "recent developments, growth signals, "
                        "and AI/technology activity. "

                        "Then assess whether the company "
                        "could be a useful prospect for "
                        "AI consulting services. "

                        "Do not invent facts. "

                        "End with a Sources section containing "
                        "the most relevant URLs."
                    ),
                },

                {
                    "role": "user",

                    "content": (
                        f"Research company: "
                        f"{company_name}\n\n"

                        "WEB SEARCH RESULTS:\n"

                        + json.dumps(
                            search_results,
                            indent=2,
                        )
                    ),
                },
            ],

            max_tokens=1200,
        )
    )


    return (
        response
        .choices[0]
        .message
        .content
        or ""
    )