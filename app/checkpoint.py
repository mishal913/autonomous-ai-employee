import os

from dotenv import load_dotenv

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from langgraph.checkpoint.postgres import PostgresSaver


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


DB_HOST = os.getenv(
    "DB_HOST",
    "localhost",
)

DB_PORT = int(
    os.getenv(
        "DB_PORT",
        "5432",
    )
)

DB_NAME = os.getenv(
    "DB_NAME",
    "ai_employee",
)

DB_USER = os.getenv(
    "DB_USER",
    "ai_employee_user",
)

DB_PASSWORD = os.getenv(
    "DB_PASSWORD",
)


if not DB_PASSWORD:
    raise RuntimeError(
        "DB_PASSWORD was not found in .env"
    )


# ============================================================
# POSTGRES CONNECTION INFORMATION
# ============================================================

DB_CONNINFO = make_conninfo(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)


# ============================================================
# CONNECTION POOL
# ============================================================

checkpoint_pool = ConnectionPool(
    conninfo=DB_CONNINFO,

    min_size=1,
    max_size=5,

    kwargs={
        "autocommit": True,
        "row_factory": dict_row,
    },
)


# ============================================================
# LANGGRAPH POSTGRES CHECKPOINTER
# ============================================================

checkpointer = PostgresSaver(
    checkpoint_pool
)


# ============================================================
# FIRST-TIME SETUP
# ============================================================

def setup_checkpointer():
    """
    Create LangGraph checkpoint tables
    in PostgreSQL.

    Safe to run again after initial setup.
    """

    checkpointer.setup()