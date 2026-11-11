from datetime import datetime, timedelta

# Configuration window: 60 seconds (matches server and settings default)
DEMO_WINDOW_SECONDS = 60

def evaluate_reminder_status(medicine_id, event_type, timestamp_str):
    """Evaluates state transitions based on incoming ESP32 events and time windows."""
    try:
        event_time = datetime.fromisoformat(timestamp_str.replace(" ", "T"))
    except ValueError:
        event_time = datetime.now()

    if event_type == "reminder_due":
        expiry_time = event_time + timedelta(seconds=DEMO_WINDOW_SECONDS)
        print(f"[Logic] Reminder DUE for medicine {medicine_id} at {event_time}. Expires at {expiry_time}")
        return "Due"

    elif event_type == "compartment_opened":
        print(f"[Logic] Compartment OPENED for medicine {medicine_id} at {event_time}")
        return "Opening Detected"

    elif event_type == "button_acknowledged":
        print(f"[Logic] Button ACKNOWLEDGED for medicine {medicine_id} at {event_time}")
        return "Acknowledged"

    elif event_type == "reminder_missed":
        print(f"[Logic] Reminder MISSED for medicine {medicine_id} at {event_time}")
        return "Missed"

    return "Unknown"