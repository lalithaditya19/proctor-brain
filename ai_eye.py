import cv2
import mediapipe as mp
import requests
import time
import threading
import os
from ultralytics import YOLO
from AppKit import NSWorkspace 

# 1. Setup Folders for Evidence
if not os.path.exists('evidence'):
    os.makedirs('evidence')

# 2. Initialize Models
phone_model = YOLO('yolov8s.pt') # Upgraded to a smarter model! 
from mediapipe.python.solutions import face_mesh as mp_face_mesh
face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True, min_detection_confidence=0.7)

SERVER_URL = "http://127.0.0.1:8000/trigger-violation"
EXAM_APP_NAME = "Electron" 

# --- BALANCED & TIGHTENED BOUNDARIES ---
# Perfectly balanced left/right so one side isn't harder to trigger than the other
HEAD_LEFT_BOUND, HEAD_RIGHT_BOUND = 0.45, 0.55 
EYE_LOW, EYE_HIGH = 0.42, 0.58 # Tighter threshold for quick eye darts
MOUTH_LIMIT = 0.04 

# State
look_away_start_time = None
strike_already_sent = False
frame_counter = 0     # NEW: Used to optimize YOLO
phone_found = False   # NEW: Cache the YOLO result

def send_alert_background(reason, filename):
    """Sends the reason AND the photo filename to the database"""
    try:
        requests.get(SERVER_URL, params={"reason": reason, "filename": filename}, timeout=1)
    except:
        pass

def save_evidence(image, reason):
    """Saves photo and returns the exact filename to send to the server"""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{reason}_{timestamp}.jpg" # Just the name
    filepath = f"evidence/{filename}"      # Where it goes
    cv2.imwrite(filepath, image)
    return filename # Hand it back to the AI loop!

def check_window_lockdown():
    active_app = NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()
    safe_apps = [EXAM_APP_NAME, "Python", "Terminal", "python3", "iTerm2", "Code"]
    if active_app not in safe_apps:
        return True, active_app
    return False, active_app

print("👁️ Stealth AI Proctoring started in background... (Press CTRL+C in terminal to stop)")
cap = cv2.VideoCapture(0)

try:
    while cap.isOpened():
        success, image = cap.read()
        if not success: break
        
        frame_counter += 1

        image = cv2.flip(image, 1)
        evidence_frame = image.copy()
        
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        is_tabbed_out, app_name = check_window_lockdown()
        
        # 🚀 OPTIMIZATION: Only run heavy YOLO model every 5 frames to stop lag!
        if frame_counter % 5 == 0:
            # conf=0.15 makes the AI hyper-paranoid. It will catch hidden phones!
            yolo_results = phone_model(image, stream=True, verbose=False, conf=0.15)
            phone_found = any(int(box.cls[0]) == 67 for r in yolo_results for box in r.boxes)

        results = face_mesh.process(rgb_image)
        cheating_now = False
        reason = "Focused"

        if is_tabbed_out:
            cheating_now, reason = True, f"ALT-TAB_{app_name}"
        elif phone_found:
            cheating_now, reason = True, "PHONE_DETECTED"
        elif results.multi_face_landmarks:
            mesh = results.multi_face_landmarks[0].landmark
            nose = mesh[1]
            l_iris, l_out, l_in = mesh[468], mesh[33], mesh[133]
            r_iris, r_out, r_in = mesh[473], mesh[362], mesh[263]
            avg_gaze = ((l_iris.x - l_out.x)/(l_in.x - l_out.x) + (r_iris.x - r_out.x)/(r_in.x - r_out.x)) / 2
            mouth_dist = abs(mesh[13].y - mesh[14].y)

            # Unified warning texts so it looks professional in the UI
            if nose.x < HEAD_LEFT_BOUND: cheating_now, reason = True, "HEAD_TURNED"
            elif nose.x > HEAD_RIGHT_BOUND: cheating_now, reason = True, "HEAD_TURNED"
            elif avg_gaze < EYE_LOW: cheating_now, reason = True, "EYES_AWAY"
            elif avg_gaze > EYE_HIGH: cheating_now, reason = True, "EYES_AWAY"
            elif mouth_dist > MOUTH_LIMIT: cheating_now, reason = True, "TALKING"
        else:
            cheating_now, reason = True, "FACE_MISSING"

        # --- ALERT & EVIDENCE LOGIC ---
        if cheating_now:
            if look_away_start_time is None: look_away_start_time = time.time()
            
            # HYPER-SENSITIVE TIMER: 0 seconds for OS/Phone, 0.4 seconds for head/eyes
            limit = 0.0 if "PHONE" in reason or "ALT-TAB" in reason else 0.4
            
            if (time.time() - look_away_start_time) > limit and not strike_already_sent:
                # 1. Save the Photo FIRST so we have the filename
                saved_file = save_evidence(evidence_frame, reason)
                
                # 2. Alert the Server with the reason AND the file
                threading.Thread(target=send_alert_background, args=(reason, saved_file)).start()
                
                strike_already_sent = True
        else:
            look_away_start_time = None
            strike_already_sent = False

        # 🛑 Visual UI completely removed for maximum CPU speed!

except KeyboardInterrupt:
    print("\n🛑 AI Proctoring Shut Down.")

cap.release()
cv2.destroyAllWindows()