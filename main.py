from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List

app = FastAPI()

# Allow your Electron app to talk to the Cloud
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global store for violations and current student
violations = []
current_student = "Unknown"

@app.get("/")
def home():
    return {"status": "Proctor Brain is Online"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global current_student
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("LOGIN:"):
                current_student = data.split(":")[1]
                print(f"Student Logged In: {current_student}")
            elif data == "EXAM_SUBMITTED":
                print(f"Exam finished for {current_student}")
    except WebSocketDisconnect:
        print("Client disconnected")

@app.get("/trigger-violation")
def trigger_violation(reason: str, filename: str):
    # Store the violation with the student's name and the photo link
    entry = {
        "student": current_student,
        "reason": reason,
        "photo": filename
    }
    violations.append(entry)
    return {"status": "logged", "entry": entry}

@app.get("/report")
def get_report():
    # This is your "Evidence Room" dashboard
    html_content = "<h1>Live Exam Evidence Room</h1><table border='1'><tr><th>Student</th><th>Violation</th><th>Evidence</th></tr>"
    for v in violations:
        html_content += f"<tr><td>{v['student']}</td><td>{v['reason']}</td><td>{v['photo']}</td></tr>"
    html_content += "</table>"
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)