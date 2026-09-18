from datetime import datetime

from pgvector.sqlalchemy import Vector

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ============================================================
# COMPANY
# ============================================================

class Company(Base):

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    profile: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ============================================================
# LEAD
# ============================================================

class Lead(Base):

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    company_name: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    lead_score: Mapped[int] = mapped_column(
        Integer,
    )

    rating: Mapped[str] = mapped_column(
        String(100),
    )

    research_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ============================================================
# EMAIL DRAFT
# ============================================================

class EmailDraft(Base):

    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    company_name: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    recipient_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    subject: Mapped[str] = mapped_column(
        String(500),
    )

    body: Mapped[str] = mapped_column(
        Text,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
    )

    gmail_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    gmail_thread_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    send_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ============================================================
# AGENT TASK
# ============================================================

class AgentTask(Base):

    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    objective: Mapped[str] = mapped_column(
        Text,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )

    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


# ============================================================
# RAG KNOWLEDGE DOCUMENT
# ============================================================

class KnowledgeDocument(Base):

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    filename: Mapped[str] = mapped_column(
        String(500),
        index=True,
    )

    source_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    document_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ============================================================
# RAG DOCUMENT CHUNK
# ============================================================

class DocumentChunk(Base):

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey(
            "knowledge_documents.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
    )

    content: Mapped[str] = mapped_column(
        Text,
    )

    # all-MiniLM-L6-v2 produces exactly
    # 384 floating point values.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )