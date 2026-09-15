import sqlite3
import os
from datetime import datetime, date

DB_FILE = "student_life.db"

class DatabaseManager:
    def __init__(self, db_name=DB_FILE):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode = WAL;")
            cur.execute("PRAGMA foreign_keys = ON;")

            # 1. Dersler
            cur.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                instructor TEXT,
                instructor_contact TEXT,
                classroom TEXT,
                credit INTEGER DEFAULT 3,
                color_hex TEXT DEFAULT '#3B82F6'
            );
            """)

            course_columns = {
                row["name"] for row in cur.execute("PRAGMA table_info(courses)")
            }
            if "instructor_contact" not in course_columns:
                cur.execute("ALTER TABLE courses ADD COLUMN instructor_contact TEXT")

            # 2. Haftalık Ders Çizelgesi
            cur.execute("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
                day_of_week INTEGER NOT NULL, -- 0: Pzt, 1: Sal, ..., 6: Paz
                start_time TEXT NOT NULL,     -- '09:00'
                end_time TEXT NOT NULL,       -- '10:30'
                instructor TEXT,
                instructor_contact TEXT,
                classroom TEXT
            );
            """)

            timetable_columns = {
                row["name"] for row in cur.execute("PRAGMA table_info(timetable)")
            }
            if "instructor" not in timetable_columns:
                cur.execute("ALTER TABLE timetable ADD COLUMN instructor TEXT")
            if "instructor_contact" not in timetable_columns:
                cur.execute("ALTER TABLE timetable ADD COLUMN instructor_contact TEXT")
            if "classroom" not in timetable_columns:
                cur.execute("ALTER TABLE timetable ADD COLUMN classroom TEXT")
            cur.execute("""
                UPDATE timetable
                SET instructor = COALESCE(instructor, (
                    SELECT instructor FROM courses WHERE courses.id = timetable.course_id
                )),
                    instructor_contact = COALESCE(instructor_contact, (
                        SELECT instructor_contact FROM courses WHERE courses.id = timetable.course_id
                    )),
                    classroom = COALESCE(classroom, (
                        SELECT classroom FROM courses WHERE courses.id = timetable.course_id
                    ))
                WHERE instructor IS NULL OR instructor_contact IS NULL OR classroom IS NULL
            """)

            # 3. Sınavlar ve Notlar
            cur.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
                title TEXT NOT NULL,          -- 'Vize 1', 'Final'
                weight REAL NOT NULL,         -- % cinsinden (örn: 40.0)
                score REAL,                   -- 0 - 100 arası (girilmediyse NULL)
                due_date TEXT NOT NULL        -- 'YYYY-MM-DD HH:MM'
            );
            """)
            cur.execute("""
                DELETE FROM assessments
                WHERE course_id IS NOT NULL
                  AND course_id NOT IN (SELECT id FROM courses)
            """)

            # 4. Not Defteri (Markdown)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 5. Materyal Havuzu (PDF & Resimler)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,      -- 'pdf', 'image'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 6. Alışkanlıklar
            cur.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                is_completed BOOLEAN DEFAULT 1,
                UNIQUE(habit_id, date)
            );
            """)

            # 7. Spor & Antrenman
            cur.execute("""
            CREATE TABLE IF NOT EXISTS workout_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week INTEGER NOT NULL,
                exercise_name TEXT NOT NULL,
                sets INTEGER NOT NULL,
                reps INTEGER NOT NULL,
                weight REAL DEFAULT 0.0,
                video_url TEXT
            );
            """)

            try:
                cur.execute("ALTER TABLE workout_exercises ADD COLUMN video_url TEXT")
            except Exception:
                pass
            
            # 8. Takvim Etkinlikleri
            cur.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_date DATE NOT NULL,      -- 'YYYY-MM-DD'
                start_time TEXT,               -- '14:00'
                end_time TEXT,                 -- '16:00'
                category TEXT DEFAULT 'Genel', -- 'Ders Çalışma', 'Proje', 'Sınav', 'Kişisel'
                is_completed BOOLEAN DEFAULT 0
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS study_time_logs (
                log_date DATE PRIMARY KEY,
                seconds INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            
            conn.commit()