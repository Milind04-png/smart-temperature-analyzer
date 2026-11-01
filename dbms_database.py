"""
Relational Database Management System (DBMS) Module
---------------------------------------------------
Implements the 4-table Relational Schema from Slide 10 of the Project Specification:
- SENSOR (sensor_id, location, sensor_type, unit)
- READING (reading_id, sensor_id, time_hr, temp_c, is_missing)
- ESTIMATE (est_id, reading_id, method, est_temp_c, abs_error)
- EXPOSURE_REPORT (report_id, sensor_id, start_hr, end_hr, exposure_cdeg_h)
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_temperature_db.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_dbms_database():
    """Initializes the exact 4-table ER schema from Slide 10."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: SENSOR
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SENSOR (
            sensor_id INTEGER PRIMARY KEY,
            location TEXT NOT NULL,
            sensor_type TEXT NOT NULL,
            unit TEXT NOT NULL
        )
    """)

    # Table 2: READING
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS READING (
            reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER NOT NULL,
            time_hr REAL NOT NULL,
            temp_c REAL,
            is_missing INTEGER DEFAULT 0,
            FOREIGN KEY (sensor_id) REFERENCES SENSOR(sensor_id)
        )
    """)

    # Table 3: ESTIMATE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ESTIMATE (
            est_id INTEGER PRIMARY KEY AUTOINCREMENT,
            reading_id INTEGER NOT NULL,
            method TEXT NOT NULL,
            est_temp_c REAL NOT NULL,
            abs_error REAL NOT NULL,
            FOREIGN KEY (reading_id) REFERENCES READING(reading_id)
        )
    """)

    # Table 4: EXPOSURE_REPORT
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS EXPOSURE_REPORT (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER NOT NULL,
            start_hr REAL NOT NULL,
            end_hr REAL NOT NULL,
            exposure_cdeg_h REAL NOT NULL,
            FOREIGN KEY (sensor_id) REFERENCES SENSOR(sensor_id)
        )
    """)

    # Populate default sensor if not exists
    cursor.execute("SELECT COUNT(*) FROM SENSOR WHERE sensor_id = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO SENSOR (sensor_id, location, sensor_type, unit)
            VALUES (1, 'Cold Storage / Greenhouse Bay 1', 'DHT22 (AM2302)', 'Celsius')
        """)

    conn.commit()
    conn.close()

def seed_sample_readings():
    """
    Seeds the discrete 06:00 to 18:00 readings matching Slides 4, 15, 16, 19.
    7 measured readings every 2 hours:
      06:00 -> 24.0 C
      08:00 -> 27.5 C
      10:00 -> 31.2 C
      12:00 -> 34.8 C
      14:00 -> 35.6 C
      16:00 -> 33.1 C
      18:00 -> 29.4 C
    6 gaps with is_missing = 1:
      07:00, 09:00, 11:00, 13:00, 15:00, 17:00
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Clear previous run
    cursor.execute("DELETE FROM ESTIMATE")
    cursor.execute("DELETE FROM READING")
    cursor.execute("DELETE FROM EXPOSURE_REPORT")

    measured_dict = {
        6.0: 24.0,
        8.0: 27.5,
        10.0: 31.2,
        12.0: 34.8,
        14.0: 35.6,
        16.0: 33.1,
        18.0: 29.4
    }

    # Insert hourly series from 6:00 to 18:00
    for h in range(6, 19):
        time_hr = float(h)
        if time_hr in measured_dict:
            cursor.execute("""
                INSERT INTO READING (sensor_id, time_hr, temp_c, is_missing)
                VALUES (1, ?, ?, 0)
            """, (time_hr, measured_dict[time_hr]))
        else:
            cursor.execute("""
                INSERT INTO READING (sensor_id, time_hr, temp_c, is_missing)
                VALUES (1, ?, NULL, 1)
            """, (time_hr,))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_dbms_database()
    seed_sample_readings()
    print("Initialized smart_temperature_db.db with 4-table ER schema and sample readings.")
