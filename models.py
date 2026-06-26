from typing import Optional

from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class ContactAdd(BaseModel):
    contact_user_id: int

class SendMessageRequest(BaseModel):
    chat_id: int
    sender_id: int
    text: Optional[str] = None
    media_url: Optional[str] = None
    reply_to_id: Optional[int] = None