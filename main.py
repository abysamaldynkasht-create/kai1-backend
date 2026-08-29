import uuid
import sqlite3
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="KAI-1 AI Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DB_FILE = "/app/kai1_chat_history.db"
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
        conn.commit()

init_db()

def get_session_history(session_id: str, limit: int = MAX_HISTORY_MESSAGES) -> List[dict]:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit))
        rows = cursor.fetchall()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

def save_message(session_id: str, role: str, content: str):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, role, content))
        conn.commit()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# 🌟 واجهة الشات المدمجة مباشرة في الرابط الرئيسي
@app.get("/", response_class=HTMLResponse)
def get_chat_ui():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>KAI-1 | Akasha AI</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
            body { background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; }
            .chat-container { width: 100%; max-width: 700px; height: 90vh; background: #1e293b; border-radius: 16px; display: flex; flex-direction: column; box-shadow: 0 10px 25px rgba(0,0,0,0.5); overflow: hidden; border: 1px solid #334155; }
            .header { padding: 18px 24px; background: #0f172a; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }
            .header h1 { font-size: 1.2rem; color: #38bdf8; }
            .header span { font-size: 0.8rem; background: #0284c7; padding: 4px 10px; border-radius: 20px; }
            .messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
            .msg { max-width: 80%; padding: 12px 18px; border-radius: 14px; line-height: 1.6; font-size: 0.95rem; word-break: break-word; }
            .user { align-self: flex-start; background: #0284c7; color: white; border-bottom-left-radius: 2px; }
            .assistant { align-self: flex-end; background: #334155; color: #f8fafc; border-bottom-right-radius: 2px; }
            .input-area { padding: 16px; background: #0f172a; border-top: 1px solid #334155; display: flex; gap: 10px; }
            input { flex: 1; padding: 12px 16px; border-radius: 10px; border: 1px solid #334155; background: #1e293b; color: white; outline: none; font-size: 1rem; }
            input:focus { border-color: #38bdf8; }
            button { padding: 12px 24px; border-radius: 10px; border: none; background: #0284c7; color: white; font-weight: bold; cursor: pointer; transition: 0.2s; }
            button:hover { background: #0369a1; }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <div class="header">
                <h1>🤖 KAI-1 Assistant</h1>
                <span>Akasha AI</span>
            </div>
            <div class="messages" id="chatBox">
                <div class="msg assistant">حبابك ألف يا حبيبنا! أنا KAI-1، جاهز معاك في أي استفسار أو موضوع حابب نتناقش فيه.</div>
            </div>
            <div class="input-area">
                <input type="text" id="userInput" placeholder="اكتب رسالتك هنا..." onkeydown="if(event.key==='Enter') send()">
                <button onclick="send()" id="sendBtn">إرسال</button>
            </div>
        </div>

        <script>
            let sessionId = localStorage.getItem("kai1_session") || "";
            async function send() {
                const input = document.getElementById("userInput");
                const text = input.value.trim();
                if (!text) return;
                
                const box = document.getElementById("chatBox");
                box.innerHTML += `<div class="msg user">${text}</div>`;
                input.value = "";
                box.scrollTop = box.scrollHeight;

                const loadingId = "load-" + Date.now();
                box.innerHTML += `<div class="msg assistant" id="${loadingId}">⏳ جاري الرد...</div>`;
                box.scrollTop = box.scrollHeight;

                try {
                    const res = await fetch("/api/kai1/chat", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ message: text, session_id: sessionId || null })
                    });
                    const data = await res.json();
                    sessionId = data.session_id;
                    localStorage.setItem("kai1_session", sessionId);
                    document.getElementById(loadingId).innerText = data.reply;
                } catch(e) {
                    document.getElementById(loadingId).innerText = "❌ حدث خطأ في الاتصال بالسيرفر";
                }
                box.scrollTop = box.scrollHeight;
            }
        </script>
    </body>
    </html>
    """

@app.post("/api/kai1/chat")
def chat(payload: ChatRequest):
    session_id = payload.session_id or str(uuid.uuid4())
    save_message(session_id, "user", payload.message)
    context_messages = get_session_history(session_id, limit=MAX_HISTORY_MESSAGES)

    data = {
        "model": "kai-1",
        "messages": context_messages,
        "stream": False,
        "options": {"temperature": 0.3, "repeat_penalty": 1.20}
    }

    try:
        res = requests.post(OLLAMA_URL, json=data, timeout=120)
        bot_reply = res.json().get("message", {}).get("content", "")
        save_message(session_id, "assistant", bot_reply)
        return {"reply": bot_reply, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
