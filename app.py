from flask import Flask, render_template, request, jsonify
from datetime import datetime
from logic import evaluate_reminder_status
from database import initialize_database, get_connection, format_time

app = Flask(__name__)

# Initialize database tables and seed sample data on startup
initialize_database()

@app.route('/')
def dashboard():
    """Renders the main web dashboard."""
    return render_template('dashboard.html')

@app.route('/api/event', methods=['POST'])
def receive_esp32_event():
    """Endpoint where the ESP32 pushes hardware events via HTTP POST."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    device_id = data.get("device_id", "unknown_device")
    event_type = data.get("event_type")
    timestamp_str = data.get("timestamp", format_time(datetime.now()))
    medicine_id = data.get("medicine_id", 1)
    
    print(f"\n[API Event] Device: {device_id} | Type: {event_type} | Time: {timestamp_str}")
    
    # Evaluate state through logic.py
    response_state = evaluate_reminder_status(medicine_id, event_type, timestamp_str)
    
    # Save event into your team's SQLite database tables
    conn = get_connection()
    cursor = conn.cursor()
    
    # Find active reminder for this medicine_id, or create a fallback entry if needed
    cursor.execute("SELECT id FROM reminders WHERE medicine_id = ? ORDER BY id DESC LIMIT 1", (medicine_id,))
    row = cursor.fetchone()
    
    if row:
        reminder_id = row[0]
    else:
        cursor.execute("INSERT INTO reminders (medicine_id, reminder_time, status) VALUES (?, ?, ?)",
                       (medicine_id, timestamp_str, 'Pending'))
        conn.commit()
        reminder_id = cursor.lastrowid
        
    # Insert event log
    cursor.execute("INSERT INTO events (reminder_id, event_type, timestamp) VALUES (?, ?, ?)",
                   (reminder_id, event_type, timestamp_str))
                   
    # Update device status log
    cursor.execute("INSERT INTO device_status (status, last_seen) VALUES (?, ?)",
                   ("Online", timestamp_str))
                   
    conn.commit()
    conn.close()
    
    return jsonify({
        "status": "success",
        "message": "Event recorded and saved to team database successfully",
        "state": response_state
    }), 200

@app.route('/api/status', methods=['GET'])
def get_system_status():
    """Provides current device status and recent event data from the team database to the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT e.event_type, e.timestamp, r.status 
        FROM events e 
        JOIN reminders r ON e.reminder_id = r.id 
        ORDER BY e.id DESC LIMIT 1
    """)
    event_row = cursor.fetchone()
    conn.close()
    
    if event_row:
        last_event_str = f"Event: {event_row[0]} (Status: {event_row[2]})"
        last_sync = event_row[1]
    else:
        last_event_str = "Waiting for events from ESP32..."
        last_sync = format_time(datetime.now())

    return jsonify({
        "connection": "active",
        "device_status": "Online",
        "last_event": last_event_str,
        "last_sync": last_sync
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)