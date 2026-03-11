from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware # REQUIRED FOR CLOUD
from typing import List
import os

app = FastAPI()

# --- 1. THE SECURITY KEY (CORS) ---
# This allows your Mac to talk to the Render Cloud
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. WEBSOCKET & DATA STORAGE ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass # Prevent one broken connection from stopping the rest

manager = ConnectionManager()
violations = [] # Using a list for Render (SQLite gets wiped on restart)
active_student = "Unknown_Student"

@app.get("/")
def home():
    return {"status": "Proctor Brain is Online", "active_student": active_student}

# --- 3. ROUTES ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global active_student
    await manager.connect(websocket)
    try:
        while True: 
            data = await websocket.receive_text()
            if data.startswith("LOGIN:"):
                active_student = data.split(":")[1]
                print(f"🎓 STUDENT LOGGED IN: {active_student}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/trigger-violation")
async def trigger_violation(reason: str, filename: str = "no_image"):
    global active_student
    print(f"🚨 LOGGED: {reason} | Student: {active_student}")
    
    # Save violation to memory
    violations.append({
        "student_id": active_student,
        "reason": reason,
        "image_file": filename,
        "timestamp": "Just Now"
    })
    
    # THIS SENDS THE RED BOX SIGNAL TO ELECTRON
    await manager.broadcast(f"SHOW_RED_BOX:{reason}")
    return {"status": "saved"}

@app.get("/report", response_class=HTMLResponse)
async def view_report():
    html_content = """
    <html>
    <head>
        <title>Proctoring Evidence Room</title>
        <style>
            body { font-family: sans-serif; margin: 40px; background-color: #f4f4f9;}
            table { width: 100%; border-collapse: collapse; background: white; }
            th, td { padding: 15px; border-bottom: 1px solid #ddd; text-align: left; }
            th { background-color: #333; color: white; }
            .red { color: red; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🛡️ Official AI Evidence Room</h1>
        <table>
            <tr><th>Student ID</th><th>Violation</th><th>Timestamp</th></tr>
    """
    
    for v in reversed(violations):
        html_content += f"""
            <tr>
                <td><b>{v['student_id']}</b></td>
                <td class="red">{v['reason']}</td>
                <td>{v['timestamp']}</td>
            </tr>
        """
        
    html_content += "</table></body></html>"
    return HTMLResponse(content=html_content)

@app.get("/clear-db")
async def clear_database():
    global violations
    violations = []
    return {"status": "List wiped clean!"}