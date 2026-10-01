import os
import uuid
import shutil
from fastapi import UploadFile

class UploadService:
    def __init__(self):
        self.upload_dir = "static/uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
        self.base_url = os.environ.get("BASE_URL", "")

    def upload_image(self, file: UploadFile) -> str:
        """
        Uploads an image to the local filesystem and returns its URL.
        """
        file_extension = ""
        if file.filename and "." in file.filename:
            file_extension = f".{file.filename.split('.')[-1]}"
        
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join(self.upload_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Return the public-facing URL
        if self.base_url:
            endpoint = self.base_url.rstrip("/")
            url = f"{endpoint}/{self.upload_dir}/{unique_filename}"
        else:
            url = f"/{self.upload_dir}/{unique_filename}"
            
        return url
