import os
import uuid
from app.core.config import settings


def save_upload_file(image_bytes: bytes, original_filename: str = "image.jpg") -> str:
    """Save an uploaded image byte buffer to disk and return the stored path."""
    ext = os.path.splitext(original_filename)[1] or ".jpg"
    unique_filename = f"{uuid.uuid4()}{ext}"
    target_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    with open(target_path, "wb") as f:
        f.write(image_bytes)
        
    return target_path
