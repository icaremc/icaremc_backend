import os
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from app.resources.uploads.service import UploadService, is_allowed_file

router = APIRouter(prefix="/uploads", tags=["Uploads"])
upload_service = UploadService()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


class UploadOut(BaseModel):
    url: str
    file_name: str | None = None
    mime_type: str | None = None
    size: int | None = None


@router.post("", response_model=UploadOut, include_in_schema=False)
@router.post(
    "/",
    response_model=UploadOut,
    summary="Upload image or document file",
    operation_id="upload_image_api_v1_uploads__post",
)
async def upload_file(file: UploadFile = File(...)):
    if not is_allowed_file(file.filename, file.content_type):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Supported types include images (PNG, JPEG, WEBP, etc.), PDFs, documents (DOC, DOCX, TXT, etc.), audio, and video.",
        )

    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds maximum allowed limit (50MB).")

    try:
        result = upload_service.upload_file(file)
        if int(result["size"]) > MAX_FILE_SIZE:
            # Clean up saved file if over limit
            uploaded_filename = os.path.basename(str(result["url"]))
            uploaded_path = os.path.join(upload_service.upload_dir, uploaded_filename)
            if os.path.exists(uploaded_path):
                os.remove(uploaded_path)
            raise HTTPException(status_code=413, detail="File size exceeds maximum allowed limit (50MB).")

        return UploadOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

