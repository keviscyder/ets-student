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


DRAFT_FOLDER = "drafts"


def upload_draft(supabase: Client, submission_id: str, data: bytes) -> str:
    """Bendras mokinio juodraštis: vienas failas vienam bandymui (perrašomas)."""
    path = f"{DRAFT_FOLDER}/{submission_id}.jpg"
    compressed = compress_image(io.BytesIO(data), max_width=1200, quality=70)
    supabase.storage.from_(BUCKET_NAME).upload(
        path, compressed, {"content-type": "image/jpeg", "upsert": "true"},
    )
    return supabase.storage.from_(BUCKET_NAME).get_public_url(path)


def find_draft(supabase: Client, submission_id: str):
    """Grąžina juodraščio URL, jei jis jau išsaugotas, kitaip None."""
    try:
        files = supabase.storage.from_(BUCKET_NAME).list(DRAFT_FOLDER, {"search": submission_id})
    except Exception:
        return None
    for f in files or []:
        if f.get("name") == f"{submission_id}.jpg":
            return supabase.storage.from_(BUCKET_NAME).get_public_url(f"{DRAFT_FOLDER}/{submission_id}.jpg")
    return None
