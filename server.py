import asyncio
import os
import csv
import io
import sys
from contextlib import asynccontextmanager

if getattr(sys, 'frozen', False):
    LOG_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    LOG_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(LOG_DIR, "helpdesk.log")

class SafeLogger:
    def __init__(self, stream, log_path):
        self.stream = stream
        self.log_path = log_path
        self.encoding = "utf-8"

    def isatty(self):
        return False

    def write(self, buf):
        if buf:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(buf)
            except Exception:
                pass
        if self.stream is not None:
            try:
                self.stream.write(buf)
                self.stream.flush()
            except Exception:
                pass

    def flush(self):
        if self.stream is not None:
            try:
                self.stream.flush()
            except Exception:
                pass

sys.stdout = SafeLogger(sys.stdout, LOG_FILE)
sys.stderr = SafeLogger(sys.stderr, LOG_FILE)

from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import (
    init_db, get_setting, set_setting, get_all_tickets,
    get_ticket_details, update_ticket_status, add_message,
    get_stats, update_ticket_phone, verify_user_credentials,
    update_user_password, get_all_users, create_user,
    delete_user, create_session, verify_session, delete_session,
    assign_ticket, update_ticket_priority, get_analytics_report
)
from telegram_bot import TelegramBot

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()
bot = TelegramBot(broadcast_callback=manager.broadcast)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    await bot.start()
    yield
    # Shutdown
    await bot.stop()

app = FastAPI(title="IT Support Helpdesk API", lifespan=lifespan)

import sys
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    meipass = getattr(sys, '_MEIPASS', exe_dir)
    if os.path.exists(os.path.join(exe_dir, "static", "index.html")):
        STATIC_DIR = os.path.join(exe_dir, "static")
    elif os.path.exists(os.path.join(meipass, "static", "index.html")):
        STATIC_DIR = os.path.join(meipass, "static")
    else:
        STATIC_DIR = os.path.join(exe_dir, "static")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Auth Dependency
async def get_current_user(request: Request) -> str:
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    username = verify_session(token)
    if not username:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
        
    return username

# Request Models
class LoginPayload(BaseModel):
    username: str
    password: str

class CredentialsPayload(BaseModel):
    current_password: str
    new_password: str

class CreateUserPayload(BaseModel):
    username: str
    password: str
    role: Optional[str] = "agent"

class TokenPayload(BaseModel):
    token: str

class ReplyPayload(BaseModel):
    text: str
    agent_name: Optional[str] = "IT Support"

class StatusPayload(BaseModel):
    status: str

class UpdateUserPayload(BaseModel):
    phone_number: Optional[str] = None

class AssignPayload(BaseModel):
    assigned_to: Optional[str] = None

class PriorityPayload(BaseModel):
    priority: str

# Routes
@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# Auth Endpoints
@app.post("/api/auth/login")
async def login(payload: LoginPayload, response: Response):
    username = payload.username.strip()
    password = payload.password
    
    user_info = verify_user_credentials(username, password)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = create_session(user_info["username"])
    # Set cookie valid for 7 days
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=7 * 24 * 3600,
        httponly=False,
        samesite="lax"
    )
    return {"ok": True, "token": token, "username": user_info["username"], "role": user_info["role"]}

@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        delete_session(token)
    response.delete_cookie("session_token")
    return {"ok": True}

@app.get("/api/auth/me")
async def get_current_session(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            
    if not token:
        return {"authenticated": False}
        
    username = verify_session(token)
    if not username:
        return {"authenticated": False}
        
    return {"authenticated": True, "username": username}

@app.post("/api/auth/credentials")
async def change_credentials(payload: CredentialsPayload, user: str = Depends(get_current_user)):
    user_info = verify_user_credentials(user, payload.current_password)
    if not user_info:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
        
    new_pass = payload.new_password.strip()
    if len(new_pass) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
        
    update_user_password(user, new_pass)
    return {"ok": True, "username": user}

# User Management Endpoints
@app.get("/api/users")
async def list_users(user: str = Depends(get_current_user)):
    users = get_all_users()
    return {"users": users}

@app.post("/api/users")
async def add_new_user(payload: CreateUserPayload, user: str = Depends(get_current_user)):
    username = payload.username.strip()
    password = payload.password.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
        
    try:
        new_u = create_user(username, password, role=payload.role or "agent")
        return {"ok": True, "user": new_u}
    except Exception as e:
        if "UNIQUE" in str(e).upper():
            raise HTTPException(status_code=400, detail="Username already exists")
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/users/{user_id}")
async def remove_user(user_id: int, user: str = Depends(get_current_user)):
    users = get_all_users()
    target = next((u for u in users if u["id"] == user_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target["username"] == user:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    delete_user(user_id)
    return {"ok": True}

# System & Settings Endpoints
@app.get("/api/status")
async def get_system_status(request: Request):
    token = bot.get_token()
    is_configured = bool(token)
    bot_info = bot.bot_info
    sess_token = request.cookies.get("session_token")
    agent_user = verify_session(sess_token) if sess_token else None
    stats = get_stats(agent_username=agent_user)
    return {
        "configured": is_configured,
        "bot_running": bot.is_running,
        "bot": bot_info,
        "stats": stats,
        "current_user": agent_user
    }

@app.post("/api/settings/token")
async def set_bot_token(payload: TokenPayload, user: str = Depends(get_current_user)):
    tok = payload.token.strip()
    if not tok:
        raise HTTPException(status_code=400, detail="Bot token cannot be empty")
    
    test_res = await bot.verify_token(tok)
    if not test_res.get("ok"):
        raise HTTPException(status_code=400, detail=test_res.get("error", "Failed to verify bot token"))
    
    await bot.restart(new_token=tok)
    return {"ok": True, "bot": test_res.get("bot")}

# Ticket Management Endpoints (Protected)
@app.get("/api/tickets")
async def list_tickets(status: Optional[str] = "all", assigned: Optional[str] = None, user: str = Depends(get_current_user)):
    tickets = get_all_tickets(status_filter=status, assigned_filter=assigned)
    stats = get_stats(agent_username=user)
    return {"tickets": tickets, "stats": stats}

@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, user: str = Depends(get_current_user)):
    ticket = get_ticket_details(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ticket": ticket}

@app.post("/api/tickets/{ticket_id}/reply")
async def reply_to_ticket(ticket_id: int, payload: ReplyPayload, user: str = Depends(get_current_user)):
    ticket = get_ticket_details(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Reply text cannot be empty")
    
    # Send message PRIVATELY to the user who opened the ticket
    delivery_res = await bot.send_agent_reply(ticket, text, agent_name=user or payload.agent_name or "IT Support")
    
    # Record in database
    msg = add_message(
        ticket_id=ticket_id,
        sender_type="agent",
        sender_name=user or payload.agent_name or "IT Support",
        text=text
    )
    
    # If ticket was open, mark as in_progress
    if ticket["status"] == "open":
        update_ticket_status(ticket_id, "in_progress")
        ticket["status"] = "in_progress"

    # Broadcast event to all open tabs
    await manager.broadcast({
        "type": "new_message",
        "ticket_id": ticket_id,
        "message": msg,
        "ticket_status": ticket["status"]
    })
    
    return {
        "ok": True, 
        "message": msg, 
        "delivered": delivery_res.get("delivered", True),
        "reason": delivery_res.get("reason", "")
    }

@app.post("/api/tickets/{ticket_id}/status")
async def change_ticket_status(ticket_id: int, payload: StatusPayload, user: str = Depends(get_current_user)):
    new_status = payload.status
    if new_status not in ('open', 'in_progress', 'resolved', 'closed'):
        raise HTTPException(status_code=400, detail="Invalid ticket status")
        
    ticket = get_ticket_details(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    try:
        updated = update_ticket_status(ticket_id, new_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Notify user on Telegram PRIVATELY
    await bot.notify_ticket_status(ticket, new_status)
    
    # Broadcast to dashboard
    await manager.broadcast({
        "type": "status_changed",
        "ticket_id": ticket_id,
        "status": new_status
    })
    
    return {"ok": True, "ticket": updated}

@app.post("/api/tickets/{ticket_id}/update-info")
async def update_ticket_info(ticket_id: int, payload: UpdateUserPayload, user: str = Depends(get_current_user)):
    if payload.phone_number is not None:
        update_ticket_phone(ticket_id, payload.phone_number.strip())
        
    await manager.broadcast({
        "type": "ticket_updated",
        "ticket_id": ticket_id,
        "phone_number": payload.phone_number
    })
    return {"ok": True}

@app.post("/api/tickets/{ticket_id}/request-phone")
async def request_ticket_phone(ticket_id: int, user: str = Depends(get_current_user)):
    ticket = get_ticket_details(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    res = await bot.request_user_phone(ticket)
    return {"ok": True, "delivered": res.get("ok", False)}

@app.post("/api/tickets/{ticket_id}/assign")
async def assign_ticket_endpoint(ticket_id: int, payload: AssignPayload, user: str = Depends(get_current_user)):
    ticket = get_ticket_details(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    updated = assign_ticket(ticket_id, payload.assigned_to)
    stats = get_stats(agent_username=user)
    
    await manager.broadcast({
        "type": "ticket_assigned",
        "ticket_id": ticket_id,
        "assigned_to": payload.assigned_to,
        "ticket": updated,
        "stats": stats
    })
    return {"ok": True, "ticket": updated}

@app.post("/api/tickets/{ticket_id}/priority")
async def change_ticket_priority(ticket_id: int, payload: PriorityPayload, user: str = Depends(get_current_user)):
    ticket = get_ticket_details(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    updated = update_ticket_priority(ticket_id, payload.priority)
    
    await manager.broadcast({
        "type": "priority_changed",
        "ticket_id": ticket_id,
        "priority": payload.priority,
        "ticket": updated
    })
    return {"ok": True, "ticket": updated}

# Analytics & Reports Endpoints
@app.get("/api/reports")
async def get_reports_endpoint(start_date: Optional[str] = None, end_date: Optional[str] = None, user: str = Depends(get_current_user)):
    report = get_analytics_report(start_date=start_date, end_date=end_date)
    return {"ok": True, "report": report}

@app.get("/api/reports/export")
async def export_reports_csv(start_date: Optional[str] = None, end_date: Optional[str] = None, user: str = Depends(get_current_user)):
    report = get_analytics_report(start_date=start_date, end_date=end_date)
    tickets = report.get("tickets", [])
    
    output = io.StringIO()
    # Write UTF-8 BOM so Microsoft Excel renders Arabic and English perfectly
    output.write('\ufeff')
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        "Ticket Number", "Created At", "Requester Name", "Username", "Phone",
        "Source Chat", "Subject", "Status", "Priority", "Assigned Technician",
        "First Response At", "Closed At", "SLA Deadline", "SLA Status"
    ])
    
    for t in tickets:
        sla_status = "Breached" if t.get("sla_breached") else "Met / On Track"
        writer.writerow([
            t.get("ticket_number", ""),
            t.get("created_at", ""),
            t.get("user_name", ""),
            f"@{t['username']}" if t.get("username") else "",
            t.get("phone_number", ""),
            t.get("chat_title") or t.get("chat_type", ""),
            t.get("subject", ""),
            t.get("status", "").upper(),
            t.get("priority", "medium").upper(),
            t.get("assigned_to") or "Unassigned",
            t.get("first_response_at", ""),
            t.get("closed_at", ""),
            t.get("sla_deadline", ""),
            sla_status
        ])
        
    csv_content = output.getvalue()
    filename = f"IT_Helpdesk_Report_{start_date or 'all'}_to_{end_date or 'now'}.csv"
    
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# WebSocket for Real-time Updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
