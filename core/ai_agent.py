import os
from datetime import datetime

def get_system_prompt(db):
    now = datetime.now()
    mem = ""
    try:
        with db.get_connection() as c:
            c.execute("SELECT title FROM todo_tasks WHERE is_completed=0 LIMIT 3")
            t = [r["title"] for r in c.fetchall()]
            if t: mem += f"Bekleyen Görevler: {','.join(t)} | "
            
            c.execute("SELECT title FROM projects WHERE status='Devam Ediyor' LIMIT 2")
            p = [r["title"] for r in c.fetchall()]
            if p: mem += f"Aktif Projeler: {','.join(p)}"
    except: pass

    return (
        "Sen Student Life OS'in entegre zeki asistanısın"
        f"Tarih: {now.strftime('%Y-%m-%d %A')}\n"
        f"Hafıza: {mem}\n"
        "Yanıtlarını gereksiz uzatmadan, net ve arkadaşça ver. Sohbet edebilirsin ancak veritabanı araçlarını (tools) kullanman gerekirse mutlaka kullan."
    )

def get_database_tools(db):
    def get_todos() -> str:
        """Bekleyen görevleri listele."""
        try:
            with db.get_connection() as c:
                c.execute("SELECT title FROM todo_tasks WHERE is_completed=0")
                return ",".join([r['title'] for r in c.fetchall()]) or "Yok"
        except Exception as e: return str(e)

    def add_todo(title: str) -> str:
        """To-Do listesine görev ekle."""
        try:
            with db.get_connection() as c:
                try:
                    c.execute("INSERT INTO todo_tasks (title, category, priority, is_completed) VALUES (?, 'Genel', 'Orta', 0)", (title,))
                except:
                    c.execute("INSERT INTO todo_tasks (title, is_completed) VALUES (?, 0)", (title,))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def complete_todo(title: str) -> str:
        """To-Do görevini tamamla."""
        try:
            with db.get_connection() as c:
                c.execute("UPDATE todo_tasks SET is_completed=1 WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            return "Tamamlandı"
        except Exception as e: return str(e)

    def delete_todo(title: str) -> str:
        """To-Do görevini sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM todo_tasks WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            return "Silindi"
        except Exception as e: return str(e)

    def get_events(date: str) -> str:
        """Takvimi oku. (YYYY-MM-DD)"""
        try:
            with db.get_connection() as c:
                c.execute("SELECT title, start_time FROM calendar_events WHERE event_date=?", (date,))
                return ",".join([f"{r['start_time']} {r['title']}" for r in c.fetchall()]) or "Yok"
        except Exception as e: return str(e)

    def add_event(title: str, date: str, time: str) -> str:
        """Takvime ekle. (YYYY-MM-DD, HH:MM)"""
        try:
            with db.get_connection() as c:
                c.execute("INSERT INTO calendar_events (title, event_date, start_time, end_time, category, is_completed) VALUES (?, ?, ?, '', 'Genel', 0)", (title, date, time))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_event(title: str) -> str:
        """Takvimden etkinlik sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM calendar_events WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            return "Silindi"
        except Exception as e: return str(e)

    def get_notes() -> str:
        """Not başlıklarını listele."""
        try:
            with db.get_connection() as c:
                c.execute("SELECT title FROM notes")
                return ",".join([r['title'] for r in c.fetchall()]) or "Yok"
        except Exception as e: return str(e)

    def add_note(title: str, content: str) -> str:
        """Not oluştur."""
        try:
            with db.get_connection() as c:
                c.execute("INSERT INTO notes (title, content) VALUES (?, ?)", (title, content))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_note(title: str) -> str:
        """Sistemden not sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM notes WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            return "Silindi"
        except Exception as e: return str(e)

    def get_schedule(day: int) -> str:
        """Ders programını oku. day:0-6."""
        try:
            d = int(float(day))
            with db.get_connection() as c:
                c.execute("SELECT c.code, t.start_time FROM timetable t JOIN courses c ON t.course_id=c.id WHERE t.day_of_week=?", (d,))
                return ",".join([f"{r['start_time']} {r['code']}" for r in c.fetchall()]) or "Yok"
        except Exception as e: return str(e)

    def add_course(code: str, name: str, day: int, time: str) -> str:
        """Ders ekle. day:0-6, time:HH:MM."""
        try:
            d = int(float(day))
            with db.get_connection() as c:
                c.execute("SELECT id FROM courses WHERE code=?", (code,))
                row = c.fetchone()
                cid = row["id"] if row else c.execute("INSERT INTO courses (code, name, credit, classroom) VALUES (?, ?, 0, '')", (code, name)).lastrowid
                c.execute("INSERT INTO timetable (course_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, '')", (cid, d, time))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_course(code: str) -> str:
        """Belirtilen kodu olan dersi sil."""
        try:
            with db.get_connection() as c:
                c.execute("SELECT id FROM courses WHERE code=?", (code,))
                row = c.fetchone()
                if row:
                    cid = row["id"]
                    c.execute("DELETE FROM timetable WHERE course_id=?", (cid,))
                    c.execute("DELETE FROM courses WHERE id=?", (cid,))
                    c.commit()
                    return "Silindi"
                return "Bulunamadı"
        except Exception as e: return str(e)

    def get_workouts(day: int) -> str:
        """Günün antrenmanını oku. day:0-6."""
        try:
            d = int(float(day))
            with db.get_connection() as c:
                c.execute("SELECT exercise_name FROM workout_exercises WHERE day_of_week=?", (d,))
                return ",".join([r['exercise_name'] for r in c.fetchall()]) or "Yok"
        except Exception as e: return str(e)

    def add_workout(day: int, name: str) -> str:
        """Spora egzersiz ekle. day:0-6."""
        try:
            d = int(float(day))
            with db.get_connection() as c:
                c.execute("INSERT INTO workout_exercises (day_of_week, exercise_name, sets, reps) VALUES (?, ?, '3', '12')", (d, name))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_workout(name: str) -> str:
        """Spor programından egzersiz sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM workout_exercises WHERE exercise_name LIKE ?", (f"%{name}%",))
                c.commit()
            return "Silindi"
        except Exception as e: return str(e)

    def get_habits() -> str:
        """Alışkanlıkları listele."""
        try:
            with db.get_connection() as c:
                c.execute("SELECT title FROM habits")
                return ",".join([r['title'] for r in c.fetchall()]) or "Yok"
        except Exception as e: return str(e)

    def add_habit(title: str) -> str:
        """Alışkanlık ekle."""
        try:
            with db.get_connection() as c:
                c.execute("INSERT INTO habits (title) VALUES (?)", (title,))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_habit(title: str) -> str:
        """Sistemden alışkanlık sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM habits WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            return "Silindi"
        except Exception as e: return str(e)

    def get_projs() -> str:
        """Projeleri ve ID'lerini listele."""
        try:
            with db.get_connection() as c:
                c.execute("SELECT id, title FROM projects")
                return ",".join([f"ID:{r['id']} {r['title']}" for r in c.fetchall()]) or "Yok"
        except Exception as e: return str(e)

    def add_project(title: str) -> str:
        """Proje oluştur."""
        try:
            now = datetime.now().strftime("%Y-%m-%d")
            with db.get_connection() as c:
                c.execute("INSERT INTO projects (title, category, status, start_date, end_date, notes) VALUES (?, 'Genel', 'Devam Ediyor', ?, '2026-12-31', '')", (title, now))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_project(pid: int) -> str:
        """Projeyi tamamen sil."""
        try:
            p = int(float(pid))
            with db.get_connection() as c:
                c.execute("DELETE FROM project_tasks WHERE project_id=?", (p,))
                c.execute("DELETE FROM projects WHERE id=?", (p,))
                c.commit()
            return "Silindi"
        except Exception as e: return str(e)

    def add_proj_task(pid: int, title: str) -> str:
        """Projeye görev ekle."""
        try:
            with db.get_connection() as c:
                c.execute("INSERT INTO project_tasks (project_id, title, is_completed) VALUES (?, ?, 0)", (int(float(pid)), title))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_proj_task(title: str) -> str:
        """Proje alt görevini sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM project_tasks WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            return "Silindi"
        except Exception as e: return str(e)

    return [
        get_todos, add_todo, complete_todo, delete_todo,
        get_events, add_event, delete_event,
        get_notes, add_note, delete_note,
        get_schedule, add_course, delete_course,
        get_workouts, add_workout, delete_workout,
        get_habits, add_habit, delete_habit,
        get_projs, add_project, delete_project, add_proj_task, delete_proj_task
    ]