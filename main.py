from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor

from database import get_db
from models import UserCreate, UserLogin, ContactAdd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@app.get("/")
async def root():
    return {"message": "Messenger API is running!"}

@app.post("/auth/register")
def register(user: UserCreate, db: psycopg2.extensions.connection = Depends(get_db)):
    hashed = hash_password(user.password)
    try:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
            (user.username, hashed)
        )
        result = cur.fetchone()
        user_id = result["id"]
        db.commit()
        return {"user_id": user_id, "message": "User created"}
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(400, "Username already exists")

@app.post("/auth/login")
def login(user: UserLogin, db: psycopg2.extensions.connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute(
        "SELECT id, username, password_hash FROM users WHERE username = %s",
        (user.username,)
    )
    db_user = cur.fetchone()
    if not db_user:
        raise HTTPException(401, "Invalid credentials")
    if db_user["password_hash"] != hash_password(user.password):
        raise HTTPException(401, "Invalid credentials")
    return {"user_id": db_user["id"], "username": db_user["username"], "message": "Login successful"}

@app.get("/users/{user_id}")
def get_user(user_id: int, db: psycopg2.extensions.connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute(
        "SELECT id, username, nickname, bio, birth_date, avatar_url, created_at FROM users WHERE id = %s",
        (user_id,)
    )
    user = cur.fetchone()
    if not user:
        raise HTTPException(404, "User not found")
    return {
        "id": user["id"],
        "username": user["username"],
        "nickname": user["nickname"] or "user",
        "bio": user["bio"],
        "birthDate": user["birth_date"],
        "avatarUrl": user["avatar_url"],
        "createdAt": str(user["created_at"]) if user["created_at"] else None
    }

@app.get("/users/by-username/{username}")
def get_user_by_username(
    username: str,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    cur = db.cursor()
    cur.execute(
        "SELECT id, username, nickname, avatar_url FROM users WHERE username = %s",
        (username,)
    )
    user = cur.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user["id"],
        "username": user["username"],
        "nickname": user["nickname"] or user["username"],
        "avatarUrl": user["avatar_url"]
    }

@app.post("/contacts")
def add_contact(
    user_id: int,
    contact: ContactAdd,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    try:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO contacts (user_id, contact_user_id) VALUES (%s, %s)",
            (user_id, contact.contact_user_id)
        )
        db.commit()
        return {"message": "Contact added"}
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(400, "Contact already exists")

@app.get("/contacts/{user_id}")
def get_contacts(
    user_id: int,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    cur = db.cursor()
    cur.execute("""
        SELECT u.id, u.username, u.nickname, u.avatar_url
        FROM contacts c
        JOIN users u ON u.id = c.contact_user_id
        WHERE c.user_id = %s
    """, (user_id,))
    contacts = cur.fetchall()
    return [
        {
            "id": contact["id"],
            "username": contact["username"],
            "nickname": contact["nickname"] or contact["username"],
            "avatarUrl": contact["avatar_url"]
        }
        for contact in contacts
    ]