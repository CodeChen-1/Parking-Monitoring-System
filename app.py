from flask import Flask, render_template, Response, send_file, jsonify, request, redirect, url_for, session
import cv2
import easyocr
from ultralytics import YOLO
from datetime import datetime, timedelta
import time
import sqlite3
import csv
import io
from functools import wraps
import os
from waitress import serve
from collections import Counter
import json
import socket

app = Flask(__name__)
app.secret_key = 'secret'

ip_in = 0 #'http://192.168.0.101:8080/video'  
ip_out = 0 # 'http://192.168.0.101:8080/video'  

recent_plates = []

# Load models
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(BASE_DIR, 'best.pt')
model = YOLO(model_path)
reader = easyocr.Reader(['en'])

# Webcam IN & OUT
cap_in = cv2.VideoCapture(ip_in)
cap_out = cv2.VideoCapture(ip_out)
if not cap_in.isOpened():
    print("Error: Could not open IN video stream.")
    exit()
if not cap_out.isOpened():
    print("Error: Could not open OUT video stream.")
    exit()
time.sleep(2.0)

# SQLite Setup
DB_PATH = 'database.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT NOT NULL,
            in_time TEXT NOT NULL,
            out_time TEXT,
            duration TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()

def read_log():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM logs")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_log(plate, in_time, is_exit=False):
    conn = get_db()
    cursor = conn.cursor()
    if is_exit:
        cursor.execute("SELECT * FROM logs WHERE plate=? AND out_time IS NULL", (plate,))
        row = cursor.fetchone()
        if row:
            in_dt = datetime.strptime(row['in_time'], "%Y-%m-%d %H:%M:%S")
            out_dt = datetime.strptime(in_time, "%Y-%m-%d %H:%M:%S")
            duration = str(out_dt - in_dt)
            cursor.execute("UPDATE logs SET out_time=?, duration=? WHERE id=?", (in_time, duration, row['id']))
    else:
        cursor.execute("INSERT INTO logs (plate, in_time, out_time, duration) VALUES (?, ?, NULL, NULL)", (plate, in_time))
    conn.commit()
    conn.close()

def detect_and_log_dual(frame, is_exit=False):
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        print("Skipping invalid frame before detection.")
        return frame, []

    frame = cv2.resize(frame, (640, 480))
    frame_h, frame_w = frame.shape[:2]
    box_width = 250
    box_height = 120
    box_x1 = frame_w // 2 - box_width // 2
    box_y1 = frame_h - box_height - 20
    box_x2 = box_x1 + box_width
    box_y2 = box_y1 + box_height

    cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 255), 3)
    cv2.putText(frame, "Detection Zone", (box_x1, box_y1 - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    detected_plates = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        results = model(frame)[0]
    except Exception as e:
        print(f"YOLO model failed: {e}")
        return frame, []
    for box in results.boxes:
        conf = float(box.conf[0])
        if conf > 0.5:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            if box_x1 <= cx <= box_x2 and box_y1 <= cy <= box_y2:
                cropped = frame[y1:y2, x1:x2]
                ocr_results = reader.readtext(cropped)

                if ocr_results:
                    print("OCR Results:", ocr_results)
                    best_result = max(ocr_results, key=lambda r: r[2])
                    _, text, prob = best_result

                    if text not in detected_plates:
                        update_log(text, current_time, is_exit)
                        detected_plates.append(text)

                        # Append to notification list
                        recent_plates.append({"plate": text, "time": current_time})
                        print(f"Detected plate: {text}")

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                    cv2.putText(frame, text, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    return frame, detected_plates

def gen_frames_dual(cap, is_exit=False):
    last_detection_time = 0
    detection_interval = 5
    frame_count = 0
    frame_skip = 2  # Only process every 2nd frame

    while True:
        ret, frame = cap.read()
        if not ret or frame is None or frame.size == 0:
            print("Warning: Empty or invalid frame.")
            time.sleep(0.5)
            continue

        frame_count += 1
        if frame_count % frame_skip != 0:
            continue  # Skip this frame to reduce load

        current_time = time.time()

        if current_time - last_detection_time >= detection_interval:
            frame, _ = detect_and_log_dual(frame, is_exit=is_exit)
            last_detection_time = current_time
        else:
            frame = cv2.resize(frame, (640, 480))
            # Draw detection zone box
            box_width = 250
            box_height = 120
            frame_h, frame_w = frame.shape[:2]
            box_x1 = frame_w // 2 - box_width // 2
            box_y1 = frame_h - box_height - 20
            box_x2 = box_x1 + box_width
            box_y2 = box_y1 + box_height
            cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 255), 3)
            cv2.putText(frame, "Detection Zone", (box_x1, box_y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def clear_log_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM logs")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
    conn.commit()
    conn.close()


# ---------------------- ROUTES ----------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user'] = username
            return redirect(url_for('live'))
        else:
            return render_template('login.html', error='Invalid credentials', hide_nav=True)
    return render_template('login.html', hide_nav=True)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/')
def home_redirect():
    return redirect(url_for('live'))

@app.route('/logs')
@login_required
def logs():
    data = read_log()
    return render_template('logs.html', data=data)

@app.route('/live')
@login_required
def live():
    return render_template('live.html')

@app.route('/current-count')
def current_count():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM logs WHERE out_time IS NULL")
    count = cursor.fetchone()[0]

    conn.close()
    return jsonify({'count': count})

@app.route('/analysis')
@login_required
def analysis():
    return render_template('analysis.html')

@app.route('/analysis-data')
def analysis_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    today = datetime.today()

    cursor.execute("""
        SELECT strftime('%Y-%m-%d', in_time) as day, COUNT(*) 
        FROM logs 
        WHERE date(in_time) >= date('now', '-6 days') 
        GROUP BY day
    """)
    weekly_rows = dict(cursor.fetchall())
    weekly = [(day.strftime('%a'), weekly_rows.get(day.strftime('%Y-%m-%d'), 0)) 
          for day in [today - timedelta(days=i) for i in reversed(range(7))]]

    cursor.execute("""
        SELECT strftime('%Y-%m-%d', in_time) as day, COUNT(*) 
        FROM logs 
        WHERE date(in_time) >= date('now', '-30 days') 
        GROUP BY day
    """)
    monthly_rows = dict(cursor.fetchall())
    monthly = [(day.strftime('%b %d'), monthly_rows.get(day.strftime('%Y-%m-%d'), 0)) 
           for day in [today - timedelta(days=i) for i in reversed(range(31))]]

    cursor.execute("""
        SELECT strftime('%Y-%m', in_time) as month, COUNT(*) 
        FROM logs 
        WHERE date(in_time) >= date('now', '-11 months') 
        GROUP BY month
    """)
    yearly_rows = dict(cursor.fetchall())
    yearly_labels = []
    for i in reversed(range(12)):
        month_dt = (today.replace(day=1) - timedelta(days=30*i))
        key = month_dt.strftime('%Y-%m')  
        label = month_dt.strftime('%b')  
        yearly_labels.append((label, key))
    yearly = [(label, yearly_rows.get(key, 0)) for label, key in yearly_labels]

    conn.close()

    return jsonify({
        'weekly': weekly,
        'monthly': monthly,
        'yearly': yearly
    })

@app.route('/video_feed_in')
@login_required
def video_feed_in():
    return Response(gen_frames_dual(cap_in, is_exit=False), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_out')
@login_required
def video_feed_out():
    return Response(gen_frames_dual(cap_out, is_exit=True), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_notifications')
@login_required
def get_notifications():
    global recent_plates
    data = recent_plates.copy()
    recent_plates = []  # Clear after sending
    return jsonify(data)

@app.route('/get_log')
@login_required
def get_log():
    data = read_log()
    return jsonify(data)

@app.route('/download')
@login_required
def download():
    logs = read_log()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Plate', 'In Time', 'Out Time', 'Duration'])
    for row in logs:
        writer.writerow([
            row.get('plate', ''),
            row.get('in_time', ''),
            row.get('out_time', ''),
            row.get('duration', '')
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='vehicle_logs.csv'
    )

@app.route('/clear_logs', methods=["POST"])
@login_required
def clear_logs():
    try:
        clear_log_db()
        return redirect(url_for('logs'))  # redirect instead of JSON
    except Exception as e:
        return render_template('error.html', message=str(e))

# ---------------------- MAIN ----------------------

if __name__ == '__main__':
    init_db()
    add_user('admin', 'password')
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print("Access your app at: http://" + local_ip + ":5000")
    serve(app, host='0.0.0.0', port=5000)
