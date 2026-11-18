from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status

from app.modules.auth.security import get_optional_vendor
from app.modules.documents.schemas import DocumentResponse, DocumentUpdate
from app.modules.documents.service import document_service

router = APIRouter()


def _get_tenant_id(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            from app.modules.auth.security import decode_access_token
            claims = decode_access_token(token)
            if claims.get("sub"):
                return str(claims["sub"])
        except Exception:
            pass
    vendor = get_optional_vendor(request)
    return str(vendor["_id"]) if vendor and "_id" in vendor else None


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document to Cloudinary and store URL in DB",
    description="Uploads a business or vehicle document file to Cloudinary and saves its URL, category and metadata in MongoDB.",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Document file to upload (PDF, PNG, JPG, etc.)"),
    name: str = Form(..., description="Document title/name"),
    category: str = Form(..., description="Category, e.g. Shop License, GST Certificate, Insurance"),
    scope: str = Form("Business", description="Scope: Business or Vehicle"),
    vehicle_id: Optional[str] = Form(None, description="Optional associated vehicle ID"),
    vehicle_name: Optional[str] = Form(None, description="Optional associated vehicle name"),
    status_val: str = Form("In review", description="Initial verification status"),
    notes: Optional[str] = Form(None, description="Optional remarks or notes"),
) -> DocumentResponse:
    try:
        tenant_id = _get_tenant_id(request)
        return await document_service.upload_document(
            file=file,
            name=name,
            category=category,
            scope=scope,
            vehicle_id=vehicle_id,
            vehicle_name=vehicle_name,
            status=status_val,
            notes=notes,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document upload failed: {str(exc)}",
        )


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List all documents",
    description="Fetch business and vehicle documents with optional filtering by scope, category or search query.",
)
def list_documents(
    request: Request,
    scope: Optional[str] = Query(None, description="Filter by scope: Business or Vehicle"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status: Verified, In review, Expired"),
    query: Optional[str] = Query(None, description="Search keyword in name or vehicle"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> List[DocumentResponse]:
    tenant_id = _get_tenant_id(request)
    return document_service.list_documents(
        scope=scope,
        category=category,
        status=status,
        query=query,
        skip=skip,
        limit=limit,
        tenant_id=tenant_id,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get single document record",
)
def get_document(document_id: str, request: Request) -> DocumentResponse:
    tenant_id = _get_tenant_id(request)
    doc = document_service.get_document(document_id, tenant_id=tenant_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return doc


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document verification status or metadata",
)
def update_document(document_id: str, payload: DocumentUpdate, request: Request) -> DocumentResponse:
    tenant_id = _get_tenant_id(request)
    updated = document_service.update_document(document_id, payload, tenant_id=tenant_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return updated


@router.delete(
    "/{document_id}",
    summary="Delete document",
)
def delete_document(document_id: str, request: Request) -> dict:
    success = document_service.delete_document(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return {"success": True, "message": f"Document '{document_id}' deleted successfully."}
