from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import psycopg2

from database import get_db
from models import UserCreate, UserLogin, ContactAdd, SendMessageRequest

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


# ============================================
# 1. Регистрация
# ============================================
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
        user_id = result[0]
        db.commit()
        return {"user_id": user_id, "message": "User created"}
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(400, "Username already exists")


# ============================================
# 2. Логин
# ============================================
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
    if db_user[2] != hash_password(user.password):
        raise HTTPException(401, "Invalid credentials")
    return {"user_id": db_user[0], "username": db_user[1], "message": "Login successful"}


# ============================================
# 3. Получение пользователя
# ============================================
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
        "id": user[0],
        "username": user[1],
        "nickname": user[2] or "user",
        "bio": user[3],
        "birthDate": user[4],
        "avatarUrl": user[5],
        "createdAt": str(user[6]) if user[6] else None
    }


# ============================================
# 4. Поиск пользователя по username
# ============================================
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
        "id": user[0],
        "username": user[1],
        "nickname": user[2] or user[1],
        "avatarUrl": user[3]
    }


# ============================================
# 5. Добавление контакта
# ============================================
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


# ============================================
# 6. Получение контактов
# ============================================
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
            "id": contact[0],
            "username": contact[1],
            "nickname": contact[2] or contact[1],
            "avatarUrl": contact[3]
        }
        for contact in contacts
    ]


# ============================================
# 7. Создание чата
# ============================================
@app.post("/chats")
def create_chat(
        user_id: int,
        type: str,
        partner_username: str,
        db: psycopg2.extensions.connection = Depends(get_db)
):
    cur = db.cursor()

    # Находим партнёра
    cur.execute("SELECT id FROM users WHERE username = %s", (partner_username,))
    partner = cur.fetchone()
    if not partner:
        raise HTTPException(404, "User not found")

    partner_id = partner[0]

    # Проверяем существующий чат
    cur.execute("""
        SELECT c.id FROM chats c
        JOIN chat_members cm1 ON cm1.chat_id = c.id AND cm1.user_id = %s
        JOIN chat_members cm2 ON cm2.chat_id = c.id AND cm2.user_id = %s
        WHERE c.type = 'private'
    """, (user_id, partner_id))
    existing = cur.fetchone()

    if existing:
        return {"id": existing[0], "type": type, "message": "Chat already exists"}

    # Создаём чат
    cur.execute(
        "INSERT INTO chats (type) VALUES (%s) RETURNING id",
        (type,)
    )
    chat_id = cur.fetchone()[0]

    # Добавляем участников
    cur.execute(
        "INSERT INTO chat_members (chat_id, user_id) VALUES (%s, %s), (%s, %s)",
        (chat_id, user_id, chat_id, partner_id)
    )
    db.commit()

    return {"id": chat_id, "type": type, "message": "Chat created"}


# ============================================
# 8. Получение чатов пользователя
# ============================================
@app.get("/chats/user/{user_id}")
def get_user_chats(user_id: int, db: psycopg2.extensions.connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute("""
        SELECT 
            c.id,
            c.type,
            c.name,
            m.text AS last_message_text,
            m.created_at AS last_message_time,
            u.id AS partner_id,
            u.username AS partner_username,
            u.nickname AS partner_nickname,
            u.avatar_url AS partner_avatar_url
        FROM chat_members cm
        JOIN chats c ON c.id = cm.chat_id
        LEFT JOIN messages m ON m.id = c.last_message_id
        LEFT JOIN chat_members cm2 ON cm2.chat_id = c.id AND cm2.user_id != cm.user_id
        LEFT JOIN users u ON u.id = cm2.user_id
        WHERE cm.user_id = %s
        ORDER BY m.created_at DESC NULLS LAST
    """, (user_id,))

    chats = cur.fetchall()

    return [
        {
            "id": chat[0],
            "type": chat[1],
            "name": chat[2],
            "last_message": {
                "text": chat[3],
                "created_at": str(chat[4]) if chat[4] else None
            } if chat[3] else None,
            "partner": {
                "id": chat[5],
                "username": chat[6],
                "nickname": chat[7] or chat[6],
                "avatar_url": chat[8]
            } if chat[5] else None,
            "unread_count": 0
        }
        for chat in chats
    ]


# ============================================
# 9. Получение сообщений чата
# ============================================
@app.get("/messages/chat/{chat_id}")
def get_chat_messages(
        chat_id: int,
        limit: int = 50,
        offset: int = 0,
        db: psycopg2.extensions.connection = Depends(get_db)
):
    cur = db.cursor()
    cur.execute("""
        SELECT id, chat_id, sender_id, text, media_url, created_at, reply_to_id, is_deleted
        FROM messages
        WHERE chat_id = %s AND (is_deleted = FALSE OR is_deleted IS NULL)
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (chat_id, limit, offset))

    messages = cur.fetchall()

    return [
        {
            "id": message[0],
            "chat_id": message[1],
            "sender_id": message[2],
            "text": message[3],
            "media_url": message[4],
            "created_at": str(message[5]) if message[5] else None,
            "reply_to_id": message[6],
            "is_deleted": message[7] if len(message) > 7 else False,
            "is_read": False
        }
        for message in messages
    ]


# ============================================
# 10. Отправка сообщения
# ============================================
@app.post("/messages")
def send_message(
        request: SendMessageRequest,
        db: psycopg2.extensions.connection = Depends(get_db)
):
    cur = db.cursor()
    cur.execute("""
        INSERT INTO messages (chat_id, sender_id, text, media_url, reply_to_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (request.chat_id, request.sender_id, request.text, request.media_url, request.reply_to_id))

    result = cur.fetchone()
    if not result:
        raise HTTPException(500, "Failed to create message")

    message_id = result[0]

    # Обновляем last_message_id в чате
    cur.execute(
        "UPDATE chats SET last_message_id = %s WHERE id = %s",
        (message_id, request.chat_id)
    )
    db.commit()

    return {"message_id": message_id}