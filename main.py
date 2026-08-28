import uuid
import sqlite3
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="KAI-1 Production Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DB_FILE = "kai1_chat_history.db"
MAX_HISTORY_MESSAGES = 10

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
        conn.commit()

init_db()

def get_session_history(session_id: str, limit: int = MAX_HISTORY_MESSAGES) -> List[dict]:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content FROM messages 
            WHERE session_id = ? 
            ORDER BY id DESC LIMIT ?
        """, (session_id, limit))
        rows = cursor.fetchall()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

def save_message(session_id: str, role: str, content: str):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (session_id, role, content) 
            VALUES (?, ?, ?)
        """, (session_id, role, content))
        conn.commit()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    total_stored_messages: int

@app.post("/api/kai1/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    session_id = payload.session_id or str(uuid.uuid4())
    save_message(session_id, "user", payload.message)
    context_messages = get_session_history(session_id, limit=MAX_HISTORY_MESSAGES)

    data = {
        "model": "kai-1",
        "messages": context_messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "repeat_penalty": 1.20
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=data, timeout=90)
        bot_reply = response.json().get("message", {}).get("content", "")
        save_message(session_id, "assistant", bot_reply)

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
            total_msgs = cursor.fetchone()[0]

        return ChatResponse(
            reply=bot_reply,
            session_id=session_id,
            total_stored_messages=total_msgs
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kai1/history/{session_id}")
def get_full_history(session_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
        rows = cursor.fetchall()
        return {"session_id": session_id, "history": [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]}

@app.delete("/api/kai1/session/{session_id}")
def delete_session(session_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        deleted = cursor.rowcount
        conn.commit()
    return {"status": "success", "deleted_messages": deleted}
