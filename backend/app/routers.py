from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from shutil import copyfileobj
from pathlib import Path
import os
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List
import json
from datetime import datetime

from .database import get_db
from .models import Conversation, Message, SenderType
from .schemas import ConversationCreate, ConversationResponse, MessageCreate, MessageResponse, MarkReadRequest
from .sockets import manager

router = APIRouter()

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{file_ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        copyfileobj(file.file, buffer)
        
    return {"url": f"/static/{filename}"}

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(conv_in: ConversationCreate, db: AsyncSession = Depends(get_db)):
    # 1. 既存の会話を検索 (アクティブかつvisitor_idが一致するもの)
    # selectinload を使い、既存の会話と一緒にメッセージも取得
    stmt = select(Conversation).where(
        Conversation.visitor_id == conv_in.visitor_id, 
        Conversation.is_active == True
    ).options(selectinload(Conversation.messages))
    
    result = await db.execute(stmt)
    existing = result.scalars().first()
    
    if existing:
        return existing

    # 2. 新しい会話を作成
    new_conv = Conversation(visitor_id=conv_in.visitor_id)
    db.add(new_conv)
    await db.commit()
    await db.refresh(new_conv)
    
    # 新規作成時は空リストを代入（エラー回避のため）
    new_conv.messages = []
    return new_conv

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_all_conversations(db: AsyncSession = Depends(get_db)):
    # 手動ループによる N+1 を排除し、1回のクエリで全メッセージを即時読み込み（selectinload）
    stmt = select(Conversation).options(
        selectinload(Conversation.messages)
    ).order_by(Conversation.created_at.desc())
    
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return conversations

@router.get("/conversations/{visitor_id}", response_model=ConversationResponse)
async def get_conversation(visitor_id: str, db: AsyncSession = Depends(get_db)):
    # 履歴取得時も selectinload を使用
    stmt = select(Conversation).where(
        Conversation.visitor_id == visitor_id
    ).options(selectinload(Conversation.messages)).order_by(Conversation.created_at.desc())
    
    result = await db.execute(stmt)
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conv

@router.post("/conversations/{visitor_id}/read")
async def mark_messages_read(
    visitor_id: str, 
    req: MarkReadRequest, 
    db: AsyncSession = Depends(get_db)
):
    # 会話を検索
    result = await db.execute(select(Conversation).where(Conversation.visitor_id == visitor_id))
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 既読にする対象のメッセージを検索
    # 自分が sender_type なら、相手のメッセージを既読にする
    target_sender_types = []
    if req.sender_type == "visitor":
        target_sender_types = [SenderType.OPERATOR, SenderType.BOT]
    elif req.sender_type == "operator":
        target_sender_types = [SenderType.VISITOR]
    
    # 未読メッセージを一括更新
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conv.id,
            Message.sender_type.in_(target_sender_types),
            Message.is_read == False
        )
    )
    result = await db.execute(stmt)
    unread_messages = result.scalars().all()
    
    print(f"[DEBUG] mark_read: visitor_id={visitor_id}, requester={req.sender_type}, found={len(unread_messages)}")
    
    if unread_messages:
        for msg in unread_messages:
            msg.is_read = True
        await db.commit()
        
        # 既読を送信
        event_data = {
            "type": "messages_read",
            "conversation_id": conv.id,
            "visitor_id": visitor_id,
            "reader_type": req.sender_type,
            "read_at": datetime.utcnow().isoformat() + "Z"
        }
        await manager.broadcast_to_conversation(visitor_id, event_data)
        
    return {"status": "ok", "updated_count": len(unread_messages)}

# 訪問者向けWebSocket
@router.websocket("/ws/visitor/{visitor_id}")
async def websocket_visitor_endpoint(websocket: WebSocket, visitor_id: str, db: AsyncSession = Depends(get_db)):
    conv_id = visitor_id # visitor_idをmanager内の会話キーとして使用
    
    # 1. WebSocket接続を確立
    await manager.connect_visitor(websocket, conv_id)
    try:
        while True:
            # 2. メッセージを受信
            data = await websocket.receive_text()
            # 3. メッセージをDBへ保存
            # 実際の会話IDをDBから検索
            result = await db.execute(select(Conversation).where(Conversation.visitor_id == visitor_id))
            conv = result.scalars().first()
            if not conv:
                 conv = Conversation(visitor_id=visitor_id)
                 db.add(conv)
                 await db.commit()
                 await db.refresh(conv)

            # 受信データはJSON形式と想定
            try:
                payload = json.loads(data)
                content = payload.get("content", "")
                image_url = payload.get("image_url")
            except json.JSONDecodeError:
                # JSONでない場合はそのままテキストとして扱う
                content = data
                image_url = None

            new_msg = Message(
                conversation_id=conv.id, 
                content=content, 
                sender_type=SenderType.VISITOR,
                image_url=image_url
            )
            db.add(new_msg)
            await db.commit()
            
            # 4. オペレーターへ送信
            # 訪問者メッセージを送信
            visitor_msg_data = {
                "id": new_msg.id,
                "conversation_id": conv.id,
                "content": new_msg.content,
                "sender_type": "visitor",
                "created_at": new_msg.created_at.isoformat() + "Z",
                "visitor_id": visitor_id,
                "image_url": new_msg.image_url,
                "is_read": False
            }
            await manager.broadcast_to_conversation(conv_id, visitor_msg_data)

            # ５．　　botの自動返信
            # botのメッセージが既にあるか確認
            bot_check_stmt = select(Message).where(
                Message.conversation_id == conv.id,
                Message.sender_type == SenderType.BOT
            )
            bot_check_res = await db.execute(bot_check_stmt)
            existing_bot_msg = bot_check_res.scalars().first()

            # botの返信がまだない場合のみ送信
            if not existing_bot_msg:
                bot_content = "お問い合わせありがとうございます．担当者が確認しておりますので，このまま少々お待ちください．"
                bot_msg = Message(
                    conversation_id=conv.id, 
                    content=bot_content, 
                    sender_type=SenderType.BOT
                )
                db.add(bot_msg)
                await db.commit()
                await db.refresh(bot_msg)

                # botのメッセージを送信
                bot_msg_data = {
                    "id": bot_msg.id,
                    "conversation_id": conv.id,
                    "content": bot_msg.content,
                    "sender_type": "bot",
                    "created_at": bot_msg.created_at.isoformat() + "Z",
                    "visitor_id": visitor_id,
                    "is_read": False
                }
                # visitor_id (conv_id) を指定してブロードキャスト
                await manager.broadcast_to_conversation(conv_id, bot_msg_data)
            
    except WebSocketDisconnect:
        manager.disconnect_visitor(websocket, conv_id)

# オペレーター向けWebSocket
@router.websocket("/ws/operator")
async def websocket_operator_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    # 1. オペレーターの接続を確立
    await manager.connect_operator(websocket)
    try:
        while True:
            # 2. メッセージを受信
            data = await websocket.receive_text()
            payload = json.loads(data)
            # 3. オペレーターからのメッセージ送信処理
            # payload に含まれるべき情報: conversation_id (int) または visitor_id, content
            
            visitor_id = payload.get("visitor_id")
            content = payload.get("content")
            image_url = payload.get("image_url")
            
            if visitor_id and (content or image_url):
                result = await db.execute(select(Conversation).where(Conversation.visitor_id == visitor_id))
                conv = result.scalars().first()
                if conv:
                    new_msg = Message(
                        conversation_id=conv.id, 
                        content=content, 
                        sender_type=SenderType.OPERATOR,
                        image_url=image_url
                    )
                    db.add(new_msg)
                    await db.commit()
                    
                    msg_data = {
                        "id": new_msg.id,
                        "conversation_id": conv.id,
                        "content": new_msg.content,
                        "sender_type": "operator",
                        "created_at": new_msg.created_at.isoformat() + "Z",
                        "visitor_id": visitor_id,
                        "image_url": new_msg.image_url,
                        "is_read": False
                    }
                    await manager.broadcast_to_conversation(visitor_id, msg_data)

    except WebSocketDisconnect:
        manager.disconnect_operator(websocket)
