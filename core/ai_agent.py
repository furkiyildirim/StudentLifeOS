import os
from datetime import datetime, timedelta
from core.events import bus


def _emit_changed(*signals):
    for signal in signals:
        signal.emit()

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
        "Yanıtlarını gereksiz uzatmadan, net ve arkadaşça ver. Kullanıcı açıkça istediğinde veya işlem veritabanını değiştirecekse ilgili aracı mutlaka kullan. "
        "To-do, kişisel plan, ders, sınav, alışkanlık, antrenman, not ve proje kayıtlarını oluşturabilir, güncelleyebilir, tamamlayabilir ve silebilirsin. "
        "To-do görevlerinde önce get_todos ile ID, öncelik ve durumu kontrol et; güncelleme için update_todo kullan ve önceliği Düşük, Normal veya Yüksek olarak belirt. "
        "Projelerde durum değiştirme, proje tamamlama ve alt görev tamamlama işlemlerini de yapabilirsin. "
        "Silme veya büyük değişikliklerde hangi kaydı etkileyeceğini doğrula; kullanıcı istemeden kayıt silme."
    )

def get_database_tools(db):
    def get_todos() -> str:
        """To-do görevlerini ID, durum ve öncelikleriyle listele."""
        try:
            with db.get_connection() as c:
                rows = c.execute(
                    "SELECT id, title, priority, is_completed FROM todo_tasks ORDER BY is_completed ASC, id DESC"
                ).fetchall()
                return ", ".join(
                    f"ID:{r['id']} {r['title']} (öncelik:{r['priority'] or 'Normal'}, "
                    f"durum:{'tamamlandı' if r['is_completed'] else 'bekliyor'})"
                    for r in rows
                ) or "Yok"
        except Exception as e: return str(e)

    def add_todo(title: str, priority: str = "Normal") -> str:
        """To-do listesine görev ekle. Öncelik: Düşük, Normal veya Yüksek."""
        try:
            priority = priority if priority in ("Düşük", "Normal", "Yüksek") else "Normal"
            with db.get_connection() as c:
                c.execute("INSERT INTO todo_tasks (title, priority, is_completed) VALUES (?, ?, 0)", (title.strip(), priority))
                c.commit()
            _emit_changed(bus.todo_changed)
            return "Eklendi"
        except Exception as e: return str(e)

    def update_todo(task_id: int, title: str = None, priority: str = None,
                    is_completed: bool = None) -> str:
        """To-do görevini ID ile güncelle; başlık, öncelik veya tamamlanma durumunu değiştirebilir."""
        try:
            updates = []
            values = []
            if title is not None:
                updates.append("title = ?")
                values.append(title.strip())
            if priority is not None:
                if priority not in ("Düşük", "Normal", "Yüksek"):
                    return "Geçersiz öncelik. Düşük, Normal veya Yüksek kullanın"
                updates.append("priority = ?")
                values.append(priority)
            if is_completed is not None:
                updates.append("is_completed = ?")
                values.append(int(bool(is_completed)))
            if not updates:
                return "Güncellenecek bilgi verilmedi"
            values.append(int(float(task_id)))
            with db.get_connection() as c:
                cursor = c.execute(f"UPDATE todo_tasks SET {', '.join(updates)} WHERE id = ?", values)
                c.commit()
            if cursor.rowcount == 0:
                return "Görev bulunamadı"
            _emit_changed(bus.todo_changed)
            return "Görev güncellendi"
        except Exception as e: return str(e)

    def complete_todo(title: str) -> str:
        """To-Do görevini tamamla."""
        try:
            with db.get_connection() as c:
                c.execute("UPDATE todo_tasks SET is_completed=1 WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            _emit_changed(bus.todo_changed)
            return "Tamamlandı"
        except Exception as e: return str(e)

    def delete_todo(title: str) -> str:
        """To-Do görevini sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM todo_tasks WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            _emit_changed(bus.todo_changed)
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
            _emit_changed(bus.calendar_changed)
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_event(title: str) -> str:
        """Takvimden etkinlik sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM calendar_events WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            _emit_changed(bus.calendar_changed)
            return "Silindi"
        except Exception as e: return str(e)

    def update_event(title: str, new_title: str = None, date: str = None,
                     time: str = None, category: str = None,
                     is_completed: bool = None) -> str:
        """Kişisel planı başlığına göre güncelle. Tarih YYYY-MM-DD, saat HH:MM olabilir."""
        try:
            updates = []
            values = []
            for column, value in (
                ("title", new_title), ("event_date", date), ("start_time", time),
                ("category", category), ("is_completed", is_completed)
            ):
                if value is not None:
                    updates.append(f"{column} = ?")
                    values.append(int(value) if column == "is_completed" else str(value).strip())
            if not updates:
                return "Güncellenecek bilgi verilmedi"

            with db.get_connection() as c:
                values.append(f"%{title}%")
                cursor = c.execute(
                    f"UPDATE calendar_events SET {', '.join(updates)} WHERE title LIKE ?",
                    values,
                )
                c.commit()
            if cursor.rowcount == 0:
                return "Plan bulunamadı"
            _emit_changed(bus.calendar_changed)
            return f"{cursor.rowcount} plan güncellendi"
        except Exception as e: return str(e)

    def complete_event(title: str) -> str:
        """Kişisel planı tamamlandı olarak işaretle."""
        return update_event(title, is_completed=True)

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
            _emit_changed(bus.notes_changed)
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_note(title: str) -> str:
        """Sistemden not sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM notes WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            _emit_changed(bus.notes_changed)
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
            _emit_changed(bus.courses_changed)
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
            _emit_changed(bus.courses_changed)
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
                    _emit_changed(bus.courses_changed)
                    return "Silindi"
                return "Bulunamadı"
        except Exception as e: return str(e)

    def get_assessments() -> str:
        """Sınav ve değerlendirmeleri ders adı, tarih ve not bilgisiyle listele."""
        try:
            with db.get_connection() as c:
                rows = c.execute("""
                    SELECT a.id, a.title, a.weight, a.score, a.due_date, c.code
                    FROM assessments a JOIN courses c ON c.id = a.course_id
                    ORDER BY a.due_date
                """).fetchall()
            return ", ".join(
                f"ID:{r['id']} {r['code']} {r['title']} ({r['due_date']}, %{r['weight']}, not:{r['score'] if r['score'] is not None else 'yok'})"
                for r in rows
            ) or "Yok"
        except Exception as e: return str(e)

    def add_assessment(course_code: str, title: str, due_date: str,
                       weight: float = 0, score: float = None) -> str:
        """Derse sınav/değerlendirme ekle. due_date YYYY-MM-DD HH:MM olmalı."""
        try:
            with db.get_connection() as c:
                course = c.execute("SELECT id FROM courses WHERE code = ?", (course_code.strip(),)).fetchone()
                if not course:
                    return "Ders bulunamadı"
                c.execute(
                    "INSERT INTO assessments (course_id, title, weight, score, due_date) VALUES (?, ?, ?, ?, ?)",
                    (course["id"], title.strip(), float(weight), score, due_date.strip()),
                )
                c.commit()
            _emit_changed(bus.assessments_changed)
            return "Eklendi"
        except Exception as e: return str(e)

    def update_assessment(assessment_id: int, title: str = None,
                          due_date: str = None, weight: float = None,
                          score: float = None) -> str:
        """Sınav/değerlendirme kaydını ID ile güncelle."""
        try:
            updates = []
            values = []
            for column, value in (("title", title), ("due_date", due_date), ("weight", weight), ("score", score)):
                if value is not None:
                    updates.append(f"{column} = ?")
                    values.append(float(value) if column in ("weight", "score") else str(value).strip())
            if not updates:
                return "Güncellenecek bilgi verilmedi"
            values.append(int(float(assessment_id)))
            with db.get_connection() as c:
                cursor = c.execute(f"UPDATE assessments SET {', '.join(updates)} WHERE id = ?", values)
                c.commit()
            if cursor.rowcount == 0:
                return "Değerlendirme bulunamadı"
            _emit_changed(bus.assessments_changed)
            return "Değerlendirme güncellendi"
        except Exception as e: return str(e)

    def delete_assessment(assessment_id: int) -> str:
        """Sınav/değerlendirmeyi ID ile sil."""
        try:
            with db.get_connection() as c:
                cursor = c.execute("DELETE FROM assessments WHERE id = ?", (int(float(assessment_id)),))
                c.commit()
            if cursor.rowcount == 0:
                return "Değerlendirme bulunamadı"
            _emit_changed(bus.assessments_changed)
            return "Silindi"
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
            _emit_changed(bus.workouts_changed)
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_workout(name: str) -> str:
        """Spor programından egzersiz sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM workout_exercises WHERE exercise_name LIKE ?", (f"%{name}%",))
                c.commit()
            _emit_changed(bus.workouts_changed)
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
            _emit_changed(bus.habits_changed)
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_habit(title: str) -> str:
        """Sistemden alışkanlık sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM habits WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            _emit_changed(bus.habits_changed)
            return "Silindi"
        except Exception as e: return str(e)

    def get_projs() -> str:
        """Projeleri ve ID'lerini listele."""
        try:
            with db.get_connection() as c:
                return ",".join([f"ID:{r['id']} {r['title']}" for r in c.execute("SELECT id, title FROM projects").fetchall()]) or "Yok"
        except Exception as e: return str(e)

    def get_project(pid: int) -> str:
        """Projenin ayrıntılarını ve alt görevlerini getir."""
        try:
            p = int(float(pid))
            with db.get_connection() as c:
                project = c.execute("SELECT * FROM projects WHERE id = ?", (p,)).fetchone()
                if not project:
                    return "Proje bulunamadı"
                tasks = c.execute(
                    "SELECT id, title, is_completed FROM project_tasks WHERE project_id = ? ORDER BY id",
                    (p,),
                ).fetchall()
            task_text = ", ".join(
                f"ID:{t['id']} {t['title']} ({'tamamlandı' if t['is_completed'] else 'bekliyor'})"
                for t in tasks
            ) or "Yok"
            return (
                f"ID:{project['id']} | {project['title']} | kategori:{project['category']} | "
                f"durum:{project['status']} | bitiş:{project['end_date']} | not:{project['notes'] or 'yok'} | "
                f"alt görevler:{task_text}"
            )
        except Exception as e: return str(e)

    def add_project(title: str, category: str = "Genel", status: str = "Devam Ediyor",
                    end_date: str = None, notes: str = "") -> str:
        """Proje oluştur. end_date YYYY-MM-DD olmalı."""
        try:
            now = datetime.now().strftime("%Y-%m-%d")
            end_date = end_date or (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            with db.get_connection() as c:
                c.execute(
                    "INSERT INTO projects (title, category, status, start_date, end_date, notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (title.strip(), category.strip(), status.strip(), now, end_date, notes.strip()),
                )
                c.commit()
            _emit_changed(bus.projects_changed)
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
            _emit_changed(bus.projects_changed)
            return "Silindi"
        except Exception as e: return str(e)

    def add_proj_task(pid: int, title: str) -> str:
        """Projeye görev ekle."""
        try:
            with db.get_connection() as c:
                c.execute("INSERT INTO project_tasks (project_id, title, is_completed) VALUES (?, ?, 0)", (int(float(pid)), title))
                c.commit()
            _emit_changed(bus.projects_changed)
            return "Eklendi"
        except Exception as e: return str(e)

    def delete_proj_task(title: str) -> str:
        """Proje alt görevini sil."""
        try:
            with db.get_connection() as c:
                c.execute("DELETE FROM project_tasks WHERE title LIKE ?", (f"%{title}%",))
                c.commit()
            _emit_changed(bus.projects_changed)
            return "Silindi"
        except Exception as e: return str(e)

    def update_project(pid: int, title: str = None, category: str = None,
                       status: str = None, end_date: str = None,
                       notes: str = None) -> str:
        """Projeyi güncelle. Durum: Planlanıyor, Devam Ediyor veya Tamamlandı."""
        try:
            updates = []
            values = []
            for column, value in (
                ("title", title), ("category", category), ("status", status),
                ("end_date", end_date), ("notes", notes)
            ):
                if value is not None:
                    updates.append(f"{column} = ?")
                    values.append(str(value).strip())
            if not updates:
                return "Güncellenecek bilgi verilmedi"
            p = int(float(pid))
            with db.get_connection() as c:
                values.append(p)
                cursor = c.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", values)
                c.commit()
            if cursor.rowcount == 0:
                return "Proje bulunamadı"
            _emit_changed(bus.projects_changed)
            return "Proje güncellendi"
        except Exception as e: return str(e)

    def complete_project(pid: int) -> str:
        """Projeyi tamamlandı durumuna getir."""
        return update_project(pid, status="Tamamlandı")

    def complete_proj_task(task_id: int) -> str:
        """Proje alt görevini ID ile tamamla."""
        try:
            with db.get_connection() as c:
                cursor = c.execute("UPDATE project_tasks SET is_completed = 1 WHERE id = ?", (int(float(task_id)),))
                c.commit()
            if cursor.rowcount == 0:
                return "Alt görev bulunamadı"
            _emit_changed(bus.projects_changed)
            return "Alt görev tamamlandı"
        except Exception as e: return str(e)

    return [
        get_todos, add_todo, update_todo, complete_todo, delete_todo,
        get_events, add_event, update_event, complete_event, delete_event,
        get_notes, add_note, delete_note,
        get_schedule, get_courses, update_course, add_course, delete_course,
        get_assessments, add_assessment, update_assessment, delete_assessment,
        get_workouts, add_workout, delete_workout,
        get_habits, add_habit, delete_habit,
        get_projs, get_project, add_project, update_project, complete_project,
        delete_project, add_proj_task, complete_proj_task, delete_proj_task
    ]