from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.knowledge_admin import (
    get_knowledge_document_content,
    update_knowledge_document_content,
)


router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Admin"],
)


class KnowledgeEditRequest(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=2_000_000,
    )


@router.get("/{document_id}/content")
def knowledge_document_content(document_id: int):
    result = get_knowledge_document_content(document_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Could not read knowledge document."),
        )

    if not result.get("found"):
        raise HTTPException(
            status_code=404,
            detail=f"Knowledge document {document_id} was not found.",
        )

    return result


@router.put("/{document_id}")
def edit_knowledge_document(
    document_id: int,
    request: KnowledgeEditRequest,
):
    result = update_knowledge_document_content(
        document_id=document_id,
        content=request.content,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Could not update knowledge document."),
        )

    return result
