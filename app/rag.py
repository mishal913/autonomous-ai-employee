from pathlib import Path

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from sqlalchemy import (
    delete,
    func,
    select,
)

from app.database import SessionLocal

from app.models import (
    KnowledgeDocument,
    DocumentChunk,
)

from app.observability import (
    log_event,
    track_operation,
)


# ============================================================
# CONFIGURATION
# ============================================================

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

EMBEDDING_DIMENSION = 384

CHUNK_SIZE_WORDS = 180

CHUNK_OVERLAP_WORDS = 40


# ------------------------------------------------------------
# Retrieval similarity threshold
#
# This is NOT a probability.
#
# We will later evaluate different thresholds scientifically.
# ------------------------------------------------------------

MIN_SIMILARITY = 0.35


# ============================================================
# GLOBAL EMBEDDING MODEL
# ============================================================

_embedding_model = None


# ============================================================
# HELPER — SHORT QUERY FOR LOGGING
# ============================================================

def _safe_query_preview(
    query: str,
    max_length: int = 200,
) -> str:
    """
    Keep logs useful without storing very long prompts.

    We log only a short preview of the search query.
    """

    query = (
        query
        .replace("\n", " ")
        .strip()
    )

    return query[
        :max_length
    ]


# ============================================================
# EMBEDDING MODEL
# ============================================================

def get_embedding_model():
    """
    Load the SentenceTransformer model once per Python process.

    In FastAPI:

        first RAG request
            ↓
        load model

        later RAG requests
            ↓
        reuse same model
    """

    global _embedding_model


    if _embedding_model is None:

        print(
            "[RAG] Loading embedding model:",
            EMBEDDING_MODEL_NAME,
        )


        with track_operation(
            "rag_embedding_model_load",
            {
                "model":
                    EMBEDDING_MODEL_NAME,

                "dimension":
                    EMBEDDING_DIMENSION,
            },
        ):

            _embedding_model = (
                SentenceTransformer(
                    EMBEDDING_MODEL_NAME
                )
            )


        log_event(
            "rag_embedding_model_loaded",
            {
                "model":
                    EMBEDDING_MODEL_NAME,

                "dimension":
                    EMBEDDING_DIMENSION,
            },
        )


    return _embedding_model


# ============================================================
# CREATE ONE EMBEDDING
# ============================================================

def create_embedding(
    text: str,
) -> list[float]:

    text = text.strip()


    if not text:

        raise ValueError(
            "Cannot create embedding from empty text."
        )


    model = get_embedding_model()


    with track_operation(
        "rag_create_query_embedding",
        {
            "text_length":
                len(text),
        },
    ):

        vector = model.encode(
            text,
            normalize_embeddings=True,
        )


    return vector.tolist()


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_pdf_text(
    file_path: str,
) -> str:

    with track_operation(
        "rag_extract_pdf_text",
        {
            "filename":
                Path(
                    file_path
                ).name,
        },
    ):

        reader = PdfReader(
            file_path
        )


        pages = []


        for page in reader.pages:

            text = (
                page.extract_text()
            )


            if text:

                cleaned = (
                    text.strip()
                )


                if cleaned:

                    pages.append(
                        cleaned
                    )


        extracted_text = (
            "\n\n".join(
                pages
            )
        )


    log_event(
        "rag_pdf_extracted",
        {
            "filename":
                Path(
                    file_path
                ).name,

            "pages":
                len(
                    reader.pages
                ),

            "characters":
                len(
                    extracted_text
                ),
        },
    )


    return extracted_text


# ============================================================
# TXT / MARKDOWN EXTRACTION
# ============================================================

def extract_text_file(
    file_path: str,
) -> str:

    path = Path(
        file_path
    )


    with track_operation(
        "rag_extract_text_file",
        {
            "filename":
                path.name,
        },
    ):

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )


    log_event(
        "rag_text_file_extracted",
        {
            "filename":
                path.name,

            "characters":
                len(
                    text
                ),
        },
    )


    return text


# ============================================================
# GENERAL DOCUMENT EXTRACTION
# ============================================================

def extract_document_text(
    file_path: str,
) -> str:

    path = Path(
        file_path
    )


    extension = (
        path.suffix
        .lower()
    )


    if extension == ".pdf":

        return extract_pdf_text(
            str(path)
        )


    if extension in {
        ".txt",
        ".md",
    }:

        return extract_text_file(
            str(path)
        )


    raise ValueError(
        f"Unsupported document type: {extension}"
    )


# ============================================================
# CHUNK TEXT
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """
    Split text into overlapping word chunks.

    Example:

        chunk_size = 180
        overlap = 40

    Chunk 1:
        words 0-179

    Chunk 2:
        words 140-319
    """

    if chunk_size <= 0:

        raise ValueError(
            "chunk_size must be greater than 0."
        )


    if overlap < 0:

        raise ValueError(
            "overlap cannot be negative."
        )


    if overlap >= chunk_size:

        raise ValueError(
            "Chunk overlap must be smaller "
            "than chunk size."
        )


    words = text.split()


    if not words:

        return []


    chunks = []

    start = 0


    while start < len(words):

        end = (
            start
            +
            chunk_size
        )


        chunk_words = words[
            start:end
        ]


        chunk = (
            " ".join(
                chunk_words
            )
            .strip()
        )


        if chunk:

            chunks.append(
                chunk
            )


        if end >= len(words):

            break


        start = (
            end
            -
            overlap
        )


    return chunks


# ============================================================
# INGEST ONE DOCUMENT
# ============================================================

def ingest_document(
    file_path: str,
) -> dict:

    path = Path(
        file_path
    ).resolve()


    if not path.exists():

        return {
            "success":
                False,

            "error":
                (
                    f"File was not found: "
                    f"{path}"
                ),
        }


    if not path.is_file():

        return {
            "success":
                False,

            "error":
                (
                    f"Path is not a file: "
                    f"{path}"
                ),
        }


    filename = path.name


    log_event(
        "rag_document_ingestion_started",
        {
            "filename":
                filename,

            "document_type":
                path.suffix
                .lower()
                .lstrip("."),
        },
    )


    try:

        with track_operation(
            "rag_document_ingestion",
            {
                "filename":
                    filename,
            },
        ):

            print(
                "\n[RAG] Reading:",
                filename,
            )


            # =================================================
            # STEP 1 — EXTRACT TEXT
            # =================================================

            text = extract_document_text(
                str(path)
            )


            if not text.strip():

                error = (
                    "No readable text was found "
                    "in the document."
                )


                log_event(
                    "rag_document_ingestion_rejected",
                    {
                        "filename":
                            filename,

                        "reason":
                            error,
                    },
                )


                return {
                    "success":
                        False,

                    "error":
                        error,
                }


            # =================================================
            # STEP 2 — CHUNK
            # =================================================

            with track_operation(
                "rag_chunk_document",
                {
                    "filename":
                        filename,

                    "chunk_size":
                        CHUNK_SIZE_WORDS,

                    "chunk_overlap":
                        CHUNK_OVERLAP_WORDS,
                },
            ):

                chunks = chunk_text(
                    text
                )


            print(
                f"[RAG] Created "
                f"{len(chunks)} chunks"
            )


            log_event(
                "rag_chunks_created",
                {
                    "filename":
                        filename,

                    "chunks":
                        len(
                            chunks
                        ),

                    "chunk_size_words":
                        CHUNK_SIZE_WORDS,

                    "chunk_overlap_words":
                        CHUNK_OVERLAP_WORDS,
                },
            )


            if not chunks:

                error = (
                    "Document produced no chunks."
                )


                log_event(
                    "rag_document_ingestion_rejected",
                    {
                        "filename":
                            filename,

                        "reason":
                            error,
                    },
                )


                return {
                    "success":
                        False,

                    "error":
                        error,
                }


            # =================================================
            # STEP 3 — CREATE EMBEDDINGS
            # =================================================

            model = get_embedding_model()


            print(
                "[RAG] Creating embeddings..."
            )


            with track_operation(
                "rag_document_embedding",
                {
                    "filename":
                        filename,

                    "chunks":
                        len(
                            chunks
                        ),

                    "model":
                        EMBEDDING_MODEL_NAME,
                },
            ):

                embeddings = model.encode(
                    chunks,
                    normalize_embeddings=True,
                    show_progress_bar=True,
                )


            log_event(
                "rag_document_embeddings_created",
                {
                    "filename":
                        filename,

                    "chunks":
                        len(
                            chunks
                        ),

                    "embedding_dimension":
                        EMBEDDING_DIMENSION,

                    "embedding_model":
                        EMBEDDING_MODEL_NAME,
                },
            )


            # =================================================
            # STEP 4 — DATABASE
            # =================================================

            db = SessionLocal()


            try:

                with track_operation(
                    "rag_store_document_database",
                    {
                        "filename":
                            filename,

                        "chunks":
                            len(
                                chunks
                            ),
                    },
                ):

                    # -----------------------------------------
                    # Remove previous ingestion of SAME PATH
                    # -----------------------------------------

                    previous_documents = (
                        db.execute(
                            select(
                                KnowledgeDocument
                            )
                            .where(
                                KnowledgeDocument
                                .source_path
                                ==
                                str(path)
                            )
                        )
                        .scalars()
                        .all()
                    )


                    removed_old_versions = len(
                        previous_documents
                    )


                    for previous in previous_documents:

                        db.execute(
                            delete(
                                DocumentChunk
                            )
                            .where(
                                DocumentChunk
                                .document_id
                                ==
                                previous.id
                            )
                        )


                        db.delete(
                            previous
                        )


                    db.flush()


                    # -----------------------------------------
                    # Create document record
                    # -----------------------------------------

                    document = (
                        KnowledgeDocument(

                            filename=
                                filename,

                            source_path=
                                str(path),

                            document_type=
                                (
                                    path.suffix
                                    .lower()
                                    .lstrip(".")
                                ),
                        )
                    )


                    db.add(
                        document
                    )


                    # Gives us document.id
                    db.flush()


                    # -----------------------------------------
                    # Save chunks + vectors
                    # -----------------------------------------

                    for index, (
                        chunk,
                        embedding,
                    ) in enumerate(
                        zip(
                            chunks,
                            embeddings,
                        )
                    ):

                        db.add(
                            DocumentChunk(

                                document_id=
                                    document.id,

                                chunk_index=
                                    index,

                                content=
                                    chunk,

                                embedding=
                                    embedding.tolist(),
                            )
                        )


                    db.commit()


                    db.refresh(
                        document
                    )


                print(
                    "[RAG] Document stored successfully"
                )


                log_event(
                    "rag_document_ingested",
                    {
                        "document_id":
                            document.id,

                        "filename":
                            document.filename,

                        "chunks":
                            len(
                                chunks
                            ),

                        "embedding_dimension":
                            EMBEDDING_DIMENSION,

                        "replaced_old_versions":
                            removed_old_versions,
                    },
                )


                return {
                    "success":
                        True,

                    "document_id":
                        document.id,

                    "filename":
                        document.filename,

                    "chunks_created":
                        len(
                            chunks
                        ),

                    "embedding_dimension":
                        EMBEDDING_DIMENSION,
                }


            except Exception:

                db.rollback()

                raise


            finally:

                db.close()


    except Exception as error:

        print(
            "[RAG] INGEST ERROR:",
            repr(
                error
            )
        )


        log_event(
            "rag_document_ingestion_error",
            {
                "filename":
                    filename,

                "error_type":
                    type(
                        error
                    ).__name__,

                "error":
                    str(
                        error
                    ),
            },
        )


        return {
            "success":
                False,

            "error":
                str(
                    error
                ),
        }


# ============================================================
# INGEST COMPLETE KNOWLEDGE FOLDER
# ============================================================

def ingest_knowledge_folder(
    folder_path: str = "knowledge",
) -> dict:

    folder = Path(
        folder_path
    ).resolve()


    if not folder.exists():

        return {
            "success":
                False,

            "error":
                (
                    "Knowledge folder does not exist: "
                    f"{folder}"
                ),
        }


    supported_extensions = {
        ".pdf",
        ".txt",
        ".md",
    }


    files = sorted(
        [
            path
            for path
            in folder.iterdir()
            if (
                path.is_file()
                and
                path.suffix.lower()
                in supported_extensions
            )
        ]
    )


    print(
        f"\n[RAG] Found "
        f"{len(files)} supported documents"
    )


    log_event(
        "rag_folder_ingestion_started",
        {
            "documents_found":
                len(
                    files
                ),
        },
    )


    results = []


    with track_operation(
        "rag_folder_ingestion",
        {
            "documents_found":
                len(
                    files
                ),
        },
    ):

        for path in files:

            print(
                f"\n[RAG] Ingesting "
                f"{path.name}"
            )


            result = ingest_document(
                str(
                    path
                )
            )


            results.append(
                result
            )


    successful = sum(
        1
        for result
        in results
        if result.get(
            "success"
        )
    )


    failed = (
        len(
            results
        )
        -
        successful
    )


    log_event(
        "rag_folder_ingestion_completed",
        {
            "documents_found":
                len(
                    files
                ),

            "documents_ingested":
                successful,

            "documents_failed":
                failed,
        },
    )


    return {
        "success":
            failed == 0,

        "folder":
            str(
                folder
            ),

        "documents_found":
            len(
                files
            ),

        "documents_ingested":
            successful,

        "documents_failed":
            failed,

        "results":
            results,
    }


# ============================================================
# SEMANTIC SEARCH
# ============================================================

def semantic_search(
    query: str,
    limit: int = 5,
    min_similarity: float = MIN_SIMILARITY,
) -> dict:

    query = query.strip()


    if not query:

        return {
            "success":
                False,

            "error":
                "Search query cannot be empty.",
        }


    if limit < 1:

        return {
            "success":
                False,

            "error":
                "Search limit must be at least 1.",
        }


    # Prevent unnecessarily huge RAG retrievals.
    limit = min(
        limit,
        20,
    )


    query_preview = (
        _safe_query_preview(
            query
        )
    )


    log_event(
        "rag_search_started",
        {
            "query_preview":
                query_preview,

            "limit":
                limit,

            "min_similarity":
                min_similarity,
        },
    )


    try:

        with track_operation(
            "rag_semantic_search",
            {
                "query_preview":
                    query_preview,

                "limit":
                    limit,
            },
        ):

            # =================================================
            # STEP 1 — QUERY EMBEDDING
            # =================================================

            query_embedding = (
                create_embedding(
                    query
                )
            )


            # =================================================
            # STEP 2 — VECTOR DATABASE SEARCH
            # =================================================

            db = SessionLocal()


            try:

                distance = (
                    DocumentChunk
                    .embedding
                    .cosine_distance(
                        query_embedding
                    )
                )


                # Retrieve extra candidates before filtering.
                candidate_limit = max(
                    limit * 3,
                    10,
                )


                with track_operation(
                    "rag_pgvector_search",
                    {
                        "candidate_limit":
                            candidate_limit,

                        "requested_limit":
                            limit,
                    },
                ):

                    rows = (
                        db.execute(
                            select(
                                DocumentChunk,
                                KnowledgeDocument,
                                distance.label(
                                    "distance"
                                ),
                            )
                            .join(
                                KnowledgeDocument,

                                KnowledgeDocument.id
                                ==
                                DocumentChunk.document_id,
                            )
                            .order_by(
                                distance
                            )
                            .limit(
                                candidate_limit
                            )
                        )
                        .all()
                    )


                # =================================================
                # STEP 3 — APPLY RELEVANCE THRESHOLD
                # =================================================

                results = []


                for (
                    chunk,
                    document,
                    cosine_distance,
                ) in rows:

                    cosine_distance = float(
                        cosine_distance
                    )


                    similarity = (
                        1.0
                        -
                        cosine_distance
                    )


                    if (
                        similarity
                        <
                        min_similarity
                    ):

                        continue


                    results.append(
                        {
                            "document_id":
                                document.id,

                            "filename":
                                document.filename,

                            "chunk_id":
                                chunk.id,

                            "chunk_index":
                                chunk.chunk_index,

                            "content":
                                chunk.content,

                            "cosine_distance":
                                cosine_distance,

                            "similarity":
                                similarity,
                        }
                    )


                    if len(
                        results
                    ) >= limit:

                        break


                # =================================================
                # OBSERVABILITY
                # =================================================

                log_event(
                    "rag_retrieval",
                    {
                        "query_preview":
                            query_preview,

                        "candidates_examined":
                            len(
                                rows
                            ),

                        "results_count":
                            len(
                                results
                            ),

                        "min_similarity":
                            min_similarity,

                        "results":
                            [
                                {
                                    "document_id":
                                        result[
                                            "document_id"
                                        ],

                                    "filename":
                                        result[
                                            "filename"
                                        ],

                                    "chunk_index":
                                        result[
                                            "chunk_index"
                                        ],

                                    "similarity":
                                        round(
                                            float(
                                                result[
                                                    "similarity"
                                                ]
                                            ),
                                            4,
                                        ),
                                }

                                for result
                                in results
                            ],
                    },
                )


                return {
                    "success":
                        True,

                    "query":
                        query,

                    "min_similarity":
                        min_similarity,

                    "results_count":
                        len(
                            results
                        ),

                    "results":
                        results,
                }


            finally:

                db.close()


    except Exception as error:

        print(
            "[RAG] SEARCH ERROR:",
            repr(
                error
            )
        )


        log_event(
            "rag_search_error",
            {
                "query_preview":
                    query_preview,

                "error_type":
                    type(
                        error
                    ).__name__,

                "error":
                    str(
                        error
                    ),
            },
        )


        return {
            "success":
                False,

            "error":
                str(
                    error
                ),
        }


# ============================================================
# LIST KNOWLEDGE DOCUMENTS
# ============================================================

def list_knowledge_documents() -> dict:

    db = SessionLocal()


    try:

        with track_operation(
            "rag_list_documents"
        ):

            documents = (
                db.execute(
                    select(
                        KnowledgeDocument
                    )
                    .order_by(
                        KnowledgeDocument
                        .created_at
                        .desc()
                    )
                )
                .scalars()
                .all()
            )


            results = []


            for document in documents:

                chunk_count = (
                    db.execute(
                        select(
                            func.count(
                                DocumentChunk.id
                            )
                        )
                        .where(
                            DocumentChunk.document_id
                            ==
                            document.id
                        )
                    )
                    .scalar_one()
                )


                results.append(
                    {
                        "document_id":
                            document.id,

                        "filename":
                            document.filename,

                        "source_path":
                            document.source_path,

                        "document_type":
                            document.document_type,

                        "chunks":
                            chunk_count,

                        "created_at":
                            (
                                document
                                .created_at
                                .isoformat()

                                if document.created_at

                                else None
                            ),
                    }
                )


        log_event(
            "rag_documents_listed",
            {
                "documents_count":
                    len(
                        results
                    ),

                "filenames":
                    [
                        document[
                            "filename"
                        ]
                        for document
                        in results
                    ],
            },
        )


        return {
            "success":
                True,

            "count":
                len(
                    results
                ),

            "documents":
                results,
        }


    except Exception as error:

        print(
            "[RAG] LIST ERROR:",
            repr(
                error
            )
        )


        log_event(
            "rag_list_documents_error",
            {
                "error_type":
                    type(
                        error
                    ).__name__,

                "error":
                    str(
                        error
                    ),
            },
        )


        return {
            "success":
                False,

            "error":
                str(
                    error
                ),
        }


    finally:

        db.close()


# ============================================================
# DELETE KNOWLEDGE DOCUMENT
# ============================================================

def delete_knowledge_document(
    document_id: int,
) -> dict:

    db = SessionLocal()


    try:

        document = db.get(
            KnowledgeDocument,
            document_id,
        )


        if not document:

            log_event(
                "rag_document_delete_not_found",
                {
                    "document_id":
                        document_id,
                },
            )


            return {
                "success":
                    False,

                "error":
                    (
                        f"Document "
                        f"{document_id} "
                        "was not found."
                    ),
            }


        filename = (
            document.filename
        )


        source_path = (
            document.source_path
        )


        with track_operation(
            "rag_delete_document",
            {
                "document_id":
                    document_id,

                "filename":
                    filename,
            },
        ):

            db.execute(
                delete(
                    DocumentChunk
                )
                .where(
                    DocumentChunk.document_id
                    ==
                    document_id
                )
            )


            db.delete(
                document
            )


            db.commit()


        log_event(
            "rag_document_deleted",
            {
                "document_id":
                    document_id,

                "filename":
                    filename,
            },
        )


        return {
            "success":
                True,

            "document_id":
                document_id,

            "filename":
                filename,

            "source_path":
                source_path,

            "message":
                (
                    "Knowledge document and its "
                    "vector chunks were deleted."
                ),
        }


    except Exception as error:

        db.rollback()


        print(
            "[RAG] DELETE ERROR:",
            repr(
                error
            )
        )


        log_event(
            "rag_document_delete_error",
            {
                "document_id":
                    document_id,

                "error_type":
                    type(
                        error
                    ).__name__,

                "error":
                    str(
                        error
                    ),
            },
        )


        return {
            "success":
                False,

            "error":
                str(
                    error
                ),
        }


    finally:

        db.close()