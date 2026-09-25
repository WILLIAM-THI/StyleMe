import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import security
from database import Base, engine, get_db

# Creates any missing tables the first time the server starts.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Style Me API")

origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


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
    except IntegrityError:  # same email error
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    return {"message": "Account created! Taking you to sign in..."}


@app.post("/api/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == body.email.lower()))

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
 
    # Also deletes their clothing items and outfits
    db.delete(user)
    db.commit()
    return {"message": "Your account has been deleted."}