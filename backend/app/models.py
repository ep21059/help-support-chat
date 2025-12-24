from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class SenderType(str, enum.Enum):
    VISITOR = "visitor"
    OPERATOR = "operator"
    BOT = "bot"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(String, index=True)  # クライアント側で保存されるUUID
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship("Message", back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    content = Column(Text)
    sender_type = Column(SAEnum(SenderType))
    image_url = Column(String, nullable=True) # 将来的な使用のため
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
