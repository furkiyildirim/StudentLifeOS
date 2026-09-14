import os
from datetime import datetime

def get_system_prompt(db):
    now = datetime.now()
    mem = ""
    try:
        with db.get_connection() as c:
            t = [r["title"] for r in c.execute("SELECT title FROM todo_tasks WHERE is_completed=0 LIMIT 3").fetchall()]
            if t: mem += f"Bekleyen Görevler: {','.join(t)} | "
            
            p = [r["title"] for r in c.execute("SELECT title FROM projects WHERE status='Devam Ediyor' LIMIT 2").fetchall()]
            if p: mem += f"Aktif Projeler: {','.join(p)}"

            courses = [
                f"{r['code']} ({r['credit'] or 0} kredi, {r['instructor'] or 'hoca yok'})"
                for r in c.execute("""
                SELECT code, name, credit, instructor
                FROM courses ORDER BY code LIMIT 8
            """).fetchall()
            ]
            if courses: mem += f" | Dersler: {', '.join(courses)}"
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
                return ",".join([r['title'] for r in c.execute("SELECT title FROM todo_tasks WHERE is_completed=0").fetchall()]) or "Yok"
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
                return ",".join([f"{r['start_time']} {r['title']}" for r in c.execute("SELECT title, start_time FROM calendar_events WHERE event_date=?", (date,)).fetchall()]) or "Yok"
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
                return ",".join([r['title'] for r in c.execute("SELECT title FROM notes").fetchall()]) or "Yok"
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
                rows = c.execute("""
                    SELECT c.code, c.name, c.credit, t.start_time, t.end_time,
                           t.instructor, t.classroom
                    FROM timetable t
                    JOIN courses c ON t.course_id = c.id
                    WHERE t.day_of_week = ?
                    ORDER BY t.start_time
                """, (d,))
                return ", ".join([
                    f"{r['start_time']}-{r['end_time']} {r['code']} "
                    f"({r['credit'] or 0} kredi, {r['instructor'] or 'hoca yok'}, "
                    f"{r['classroom'] or 'derslik yok'})"
                    for r in rows.fetchall()
                ]) or "Yok"
        except Exception as e: return str(e)

    def get_courses() -> str:
        """Dersleri kredi, hoca ve iletişim bilgileriyle listele."""
        try:
            with db.get_connection() as c:
                rows = c.execute("""
                    SELECT code, name, credit, instructor, instructor_contact, classroom
                    FROM courses ORDER BY code
                """)
                return ", ".join([
                    f"{r['code']} - {r['name']} ({r['credit'] or 0} kredi; "
                    f"hoca: {r['instructor'] or 'yok'}; "
                    f"iletişim: {r['instructor_contact'] or 'yok'}; "
                    f"varsayılan derslik: {r['classroom'] or 'yok'})"
                    for r in rows.fetchall()
                ]) or "Yok"
        except Exception as e: return str(e)

    def update_course(code: str, name: str = None, credit: int = None,
                      instructor: str = None, instructor_contact: str = None,
                      classroom: str = None) -> str:
        """Dersin genel bilgilerini güncelle. Çizelge saatlerinin hoca/derslik bilgilerine dokunmaz."""
        try:
            updates = []
            values = []
            for column, value in (
                ("name", name), ("credit", credit), ("instructor", instructor),
                ("instructor_contact", instructor_contact), ("classroom", classroom)
            ):
                if value is not None:
                    updates.append(f"{column} = ?")
                    values.append(int(float(value)) if column == "credit" else str(value).strip())
            if not updates:
                return "Güncellenecek bilgi verilmedi"

            with db.get_connection() as c:
                values.append(code.strip())
                cursor = c.execute(f"UPDATE courses SET {', '.join(updates)} WHERE code = ?", values)
                if cursor.rowcount == 0:
                    return "Ders bulunamadı"
                c.commit()
            return "Ders bilgileri güncellendi"
        except Exception as e: return str(e)

    def add_course(code: str, name: str, day: int, time: str) -> str:
        """Ders ekle. day:0-6, time:HH:MM."""
        try:
            d = int(float(day))
            with db.get_connection() as c:
                row = c.execute("SELECT id FROM courses WHERE code=?", (code,)).fetchone()
                cid = row["id"] if row else c.execute("INSERT INTO courses (code, name, credit, classroom) VALUES (?, ?, 0, '')", (code, name)).lastrowid
                c.execute("INSERT INTO timetable (course_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, '')", (cid, d, time))
                c.commit()
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_course(code: str) -> str:
        """Belirtilen kodu olan dersi sil."""
        try:
            with db.get_connection() as c:
                row = c.execute("SELECT id FROM courses WHERE code=?", (code,)).fetchone()
                if row:
                    cid = row["id"]
                    c.execute("UPDATE materials SET course_id=NULL WHERE course_id=?", (cid,))
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
                return ",".join([r['exercise_name'] for r in c.execute("SELECT exercise_name FROM workout_exercises WHERE day_of_week=?", (d,)).fetchall()]) or "Yok"
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
                return ",".join([r['title'] for r in c.execute("SELECT title FROM habits").fetchall()]) or "Yok"
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
                return ",".join([f"ID:{r['id']} {r['title']}" for r in c.execute("SELECT id, title FROM projects").fetchall()]) or "Yok"
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
        get_schedule, get_courses, update_course, add_course, delete_course,
        get_workouts, add_workout, delete_workout,
        get_habits, add_habit, delete_habit,
        get_projs, add_project, delete_project, add_proj_task, delete_proj_task
    ]