from flask import Flask, render_template, request, jsonify
from datetime import datetime
from logic import evaluate_reminder_status
from database import initialize_database, get_connection, format_time

app = Flask(__name__)
initialize_database()

# Day codes matching JavaScript's convention (Mon=0 ... Sun=6)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def today_str():
    """Today's date as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")

def today_code():
    """Today's short day name e.g. 'Mon', 'Tue'."""
    return DAYS[datetime.now().weekday()]


def ensure_today_reminders(cursor):
    """Ensure today's reminders exist in the DB for all medicines scheduled for today."""
    today = today_str()
    day_code = today_code()
    cursor.execute("SELECT id, time, days FROM medicines")
    for med_id, med_time, med_days in cursor.fetchall():
        days_list = [d.strip() for d in med_days.split(",") if d.strip()]
        if day_code in days_list:
            cursor.execute(
                "SELECT id FROM reminders WHERE medicine_id=? AND reminder_time LIKE ?",
                (med_id, today + "%")
            )
            if not cursor.fetchone():
                reminder_time = f"{today} {med_time}:00"
                cursor.execute(
                    "INSERT INTO reminders (medicine_id, reminder_time, status) VALUES (?,?,?)",
                    (med_id, reminder_time, "pending")
                )


# ── Main page ────────────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    """Serve the main dashboard page."""
    return render_template('dashboard.html')


# ── Medicines CRUD ────────────────────────────────────────────────────────────

@app.route('/api/medicines', methods=['GET'])
def get_medicines():
    """Return all medicines with today's reminder status."""
    conn = get_connection()
    cursor = conn.cursor()
    ensure_today_reminders(cursor)
    mark_expired_reminders(cursor)

    # For each medicine, pick the most actionable status for today.
    # Priority: pending (most urgent) → missed → completed
    cursor.execute("""
        SELECT m.id, m.name, m.dosage, m.time, m.days,
               COALESCE(
                   (SELECT r.status FROM reminders r
                    WHERE r.medicine_id = m.id
                      AND r.reminder_time LIKE ?
                    ORDER BY CASE r.status
                        WHEN 'pending'   THEN 0
                        WHEN 'missed'    THEN 1
                        WHEN 'completed' THEN 2
                        ELSE 3
                    END
                    LIMIT 1),
                   'pending'
               ) AS today_status
        FROM medicines m
        ORDER BY m.time
    """, (today_str() + "%",))

    medicines = []
    for row in cursor.fetchall():
        medicines.append({
            "id":     row[0],
            "name":   row[1],
            "dose":   row[2],
            "time":   row[3],
            "days":   row[4].split(",") if row[4] else [],
            "status": row[5]
        })

    conn.commit()
    conn.close()
    return jsonify(medicines)


def mark_expired_reminders(cursor):
    """Mark due reminders missed after the saved grace period."""
    row = cursor.execute(
        "SELECT missed_window FROM device_status ORDER BY id DESC LIMIT 1"
    ).fetchone()
    window = int(row[0]) if row else 60
    cutoff = format_time(datetime.now())
    expired = cursor.execute(
        "SELECT id FROM reminders WHERE status='pending' AND reminder_time <= datetime(?, ?)",
        (cutoff, f'-{window} seconds')
    ).fetchall()
    for (reminder_id,) in expired:
        cursor.execute("UPDATE reminders SET status='missed' WHERE id=?", (reminder_id,))
        # Avoid duplicate reminder_missed events
        cursor.execute(
            "SELECT id FROM events WHERE reminder_id=? AND event_type='reminder_missed'",
            (reminder_id,)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO events (reminder_id, event_type, timestamp) VALUES (?, 'reminder_missed', ?)",
                (reminder_id, cutoff)
            )


@app.route('/api/medicines', methods=['POST'])
def add_medicine():
    """Add a new medicine and create today's reminder if today is a scheduled day."""
    data = request.get_json()
    error = validate_medicine(data)
    if error:
        return jsonify({"error": error}), 400

    name     = data['name']
    dose     = data.get('dose', '')
    time_str = data.get('time', '08:00')
    days     = data.get('days', DAYS)
    days_str = ",".join(days)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO medicines (name, dosage, time, days, created_at) VALUES (?,?,?,?,?)",
        (name, dose, time_str, days_str, format_time(datetime.now()))
    )
    medicine_id = cursor.lastrowid

    # Create today's reminder if today is in the scheduled days
    if today_code() in days:
        reminder_time = today_str() + " " + time_str + ":00"
        cursor.execute(
            "INSERT INTO reminders (medicine_id, reminder_time, status) VALUES (?,?,?)",
            (medicine_id, reminder_time, "pending")
        )

    conn.commit()
    conn.close()
    return jsonify({"id": medicine_id, "message": "Medicine added"}), 201


@app.route('/api/medicines/<int:medicine_id>', methods=['PUT'])
def update_medicine(medicine_id):
    """Update a medicine's details and adjust today's reminder if needed."""
    data = request.get_json()
    error = validate_medicine(data)
    if error:
        return jsonify({"error": error}), 400

    name     = data['name']
    dose     = data.get('dose', '')
    time_str = data.get('time', '08:00')
    days     = data.get('days', DAYS)
    days_str = ",".join(days)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE medicines SET name=?, dosage=?, time=?, days=? WHERE id=?",
        (name, dose, time_str, days_str, medicine_id)
    )

    # Update, create, or remove today's pending reminder to match the schedule.
    if today_code() in days:
        reminder_time = today_str() + " " + time_str + ":00"
        cursor.execute(
            "SELECT id FROM reminders WHERE medicine_id=? AND reminder_time LIKE ?",
            (medicine_id, today_str() + "%")
        )
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE reminders SET reminder_time=? WHERE id=?", (reminder_time, row[0]))
        else:
            cursor.execute(
                "INSERT INTO reminders (medicine_id, reminder_time, status) VALUES (?,?,?)",
                (medicine_id, reminder_time, "pending")
            )
    else:
        cursor.execute(
            "DELETE FROM reminders WHERE medicine_id=? AND reminder_time LIKE ? AND status='pending'",
            (medicine_id, today_str() + "%")
        )

    conn.commit()
    conn.close()
    return jsonify({"message": "Medicine updated"})


def validate_medicine(data):
    """Check medicine fields before they are saved."""
    if not isinstance(data, dict) or not str(data.get("name", "")).strip():
        return "Name is required"
    if not str(data.get("dose", "")).strip():
        return "Dose is required"
    try:
        datetime.strptime(data.get("time", ""), "%H:%M")
    except (TypeError, ValueError):
        return "Time must use HH:MM format"
    days = data.get("days")
    if not isinstance(days, list) or not days or any(day not in DAYS for day in days):
        return "Select at least one valid day"
    return None


@app.route('/api/medicines/<int:medicine_id>', methods=['DELETE'])
def delete_medicine(medicine_id):
    """Delete a medicine along with all its reminders and events."""
    conn = get_connection()
    cursor = conn.cursor()

    # Delete events first (they reference reminders)
    cursor.execute(
        "DELETE FROM events WHERE reminder_id IN (SELECT id FROM reminders WHERE medicine_id=?)",
        (medicine_id,)
    )
    cursor.execute("DELETE FROM reminders WHERE medicine_id=?", (medicine_id,))
    cursor.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))

    conn.commit()
    conn.close()
    return jsonify({"message": "Medicine deleted"})


# ── Events ────────────────────────────────────────────────────────────────────

@app.route('/api/events', methods=['GET'])
def get_events():
    """Return recent events formatted for the frontend dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.id, e.event_type, e.timestamp, m.name
        FROM events e
        JOIN reminders r ON e.reminder_id = r.id
        JOIN medicines m ON r.medicine_id = m.id
        ORDER BY e.id DESC
        LIMIT 50
    """)

    # Maps the ESP32 event_type to what the frontend displays
    type_map = {
        "reminder_due":        ("triggered",    "Reminder activated", "Due"),
        "compartment_opened":  ("opening",      "Compartment opened", "Opening detected"),
        "button_acknowledged": ("acknowledged", "Button pressed",     "Acknowledged"),
        "reminder_missed":     ("missed",       "Reminder missed",    "Missed"),
    }

    events = []
    for event_id, event_type, timestamp, medicine_name in cursor.fetchall():
        # Extract HH:MM from "YYYY-MM-DD HH:MM:SS"
        time_part = timestamp[11:16] if len(timestamp) >= 16 else "--:--"
        frontend_type, label, status = type_map.get(event_type, ("triggered", event_type, "Unknown"))
        events.append({
            "id":       event_id,
            "time":     time_part,
            "medicine": medicine_name,
            "type":     frontend_type,
            "label":    label,
            "status":   status
        })

    conn.close()
    return jsonify(events)


# ── ESP32 event receiver ──────────────────────────────────────────────────────

@app.route('/api/event', methods=['POST'])
def receive_esp32_event():
    """Endpoint where the ESP32 pushes hardware events via HTTP POST."""
    data = request.get_json()
    allowed_events = {"reminder_due", "compartment_opened", "button_acknowledged", "reminder_missed"}
    if not isinstance(data, dict) or data.get("event_type") not in allowed_events:
        return jsonify({"error": "Invalid JSON payload"}), 400

    device_id    = data.get("device_id", "unknown_device")
    event_type   = data.get("event_type")
    timestamp_str = data.get("timestamp", format_time(datetime.now()))
    medicine_id  = data.get("medicine_id")
    if not isinstance(medicine_id, int):
        return jsonify({"error": "A valid medicine_id is required"}), 400

    print(f"\n[ESP32] Device: {device_id} | Event: {event_type} | Time: {timestamp_str}")

    # Evaluate the event (pure logic, no DB writes)
    response_state = evaluate_reminder_status(medicine_id, event_type, timestamp_str)

    conn = get_connection()
    cursor = conn.cursor()

    # Find today's reminder for this medicine, or create one if it doesn't exist
    cursor.execute(
        "SELECT id FROM reminders WHERE medicine_id=? AND reminder_time LIKE ? ORDER BY id DESC LIMIT 1",
        (medicine_id, today_str() + "%")
    )
    row = cursor.fetchone()

    if row:
        reminder_id = row[0]
    else:
        cursor.execute(
            "INSERT INTO reminders (medicine_id, reminder_time, status) VALUES (?,?,?)",
            (medicine_id, timestamp_str, "pending")
        )
        conn.commit()
        reminder_id = cursor.lastrowid

    # Update reminder status based on the event received
    if event_type in ("button_acknowledged", "compartment_opened"):
        cursor.execute("UPDATE reminders SET status='completed' WHERE id=?", (reminder_id,))
    elif event_type == "reminder_missed":
        cursor.execute("UPDATE reminders SET status='missed' WHERE id=?", (reminder_id,))

    # Log the event (avoid duplicate consecutive missed events)
    if event_type == "reminder_missed":
        cursor.execute(
            "SELECT id FROM events WHERE reminder_id=? AND event_type='reminder_missed'",
            (reminder_id,)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO events (reminder_id, event_type, timestamp) VALUES (?,?,?)",
                (reminder_id, event_type, timestamp_str)
            )
    else:
        cursor.execute(
            "INSERT INTO events (reminder_id, event_type, timestamp) VALUES (?,?,?)",
            (reminder_id, event_type, timestamp_str)
        )

    # Update device status (single row — update if exists, insert if not)
    cursor.execute("UPDATE device_status SET status='Online', last_seen=?", (timestamp_str,))
    if cursor.rowcount == 0:
        cursor.execute("INSERT INTO device_status (status, last_seen) VALUES ('Online', ?)", (timestamp_str,))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": "Event recorded",
        "state": response_state
    }), 200


# ── System status ─────────────────────────────────────────────────────────────

@app.route('/api/status', methods=['GET'])
def get_system_status():
    """Returns device connection status and latest event for the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    ensure_today_reminders(cursor)
    mark_expired_reminders(cursor)
    conn.commit()

    cursor.execute("SELECT status, last_seen FROM device_status ORDER BY id DESC LIMIT 1")
    device_row = cursor.fetchone()

    cursor.execute("""
        SELECT e.event_type, m.name
        FROM events e
        JOIN reminders r ON e.reminder_id = r.id
        JOIN medicines m ON r.medicine_id = m.id
        ORDER BY e.id DESC LIMIT 1
    """)
    event_row = cursor.fetchone()
    conn.close()

    device_status = device_row[0] if device_row else "Offline"
    last_seen     = device_row[1] if device_row else format_time(datetime.now())
    last_event    = f"{event_row[1]}: {event_row[0]}" if event_row else "No events yet"

    return jsonify({
        "device_status": device_status,
        "last_event":    last_event,
        "last_sync":     last_seen
    })


@app.route('/api/settings', methods=['GET'])
def get_settings():
    conn = get_connection()
    row = conn.execute("SELECT missed_window FROM device_status ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return jsonify({"missedWindow": int(row[0]) if row else 60})


@app.route('/api/settings', methods=['PUT'])
def update_settings():
    data = request.get_json(silent=True)
    try:
        seconds = int(data.get("missedWindow"))
    except (AttributeError, TypeError, ValueError):
        return jsonify({"error": "Enter a valid missed-reminder window"}), 400
    if not 10 <= seconds <= 3600:
        return jsonify({"error": "Window must be between 10 and 3600 seconds"}), 400
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE device_status SET missed_window=?", (seconds,))
    if cursor.rowcount == 0:
        cursor.execute(
            "INSERT INTO device_status (status, last_seen, missed_window) VALUES ('Offline', ?, ?)",
            (format_time(datetime.now()), seconds)
        )
    conn.commit()
    conn.close()
    return jsonify({"missedWindow": seconds})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
