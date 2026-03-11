from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
                pass

manager = ConnectionManager()
violations = [] 
active_student = "Unknown_Student"

@app.get("/")
def home():
    return {"status": "Proctor Brain is Online", "active_student": active_student}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global active_student
    await manager.connect(websocket)
    try:
        while True: 
            data = await websocket.receive_text()
            if data.startswith("LOGIN:"):
                active_student = data.split(":")[1]
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/trigger-violation")
async def trigger_violation(reason: str, filename: str = "no_image"):
    global active_student
    
    # 1. BROADCAST THE SIGNAL
    # This sends "HIDE", "SHOW:reason", or "TERMINATE:reason" to the App
    await manager.broadcast(reason)
    
    # 2. LOG TO EVIDENCE ROOM (Only if it's not a 'HIDE' command)
    if reason != "HIDE":
        violations.append({
            "student_id": active_student,
            "reason": reason,
            "image_file": filename,
            "timestamp": time.strftime("%H:%M:%S")
        })
    
    return {"status": "signal_sent"}

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
        html_content += f"<tr><td><b>{v['student_id']}</b></td><td class='red'>{v['reason']}</td><td>{v['timestamp']}</td></tr>"
    html_content += "</table></body></html>"
    return HTMLResponse(content=html_content)