from flask import Flask, render_template, request, jsonify
from datetime import datetime
from logic import evaluate_reminder_status

app = Flask(__name__)

# Track the latest event globally in memory for the dashboard live feed
latest_event_memory = "Waiting for events from ESP32..."

@app.route('/')
def dashboard():
    """Renders the main web dashboard."""
    return render_template('dashboard.html')

@app.route('/api/event', methods=['POST'])
def receive_esp32_event():
    """Endpoint where the ESP32 pushes hardware events via HTTP POST."""
    global latest_event_memory
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    device_id = data.get("device_id", "unknown_device")
    event_type = data.get("event_type")
    timestamp_str = data.get("timestamp", datetime.now().isoformat())
    medicine_id = data.get("medicine_id", 1)
    
    print(f"\n[API Event] Device: {device_id} | Type: {event_type} | Time: {timestamp_str}")
    
    # Evaluate state through logic.py
    response_state = evaluate_reminder_status(medicine_id, event_type, timestamp_str)
    
    # Update the global memory so /api/status can display it on the dashboard
    latest_event_memory = f"Event: {event_type} (State: {response_state})"
    
    return jsonify({
        "status": "success",
        "message": "Event recorded successfully",
        "state": response_state
    }), 200

@app.route('/api/status', methods=['GET'])
def get_system_status():
    """Provides current device status and recent event data to the dashboard."""
    return jsonify({
        "connection": "active",
        "device_status": "Online",
        "last_event": latest_event_memory,
        "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)