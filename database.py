"""Local SQLite setup for Medimate (smart medicine reminder)."""

import os
import sqlite3
from datetime import datetime, timedelta

DB_NAME="medimate.db"
FOLDER=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(FOLDER, DB_NAME)

def format_time(value):
    """Turn a datetime into a simple text timestamp."""
    return value.strftime("%Y-%m-%d %H:%M:%S")

def get_connection(db_path=DB_PATH):
    """Open the SQLite database and turn foreign keys on."""
    connection=sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def create_tables(connection):
    """Create medicines, reminders, events, and device_status tables."""
    cursor=connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL,
            reminder_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (reminder_id) REFERENCES reminders(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            last_seen TEXT NOT NULL
        )
    """)
    connection.commit()

def count_rows(connection, sql):
    """Run a COUNT query and return the number."""
    cursor=connection.cursor()
    cursor.execute(sql)
    result=cursor.fetchone()
    return result[0]

def seed_sample_data(connection):
    """Add sample rows only if a table is still empty."""
    now=datetime.now()
    cursor=connection.cursor()
    medicine_count=count_rows(connection, "SELECT COUNT(*) FROM medicines")
    if medicine_count==0:
        medicines=[
            ("Paracetamol", "500mg", format_time(now)),
            ("Vitamin D3", "1000 IU", format_time(now-timedelta(days=2))),
            ("Probiotics capsule", "1 capsule", format_time(now-timedelta(days=5))),
            ("Omega-3 Fish Oil", "1000mg", format_time(now-timedelta(days=1))),
            ("Calcium Tablet", "600mg", format_time(now-timedelta(hours=8))),
            ("Amoxicillin", "250mg", format_time(now-timedelta(days=3))),
            ("Multivitamin", "1 tablet", format_time(now-timedelta(days=7))),
        ]
        cursor.executemany(
            "INSERT INTO medicines (medicine_name, dosage, created_at) VALUES (?, ?, ?)",
            medicines,
        )
        connection.commit()
        print("[Seed] Inserted", len(medicines), "medicines/supplements.")

    # Build a simple name -> id lookup so reminders can use the right medicine
    medicine_ids={}
    cursor.execute("SELECT id, medicine_name FROM medicines")
    medicine_rows=cursor.fetchall()
    for row in medicine_rows:
        medicine_id=row[0]
        medicine_name=row[1]
        medicine_ids[medicine_name]=medicine_id

    reminder_count=count_rows(connection, "SELECT COUNT(*) FROM reminders")
    if reminder_count==0:
        today=now.strftime("%Y-%m-%d")
        reminders=[
            (medicine_ids["Paracetamol"], today+" 08:00:00", "Pending"),
            (medicine_ids["Paracetamol"], today+" 20:00:00", "Pending"),
            (medicine_ids["Vitamin D3"], today+" 09:00:00", "Taken"),
            (medicine_ids["Probiotics capsule"], today+" 07:30:00", "Pending"),
            (medicine_ids["Omega-3 Fish Oil"], today+" 13:00:00", "Missed"),
            (medicine_ids["Calcium Tablet"], today+" 21:30:00", "Pending"),
            (medicine_ids["Amoxicillin"], today+" 08:00:00", "Taken"),
            (medicine_ids["Amoxicillin"], today+" 14:00:00", "Pending"),
            (medicine_ids["Amoxicillin"], today+" 20:00:00", "Pending"),
            (medicine_ids["Multivitamin"], today+" 08:30:00", "Taken"),
        ]
        cursor.executemany(
            "INSERT INTO reminders (medicine_id, reminder_time, status) VALUES (?, ?, ?)",
            reminders,
        )
        connection.commit()
        print("[Seed] Inserted", len(reminders), "reminders.")

    event_count=count_rows(connection, "SELECT COUNT(*) FROM events")
    if event_count==0:
        cursor.execute("SELECT id, reminder_time, status FROM reminders ORDER BY id")
        reminder_rows=cursor.fetchall()
        events=[]

        for row in reminder_rows:
            reminder_id=row[0]
            reminder_time=datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
            status=row[2]

            events.append((reminder_id, "reminder_due", format_time(reminder_time)))

            if status=="Taken":
                opened_time=reminder_time+timedelta(minutes=2)
                ack_time=reminder_time+timedelta(minutes=3)
                events.append((reminder_id, "compartment_opened", format_time(opened_time)))
                events.append((reminder_id, "button_acknowledged", format_time(ack_time)))
            elif status=="Missed":
                missed_time=reminder_time+timedelta(minutes=45)
                events.append((reminder_id, "reminder_missed", format_time(missed_time)))

        cursor.executemany(
            "INSERT INTO events (reminder_id, event_type, timestamp) VALUES (?, ?, ?)",
            events,
        )
        connection.commit()
        print("[Seed] Inserted", len(events), "events.")

    device_count=count_rows(connection, "SELECT COUNT(*) FROM device_status")
    if device_count==0:
        device_rows=[
            ("Online", format_time(now)),
            ("Idle", format_time(now-timedelta(minutes=15))),
        ]
        cursor.executemany(
            "INSERT INTO device_status (status, last_seen) VALUES (?, ?)",
            device_rows,
        )
        connection.commit()
        print("[Seed] Inserted", len(device_rows), "device_status rows.")

def initialize_database(db_path=DB_PATH):
    """Create tables and add sample data when tables are empty."""
    connection=get_connection(db_path)
    create_tables(connection)
    seed_sample_data(connection)
    connection.close()
    print("[Init] Database ready at", db_path)

if __name__=="__main__":
    initialize_database()
