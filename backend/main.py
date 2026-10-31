import os

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import ai_identify
import models
import security
import storage
from database import Base, engine, get_db

# Creates any missing tables the first time the server starts.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Style Me API")

# Lets website call this backend from the browser.
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

# Only used while S3_BUCKET is unset (testing on your own computer): serves saved photos.
storage.LOCAL_UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=storage.LOCAL_UPLOAD_DIR), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------- What the frontend is allowed to send ----------
class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ---------- Routes ----------
@app.post("/api/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower()

    if len(body.password.encode("utf-8")) > 72:  # bcrypt's limit
        raise HTTPException(status_code=400, detail="Password is too long.")

    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = models.User(
        name=body.name.strip(),
        email=email,
        password_hash=security.hash_password(body.password),  # only the hash is saved
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two people registered the same email at the same moment
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    return {"message": "Account created! Taking you to sign in..."}


@app.post("/api/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == body.email.lower()))

    # Error message whether the email or the password is wrong.
    if not user or not security.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    return {"message": f"Welcome back, {user.name}!", "token": security.create_token(user.id)}



bearer = HTTPBearer()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.User:
    user_id = security.decode_token(creds.credentials)
    user = db.get(models.User, user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    return user


@app.get("/api/me")
def me(user: models.User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


# ---------- Account settings ----------
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)


class DeleteAccountRequest(BaseModel):
    password: str


@app.put("/api/me/password")
def change_password(
    body: ChangePasswordRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not security.verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect.")
    if len(body.new_password.encode("utf-8")) > 72:  # bcrypt's limit
        raise HTTPException(status_code=400, detail="Password is too long.")

    user.password_hash = security.hash_password(body.new_password)
    db.commit()
    return {"message": "Password updated."}


@app.delete("/api/me")
def delete_account(
    body: DeleteAccountRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not security.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password is incorrect.")

    # Remember the photo filenames first, rows are about to be deleted.
    photo_names = db.scalars(
        select(models.ClothingItem.image_filename).where(models.ClothingItem.user_id == user.id)
    ).all()

    # Also deletes clothing items and outfits.
    db.delete(user)
    db.commit()

    for name in photo_names:  # only after the database change succeeded
        storage.delete_image(name)
    return {"message": "Your account has been deleted."}


# ---------- Wardrobe ----------
def _item_out(item: models.ClothingItem) -> dict:
    return {
        "id": item.id,
        "image_url": storage.image_url(item.image_filename),
        "category": item.category,
        "colour": item.colour,
        "pattern": item.pattern,
        "season": item.season,
    }


@app.post("/api/wardrobe", status_code=201)
async def add_clothing_item(
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    data = await file.read()
    if len(data) > 15 * 1024 * 1024:  # 15 MB, before compression
        raise HTTPException(status_code=400, detail="Image is too large.")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        traits = ai_identify.identify_clothing(data, file.content_type)
        filename = storage.save_image(data, user.email)
    except Exception:
        raise HTTPException(status_code=400, detail="That file doesn't look like a valid image.")

    item = models.ClothingItem(
        user_id=user.id,
        image_filename=filename,
        category=traits["category"],
        colour=traits["colour"],
        pattern=traits["pattern"],
        season=traits["season"],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_out(item)


@app.get("/api/wardrobe")
def list_wardrobe(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(
        select(models.ClothingItem)
        .where(models.ClothingItem.user_id == user.id)
        .order_by(models.ClothingItem.created_at.desc())
    ).all()
    return [_item_out(item) for item in items]


def _get_owned_item(item_id: int, user: models.User, db: Session) -> models.ClothingItem:
    item = db.get(models.ClothingItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found.")
    return item


@app.get("/api/wardrobe/{item_id}")
def get_clothing_item(item_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _item_out(_get_owned_item(item_id, user, db))


class UpdateItemRequest(BaseModel):
    category: str
    colour: str
    pattern: str
    season: str


@app.put("/api/wardrobe/{item_id}")
def update_clothing_item(
    item_id: int,
    body: UpdateItemRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_owned_item(item_id, user, db)
    for field, allowed in (
        ("category", models.CATEGORIES),
        ("colour", models.COLOURS),
        ("pattern", models.PATTERNS),
        ("season", models.SEASONS),
    ):
        if getattr(body, field) not in allowed:
            raise HTTPException(status_code=400, detail=f"'{getattr(body, field)}' is not a valid {field}.")

    item.category, item.colour, item.pattern, item.season = body.category, body.colour, body.pattern, body.season
    db.commit()
    return _item_out(item)


@app.delete("/api/wardrobe/{item_id}")
def delete_clothing_item(item_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get_owned_item(item_id, user, db)
    filename = item.image_filename
    db.delete(item)
    db.commit()
    storage.delete_image(filename)
    return {"message": "Item deleted."}
