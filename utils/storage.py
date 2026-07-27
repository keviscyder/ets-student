"""
Nuotraukų kompresavimas ir įkėlimas į Supabase Storage.
"""
import io
import uuid
from PIL import Image
from supabase import Client

BUCKET_NAME = "test-images"
MAX_WIDTH = 1600


def compress_image(uploaded_file, max_width: int = MAX_WIDTH, quality: int = 85) -> bytes:
    """Sumažina nuotraukos plotį (jei reikia) ir grąžina suspaustus baitus."""
    img = Image.open(uploaded_file)
    img = img.convert("RGB")

    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def upload_image(supabase: Client, uploaded_file, folder: str = "questions") -> str:
    """
    Suspaudžia ir įkelia nuotrauką į Supabase Storage.
    Grąžina viešą URL.
    """
    compressed_bytes = compress_image(uploaded_file)
    filename = f"{folder}/{uuid.uuid4()}.jpg"

    supabase.storage.from_(BUCKET_NAME).upload(
        filename,
        compressed_bytes,
        {"content-type": "image/jpeg"},
    )

    return supabase.storage.from_(BUCKET_NAME).get_public_url(filename)
