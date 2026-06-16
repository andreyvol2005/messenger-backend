from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import hashlib

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
async def register(user: UserCreate, db: asyncpg.Connection = Depends(get_db)):
    hashed = hash_password(user.password)
    try:
        result = await db.fetchrow(
            "INSERT INTO users (username, password_hash) VALUES ($1, $2) RETURNING id",
            user.username, hashed
        )
        return {"user_id": result["id"], "message": "User created"}
    except asyncpg.UniqueViolationError:
        raise HTTPException(400, "Username already exists")

@app.post("/auth/login")
async def login(user: UserLogin, db: asyncpg.Connection = Depends(get_db)):
    db_user = await db.fetchrow(
        "SELECT id, username, password_hash FROM users WHERE username = $1", user.username
    )
    if not db_user:
        raise HTTPException(401, "Invalid credentials")
    if db_user["password_hash"] != hash_password(user.password):
        raise HTTPException(401, "Invalid credentials")
    return {"user_id": db_user["id"], "username": db_user["username"], "message": "Login successful"}