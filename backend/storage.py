"""Saves and serves clothing photos.

If S3_BUCKET is set in .env (the live server), photos go to a PRIVATE Amazon S3
bucket. Otherwise they are saved to a local "uploads" folder, so you can build
and test on your own computer without any AWS setup.

Only the filename is saved in the database, never a full URL,
so switching between local and S3 doesn't need a database change.

On the live server the AWS permissions come from the EC2 server's IAM role, so
there are no AWS keys in .env or in git.
"""
import io
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

load_dotenv()

LOCAL_UPLOAD_DIR = Path(__file__).parent / "uploads"
S3_BUCKET = os.getenv("S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")

MAX_DIMENSION = 1024      # longest side, in pixels
JPEG_QUALITY = 80         # 0-100; lower = smaller file, more visible quality loss
URL_LIFETIME = 3600       # seconds a private photo link stays valid (1 hour)

_s3 = None


def _safe_email_prefix(email: str) -> str:
    """Turns an email into something safe to use as a folder name."""
    return email.lower().replace("@", "_at_").replace(".", "_")


def _compress(data: bytes) -> bytes:
    """Shrinks the photo and re-saves it as JPEG, so wardrobe photos don't
    eat up storage space or take ages to load in the app."""
    image = Image.open(io.BytesIO(data))
    image = image.convert("RGB")  # drops transparency; needed for JPEG
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def _client():
    """The S3 connection, created once. boto3 is imported here so it is only
    needed when S3 is actually switched on."""
    global _s3
    if _s3 is None:
        import boto3
        from botocore.config import Config
        _s3 = boto3.client("s3", region_name=AWS_REGION, config=Config(signature_version="s3v4"))
    return _s3


def save_image(data: bytes, email: str) -> str:
    """Compresses the photo and saves it. Returns the filename to store
    in the ClothingItem.image_filename column."""
    compressed = _compress(data)
    filename = f"{_safe_email_prefix(email)}/{uuid.uuid4().hex}.jpg"

    if S3_BUCKET:
        _client().put_object(
            Bucket=S3_BUCKET, Key=filename, Body=compressed, ContentType="image/jpeg"
        )
    else:
        path = LOCAL_UPLOAD_DIR / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(compressed)

    return filename


def delete_image(filename: str) -> None:
    try:
        if S3_BUCKET:
            _client().delete_object(Bucket=S3_BUCKET, Key=filename)
        else:
            (LOCAL_UPLOAD_DIR / filename).unlink(missing_ok=True)
    except Exception:
        pass 


def image_exists(filename: str) -> bool:
    """True if the photo file is really there. Used so outfits never include an item
    whose photo is missing (for example a test item added on another computer)."""
    if not S3_BUCKET:
        return (LOCAL_UPLOAD_DIR / filename).exists()
    try:
        _client().head_object(Bucket=S3_BUCKET, Key=filename)
        return True
    except Exception as err:
        code = str(getattr(err, "response", {}).get("Error", {}).get("Code", ""))
        # Without permission to list the bucket, S3 answers a missing file with 403, not 404.
        return code not in {"404", "NoSuchKey", "NotFound", "403", "Forbidden", "AccessDenied"}


def image_url(filename: str) -> str:
    """The address the frontend uses in an <img src="..."> tag.

    The S3 bucket is private, so this makes a temporary signed link that works
    for one hour. The frontend asks for a fresh one each time it loads the list.
    """
    if S3_BUCKET:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": filename},
            ExpiresIn=URL_LIFETIME,
        )
    return f"/uploads/{filename}"
