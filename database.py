"""SQLite database setup for Medimate (smart medicine reminder)."""

import os
import sqlite3
from datetime import datetime, timedelta

DB_NAME = "medimate.db"
FOLDER = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(FOLDER, DB_NAME)

ALL_DAYS = "Mon,Tue,Wed,Thu,Fri,Sat,Sun"


def format_time(value):
    """Turn a datetime into a readable text timestamp."""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def get_connection(db_path=DB_PATH):
    """Open the SQLite database with foreign key support enabled."""
    connection = sqlite3.connect(db_path, timeout=10)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables(connection):
    """Create all tables if they don't already exist."""
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            dosage     TEXT NOT NULL,
            time       TEXT NOT NULL DEFAULT '08:00',
            days       TEXT NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id   INTEGER NOT NULL,
            reminder_time TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_id INTEGER NOT NULL,
            event_type  TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            FOREIGN KEY (reminder_id) REFERENCES reminders(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_status (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            status         TEXT NOT NULL,
            last_seen      TEXT NOT NULL,
            missed_window  INTEGER NOT NULL DEFAULT 60
        )
    """)

    connection.commit()


def add_missing_columns(connection):
    """Add new columns to existing tables in case of a partial upgrade."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA table_info(medicines)")
    existing = [row[1] for row in cursor.fetchall()]
    if "time" not in existing:
        cursor.execute("ALTER TABLE medicines ADD COLUMN time TEXT NOT NULL DEFAULT '08:00'")
    if "days" not in existing:
        cursor.execute("ALTER TABLE medicines ADD COLUMN days TEXT NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'")

    cursor.execute("PRAGMA table_info(device_status)")
    device_columns = [row[1] for row in cursor.fetchall()]
    if "missed_window" not in device_columns:
        cursor.execute("ALTER TABLE device_status ADD COLUMN missed_window INTEGER NOT NULL DEFAULT 60")

    # Preserve a value saved by the earlier settings-table version, then remove that table.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
    if cursor.fetchone():
        cursor.execute("SELECT value FROM settings WHERE name='missed_window'")
        saved = cursor.fetchone()
        if saved:
            cursor.execute("SELECT COUNT(*) FROM device_status")
            if cursor.fetchone()[0]:
                cursor.execute("UPDATE device_status SET missed_window=?", (int(saved[0]),))
            else:
                cursor.execute(
                    "INSERT INTO device_status (status, last_seen, missed_window) VALUES ('Offline', ?, ?)",
                    (format_time(datetime.now()), int(saved[0]))
                )
        cursor.execute("DROP TABLE settings")
    connection.commit()


def normalize_statuses(connection):
    """Make sure all reminder statuses use the lowercase format the frontend expects."""
    cursor = connection.cursor()
    cursor.execute("UPDATE reminders SET status = 'completed' WHERE status = 'Taken'")
    cursor.execute("UPDATE reminders SET status = 'pending'   WHERE status = 'Pending'")
    cursor.execute("UPDATE reminders SET status = 'missed'    WHERE status = 'Missed'")
    connection.commit()


def seed_sample_data(connection):
    """Add sample medicines and reminders only when the medicines table is empty."""
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM medicines")
    if cursor.fetchone()[0] > 0:
        return  # Data already exists — skip seeding

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    mwf = "Mon,Wed,Fri,Sun"

    medicines = [
        ("Paracetamol",        "500mg",     "08:00", ALL_DAYS, format_time(now)),
        ("Vitamin D3",         "1000 IU",   "09:00", ALL_DAYS, format_time(now - timedelta(days=2))),
        ("Probiotics capsule", "1 capsule", "07:30", ALL_DAYS, format_time(now - timedelta(days=5))),
        ("Omega-3 Fish Oil",   "1000mg",    "13:00", ALL_DAYS, format_time(now - timedelta(days=1))),
        ("Calcium Tablet",     "600mg",     "21:30", mwf,      format_time(now - timedelta(hours=8))),
        ("Amoxicillin",        "250mg",     "08:00", ALL_DAYS, format_time(now - timedelta(days=3))),
        ("Multivitamin",       "1 tablet",  "08:30", ALL_DAYS, format_time(now - timedelta(days=7))),
    ]
    cursor.executemany(
        "INSERT INTO medicines (name, dosage, time, days, created_at) VALUES (?,?,?,?,?)",
        medicines
    )
    connection.commit()
    print(f"[Seed] Inserted {len(medicines)} medicines.")

    # Build name → id lookup
    cursor.execute("SELECT id, name FROM medicines")
    ids = {row[1]: row[0] for row in cursor.fetchall()}

    # Create today's reminders with realistic statuses
    reminders = [
        (ids["Paracetamol"],        today + " 08:00:00", "pending"),
        (ids["Paracetamol"],        today + " 20:00:00", "pending"),
        (ids["Vitamin D3"],         today + " 09:00:00", "completed"),
        (ids["Probiotics capsule"], today + " 07:30:00", "pending"),
        (ids["Omega-3 Fish Oil"],   today + " 13:00:00", "missed"),
        (ids["Calcium Tablet"],     today + " 21:30:00", "pending"),
        (ids["Amoxicillin"],        today + " 08:00:00", "completed"),
        (ids["Amoxicillin"],        today + " 14:00:00", "pending"),
        (ids["Amoxicillin"],        today + " 20:00:00", "pending"),
        (ids["Multivitamin"],       today + " 08:30:00", "completed"),
    ]
    cursor.executemany(
        "INSERT INTO reminders (medicine_id, reminder_time, status) VALUES (?,?,?)",
        reminders
    )
    connection.commit()
    print(f"[Seed] Inserted {len(reminders)} reminders.")

    # Create matching events for completed and missed reminders
    cursor.execute("SELECT id, reminder_time, status FROM reminders ORDER BY id")
    events = []
    for row in cursor.fetchall():
        reminder_id, reminder_time_str, status = row
        t = datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M:%S")
        events.append((reminder_id, "reminder_due", format_time(t)))
        if status == "completed":
            events.append((reminder_id, "compartment_opened",  format_time(t + timedelta(minutes=2))))
            events.append((reminder_id, "button_acknowledged", format_time(t + timedelta(minutes=3))))
        elif status == "missed":
            events.append((reminder_id, "reminder_missed", format_time(t + timedelta(minutes=45))))

    cursor.executemany(
        "INSERT INTO events (reminder_id, event_type, timestamp) VALUES (?,?,?)",
        events
    )
    connection.commit()
    print(f"[Seed] Inserted {len(events)} events.")

    # Ensure a device status row exists without replacing migrated settings.
    cursor.execute("SELECT COUNT(*) FROM device_status")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO device_status (status, last_seen) VALUES (?,?)",
            ("Offline", format_time(now))
        )
        connection.commit()
        print("[Seed] Device status initialized.")


def initialize_database(db_path=DB_PATH):
    """
    Set up the database on startup.
    If the old schema (medicine_name column) is detected, the DB is deleted
    and rebuilt cleanly so there are no conflicts.
    """
    # Detect and handle the old schema
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(medicines)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        if columns and "medicine_name" in columns:
            print("[Init] Old database schema detected. Rebuilding from scratch...")
            os.remove(db_path)

    connection = get_connection(db_path)
    create_tables(connection)
    add_missing_columns(connection)
    normalize_statuses(connection)
    seed_sample_data(connection)
    connection.close()
    print("[Init] Database ready at", db_path)


if __name__ == "__main__":
    initialize_database()
