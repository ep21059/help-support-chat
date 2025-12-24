from pydantic import BaseModel, field_serializer
from typing import Optional, List
from datetime import datetime, timezone
from .models import SenderType

class MessageCreate(BaseModel):
    content: str
    sender_type: SenderType

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    content: str
    sender_type: SenderType
    image_url: Optional[str] = None
    is_read: bool = False
    created_at: datetime
    
    @field_serializer('created_at')
    def serialize_dt(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    
    class Config:
        # ORMモード有効化
        from_attributes = True

class ConversationCreate(BaseModel):
    visitor_id: str

class MarkReadRequest(BaseModel):
    sender_type: str

class ConversationResponse(BaseModel):
    id: int
    visitor_id: str
    is_active: bool
    created_at: datetime
    messages: List[MessageResponse] = []

    @field_serializer('created_at')
    def serialize_dt(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    class Config:
        from_attributes = True
