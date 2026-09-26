import os
import uuid
import shutil
from fastapi import UploadFile

class UploadService:
    def __init__(self):
        self.upload_dir = "static/uploads"
        os.makedirs(self.upload_dir, exist_ok=True)

    def upload_image(self, file: UploadFile) -> str:
        """
        Uploads an image to local static directory and returns its public URL.
        """
        file_extension = ""
        if file.filename and "." in file.filename:
            file_extension = f".{file.filename.split('.')[-1]}"
        
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        filepath = os.path.join(self.upload_dir, unique_filename)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        url = f"/static/uploads/{unique_filename}"
        
        return url
