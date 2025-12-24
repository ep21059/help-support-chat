from typing import List, Dict
from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        # active_connections: conversation_id -> List[WebSocket] (訪問者は通常1人だが、技術的には複数タブの可能性があるためリスト)
        self.active_conversations: Dict[str, List[WebSocket]] = {}
        # operator_connections: List[WebSocket] (全てのチャットをリッスンするオペレーター)
        self.operator_connections: List[WebSocket] = []

    async def connect_visitor(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = []
        self.active_conversations[conversation_id].append(websocket)

    def disconnect_visitor(self, websocket: WebSocket, conversation_id: str):
        if conversation_id in self.active_conversations:
            if websocket in self.active_conversations[conversation_id]:
                self.active_conversations[conversation_id].remove(websocket)

    async def connect_operator(self, websocket: WebSocket):
        await websocket.accept()
        self.operator_connections.append(websocket)

    def disconnect_operator(self, websocket: WebSocket):
        if websocket in self.operator_connections:
            self.operator_connections.remove(websocket)

    async def broadcast_to_conversation(self, conversation_id: str, message: dict):
        # 1. その会話の訪問者へ送信
        if conversation_id in self.active_conversations:
            for connection in self.active_conversations[conversation_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error broadcasting to visitor: {e}")
                    pass # 切断を適切に処理

        # 2. 全てのオペレーターへ送信
        for connection in self.operator_connections:
            try:
                # オペレーター向けに conversation_id をコンテキストに追加
                # メッセージ内に既に conversation_id (int) が含まれている場合は上書きしない
                if "conversation_id" in message:
                     msg_with_context = message
                else:
                     msg_with_context = {**message, "conversation_id": conversation_id}
                
                await connection.send_json(msg_with_context)
            except Exception as e:
                print(f"Error broadcasting to operator: {e}")
                pass

manager = ConnectionManager()
