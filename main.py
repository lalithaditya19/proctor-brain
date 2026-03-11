from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles # NEW: Needed to serve images!
from typing import List
import time
import sqlite3
import os

app = FastAPI()

# --- 1. SETUP EVIDENCE FOLDER & DATABASE ---
if not os.path.exists('evidence'):
    os.makedirs('evidence')

# This tells the server: "Allow the web browser to see photos inside the 'evidence' folder"
app.mount("/evidence", StaticFiles(directory="evidence"), name="evidence")

conn = sqlite3.connect('exam_records.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        reason TEXT,
        image_file TEXT, 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()
print("🗄️ Database Ready (With Image Support)!")

# --- 2. THE WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- 3. ROUTES ---
# Add this right above your routes
active_student = "Unknown_Student"

# --- 1. UPDATE THE WEBSOCKET ROUTE ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global active_student  # Allows us to change the memory
    await manager.connect(websocket)
    try:
        while True: 
            data = await websocket.receive_text()
            # Listen for the frontend sending the login name
            if data.startswith("LOGIN:"):
                active_student = data.split(":")[1]
                print(f"🎓 STUDENT LOGGED IN: {active_student}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- 2. UPDATE THE VIOLATION TRIGGER ---
# Remove the old default 'student_id="Student_01"' from the parameters!
@app.get("/trigger-violation")
async def trigger_violation(reason: str, filename: str = "no_image"):
    global active_student
    print(f"🚨 LOGGED: {reason} | Photo: {filename} | Student: {active_student}")
    
    # Save the real student's name to the database
    cursor.execute("INSERT INTO violations (student_id, reason, image_file) VALUES (?, ?, ?)", (active_student, reason, filename))
    conn.commit()
    
    await manager.broadcast(f"SHOW_RED_BOX:{reason}")
    return {"status": "saved"}

# --- 4. THE EVIDENCE ROOM DASHBOARD ---
@app.get("/report", response_class=HTMLResponse)
async def view_report():
    cursor.execute("SELECT id, student_id, reason, image_file, timestamp FROM violations ORDER BY timestamp DESC")
    records = cursor.fetchall()
    
    html_content = """
    <html>
    <head>
        <title>Proctoring Evidence Room</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 40px; background-color: #f4f4f9;}
            h1 { color: #2d3748; }
            table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
            th, td { padding: 16px; text-align: left; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }
            th { background-color: #4a5568; color: white; }
            tr:hover { background-color: #f7fafc; }
            .evidence-img { width: 140px; border-radius: 6px; border: 2px solid #cbd5e0; }
        </style>
    </head>
    <body>
        <h1>🛡️ Official AI Evidence Room</h1>
        <table>
            <tr>
                <th>Log ID</th>
                <th>Student ID</th>
                <th>Violation</th>
                <th>Photographic Evidence</th>
                <th>Timestamp</th>
            </tr>
    """
    
    for row in records:
        # Load the image, or show text if missing
        img_html = f"<img src='/evidence/{row[3]}' class='evidence-img'/>" if row[3] != "no_image" else "<i>No photo captured</i>"
        
        html_content += f"""
            <tr>
                <td>#{row[0]}</td>
                <td><b>{row[1]}</b></td>
                <td style="color: #e53e3e; font-weight: bold;">{row[2]}</td>
                <td>{img_html}</td>
                <td style="color: #718096;">{row[4]}</td>
            </tr>
        """
        
    html_content += "</table></body></html>"
    return HTMLResponse(content=html_content)

@app.get("/clear-db")
async def clear_database():
    cursor.execute("DELETE FROM violations")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='violations'")
    conn.commit()
    return {"status": "Database wiped clean!"}