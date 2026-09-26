from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from app.resources.uploads.service import UploadService

router = APIRouter(prefix="/uploads", tags=["Uploads"])
upload_service = UploadService()

class UploadOut(BaseModel):
    url: str

@router.post("/", response_model=UploadOut)
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")
    
    try:
        url = upload_service.upload_image(file)
        return UploadOut(url=url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
