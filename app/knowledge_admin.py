from pathlib import Path

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import KnowledgeDocument, DocumentChunk
from app.rag import chunk_text, create_embedding


EDITABLE_EXTENSIONS = {".txt", ".md"}


def _document_path(document: KnowledgeDocument) -> Path:
    raw_path = str(getattr(document, "source_path", "") or "").strip()

    if not raw_path:
        raise RuntimeError(
            f"Knowledge document {document.id} has no source_path."
        )

    return Path(raw_path)


def _document_extension(document: KnowledgeDocument) -> str:
    filename = str(getattr(document, "filename", "") or "")
    suffix = Path(filename).suffix.lower()

    if suffix:
        return suffix

    return _document_path(document).suffix.lower()


def get_knowledge_document_content(document_id: int) -> dict:
    """Return editable text for TXT/MD knowledge documents.

    PDFs are intentionally not edited as plain text because doing so would
    make the stored source PDF and its pgvector representation disagree.
    """

    db = SessionLocal()

    try:
        document = db.get(KnowledgeDocument, document_id)

        if not document:
            return {
                "success": True,
                "found": False,
                "document_id": document_id,
            }

        extension = _document_extension(document)
        editable = extension in EDITABLE_EXTENSIONS

        content = None

        if editable:
            path = _document_path(document)

            if path.exists():
                content = path.read_text(encoding="utf-8")
            else:
                chunks = (
                    db.execute(
                        select(DocumentChunk)
                        .where(DocumentChunk.document_id == document_id)
                        .order_by(DocumentChunk.chunk_index.asc())
                    )
                    .scalars()
                    .all()
                )

                content = "\n\n".join(
                    str(chunk.content or "")
                    for chunk in chunks
                )

        return {
            "success": True,
            "found": True,
            "document_id": document.id,
            "filename": document.filename,
            "document_type": document.document_type,
            "source_path": document.source_path,
            "editable": editable,
            "extension": extension,
            "content": content,
            "edit_note": (
                None
                if editable
                else (
                    "PDF documents are not edited inline. "
                    "Delete the PDF and upload a replacement file instead."
                )
            ),
        }

    except Exception as error:
        return {
            "success": False,
            "found": False,
            "document_id": document_id,
            "error": str(error),
        }

    finally:
        db.close()


def update_knowledge_document_content(
    document_id: int,
    content: str,
) -> dict:
    """Edit TXT/MD content and rebuild every chunk + embedding.

    The key point is that editing a source file alone is not enough for RAG.
    Old pgvector embeddings must be removed and regenerated from the new text.
    """

    cleaned_content = str(content or "").strip()

    if not cleaned_content:
        return {
            "success": False,
            "error": "Document content cannot be empty.",
        }

    db = SessionLocal()
    path = None
    old_text = None

    try:
        document = db.get(KnowledgeDocument, document_id)

        if not document:
            return {
                "success": False,
                "error": f"Knowledge document {document_id} was not found.",
            }

        extension = _document_extension(document)

        if extension not in EDITABLE_EXTENSIONS:
            return {
                "success": False,
                "error": (
                    "Only TXT and Markdown documents can be edited inline. "
                    "For PDFs, delete the old file and upload a replacement."
                ),
            }

        chunks = chunk_text(cleaned_content)

        if not chunks:
            return {
                "success": False,
                "error": "No chunks could be created from the edited content.",
            }

        # Generate all embeddings before changing the database. If model
        # inference fails, the existing RAG record remains untouched.
        embedded_chunks = []

        for index, chunk in enumerate(chunks):
            embedding = create_embedding(chunk)

            embedded_chunks.append(
                {
                    "chunk_index": index,
                    "content": chunk,
                    "embedding": embedding,
                }
            )

        path = _document_path(document)

        if path.exists():
            old_text = path.read_text(encoding="utf-8")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(cleaned_content, encoding="utf-8")

        db.execute(
            delete(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )

        for item in embedded_chunks:
            db.add(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=item["chunk_index"],
                    content=item["content"],
                    embedding=item["embedding"],
                )
            )

        db.commit()

        return {
            "success": True,
            "document_id": document_id,
            "filename": document.filename,
            "chunks_created": len(embedded_chunks),
            "message": (
                "Document updated and all pgvector embeddings were rebuilt."
            ),
        }

    except Exception as error:
        db.rollback()

        # Best-effort restoration of the text file if the DB transaction
        # failed after the source file was changed.
        if path is not None and old_text is not None:
            try:
                path.write_text(old_text, encoding="utf-8")
            except Exception:
                pass

        return {
            "success": False,
            "error": str(error),
        }

    finally:
        db.close()
