from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import psycopg2

from database import get_db
from models import UserCreate, UserLogin

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@app.post("/auth/register")
def register(user: UserCreate, db: psycopg2.extensions.connection = Depends(get_db)):
    hashed = hash_password(user.password)
    try:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
            (user.username, hashed)
        )
        user_id = cur.fetchone()["id"]
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