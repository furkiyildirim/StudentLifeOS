import calendar
from datetime import datetime, date, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QLineEdit, QComboBox,
    QMessageBox, QFrame, QSplitter, QGridLayout
)

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor

from core.events import bus
from core.sound import play_action_sound

CATEGORIES = {
    "Ders Çalışma": "#3b82f6",
    "Proje / Ödev": "#8b5cf6",
    "Sınav / Quiz": "#ef4444",
    "Kişisel / Sosyal": "#10b981",
    "Genel": "#f59e0b"
}

DAYS_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
DAYS_FULL_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS_TR = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]

class CalendarDayCell(QFrame):
    clicked = Signal(date)

    def __init__(self, target_date: date, is_current_month: bool, is_today: bool, is_selected: bool, events: list):
        super().__init__()
        self.target_date = target_date
        self.is_current_month = is_current_month
        self.is_today = is_today
        self.is_selected = is_selected
        self.events = events
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_day = QLabel(str(self.target_date.day))
        self.update_day_label_style()
        top_bar.addWidget(self.lbl_day)

        if self.is_today:
            lbl_today = QLabel("Bugün")
            lbl_today.setStyleSheet("""
                background-color: #0369a1;
                color: #ffffff;
                font-size: 9px;
                font-weight: bold;
                padding: 1px 4px;
                border-radius: 4px;
            """)
            top_bar.addWidget(lbl_today)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        max_visible = 3
        visible_events = self.events[:max_visible]
        
        for ev in visible_events:
            badge = QLabel(f"• {ev['title']}")
            badge.setFixedHeight(18)
            badge.setStyleSheet(f"""
                background-color: #292524;
                color: #f4f4f5;
                border-left: 2px solid {ev['color']};
                border-radius: 3px;
                font-size: 10px;
                font-weight: 600;
                padding: 1px 4px;
            """)
            layout.addWidget(badge)

        remaining = len(self.events) - max_visible
        if remaining > 0:
            lbl_more = QLabel(f"+{remaining} daha...")
            lbl_more.setStyleSheet("font-size: 9px; color: #a1a1aa; font-weight: bold; padding-left: 2px;")
            layout.addWidget(lbl_more)

        layout.addStretch()
        self.apply_cell_style()

    def update_day_label_style(self):
        self.lbl_day.setStyleSheet(f"""
            font-size: 13px;
            font-weight: {'800' if (self.is_today or self.is_selected) else '600'};
            color: {'#38bdf8' if self.is_today else ('#f4f4f5' if self.is_current_month else '#52525b')};
        """)

    def apply_cell_style(self):
        bg = "#171412" if self.is_current_month else "#0f0e0d"
        border_color = "#38bdf8" if self.is_selected else ("#292524" if self.is_current_month else "#1c1917")
        border_width = "2px" if self.is_selected else "1px"

        self.setStyleSheet(f"""
            CalendarDayCell {{
                background-color: {bg};
                border: {border_width} solid {border_color};
                border-radius: 8px;
            }}
            CalendarDayCell:hover {{
                background-color: #1f1b18;
                border-color: #0284c7;
            }}
        """)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self.target_date)
        super().mouseReleaseEvent(event)


class CalendarView(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_month_date = date.today().replace(day=1)
        self.selected_date = date.today()
        
        self.init_completions_table()
        self.init_ui()

    def init_completions_table(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS calendar_completions (
                    item_type TEXT,
                    item_id INTEGER,
                    date TEXT,
                    PRIMARY KEY (item_type, item_id, date)
                )
            """)
            conn.commit()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        header_bar = QHBoxLayout()
        header_bar.setSpacing(12)

        self.lbl_month_year = QLabel()
        self.lbl_month_year.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff;")
        header_bar.addWidget(self.lbl_month_year)

        btn_prev = QPushButton("◀")
        btn_prev.setFixedSize(34, 34)
        btn_prev.setCursor(QCursor(Qt.PointingHandCursor))
        btn_prev.clicked.connect(self.prev_month)

        btn_today = QPushButton("Bugüne Dön")
        btn_today.setFixedHeight(34)
        btn_today.setCursor(QCursor(Qt.PointingHandCursor))
        btn_today.setStyleSheet("padding: 0 12px; font-weight: bold;")
        btn_today.clicked.connect(self.go_to_today)

        btn_next = QPushButton("▶")
        btn_next.setFixedSize(34, 34)
        btn_next.setCursor(QCursor(Qt.PointingHandCursor))
        btn_next.clicked.connect(self.next_month)

        header_bar.addWidget(btn_prev)
        header_bar.addWidget(btn_today)
        header_bar.addWidget(btn_next)
        header_bar.addStretch()

        btn_add_plan = QPushButton("+ Seçilen Güne Plan Ekle")
        btn_add_plan.setObjectName("AccentButton")
        btn_add_plan.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_plan.setFixedHeight(36)
        btn_add_plan.clicked.connect(self.dialog_add_event)
        header_bar.addWidget(btn_add_plan)

        main_layout.addLayout(header_bar)

        splitter = QSplitter(Qt.Horizontal)

        grid_container = QFrame()
        grid_container.setObjectName("Card")
        self.grid_layout = QVBoxLayout(grid_container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(6)

        day_headers_layout = QHBoxLayout()
        day_headers_layout.setSpacing(6)
        for d in DAYS_TR:
            lbl_d = QLabel(d)
            lbl_d.setAlignment(Qt.AlignCenter)
            lbl_d.setStyleSheet("color: #a8a29e; font-weight: 700; font-size: 12px; padding: 4px;")
            day_headers_layout.addWidget(lbl_d)
        self.grid_layout.addLayout(day_headers_layout)

        self.days_grid = QGridLayout()
        self.days_grid.setSpacing(6)
        self.grid_layout.addLayout(self.days_grid)

        splitter.addWidget(grid_container)

        detail_container = QFrame()
        detail_container.setObjectName("Card")
        detail_container.setFixedWidth(340)
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(12)

        self.lbl_selected_title = QLabel()
        self.lbl_selected_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #38bdf8; border-bottom: 1px solid #292524; padding-bottom: 8px;")
        detail_layout.addWidget(self.lbl_selected_title)

        self.events_list = QListWidget()
        self.events_list.setStyleSheet("""
            QListWidget {
                background-color: #141210;
                border: 1px solid #292524;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-bottom: 1px solid #1f1b18;
            }
        """)
        detail_layout.addWidget(self.events_list)

        btn_box = QHBoxLayout()
        btn_toggle = QPushButton("✓ TAMAMLANDI")
        btn_toggle.setCursor(QCursor(Qt.PointingHandCursor))
        btn_toggle.clicked.connect(self.toggle_event_status)
        btn_toggle.setStyleSheet("background-color: green; color: white; border-radius: 6px; padding: 6px 12px; font-weight: bold;")

        btn_delete = QPushButton("🗑 Sil")
        btn_delete.setCursor(QCursor(Qt.PointingHandCursor))
        btn_delete.setStyleSheet("background-color: #7f1d1d; color: white; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        btn_delete.clicked.connect(self.delete_event)

        btn_box.addWidget(btn_toggle)
        btn_box.addWidget(btn_delete)
        detail_layout.addLayout(btn_box)

        splitter.addWidget(detail_container)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        self.refresh_calendar()

    def prev_month(self):
        prev_m = self.current_month_date.month - 1
        y = self.current_month_date.year
        if prev_m == 0:
            prev_m = 12
            y -= 1
        self.current_month_date = date(y, prev_m, 1)
        self.refresh_calendar()

    def next_month(self):
        next_m = self.current_month_date.month + 1
        y = self.current_month_date.year
        if next_m == 13:
            next_m = 1
            y += 1
        self.current_month_date = date(y, next_m, 1)
        self.refresh_calendar()

    def go_to_today(self):
        today = date.today()
        self.current_month_date = today.replace(day=1)
        self.selected_date = today
        self.refresh_calendar()

    def refresh_calendar(self):
        self.lbl_month_year.setText(f"{MONTHS_TR[self.current_month_date.month]} {self.current_month_date.year}")

        while self.days_grid.count():
            item = self.days_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdatescalendar(self.current_month_date.year, self.current_month_date.month)
        events_by_date = self.fetch_month_events()
        today = date.today()

        for r_idx, week in enumerate(month_days):
            for c_idx, day_dt in enumerate(week):
                is_curr_m = (day_dt.month == self.current_month_date.month)
                is_tod = (day_dt == today)
                is_sel = (day_dt == self.selected_date)

                # Yalnızca o güne ait özel etkinlikleri ve sınavları alıyoruz
                day_events = list(events_by_date.get(day_dt.isoformat(), []))
                
                # Haftalık derslerin tüm sütuna yansımasını engellemek için timetable 
                # birleştirmesi buradan kaldırıldı. (Dersler sağ panelde görünmeye devam edecek).

                cell = CalendarDayCell(
                    target_date=day_dt,
                    is_current_month=is_curr_m,
                    is_today=is_tod,
                    is_selected=is_sel,
                    events=day_events
                )
                cell.clicked.connect(self.on_day_clicked)
                self.days_grid.addWidget(cell, r_idx, c_idx)

        self.update_detail_view()

    def fetch_month_events(self):
        events_map = {}
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT event_date, title, category, is_completed FROM calendar_events")
            for r in cur.fetchall():
                d_str = r["event_date"]
                events_map.setdefault(d_str, []).append({
                    "type": "plan",
                    "title": r["title"],
                    "color": CATEGORIES.get(r["category"], "#f59e0b")
                })

            cur.execute("SELECT SUBSTR(due_date, 1, 10) as dt, title, course_id FROM assessments")
            for r in cur.fetchall():
                d_str = r["dt"]
                events_map.setdefault(d_str, []).append({
                    "type": "exam",
                    "title": f"Sınav: {r['title']}",
                    "color": "#ef4444"
                })
        return events_map

    def get_classes_for_dow(self, dow: int):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT c.code, c.color_hex, t.start_time 
                FROM timetable t
                JOIN courses c ON t.course_id = c.id
                WHERE t.day_of_week = ?
                ORDER BY t.start_time
            """, (dow,))
            return cur.fetchall()

    def on_day_clicked(self, selected_date: date):
        old_month = self.current_month_date.month
        self.selected_date = selected_date
        
        if selected_date.month == old_month:
            self.update_selection_visuals()
            self.update_detail_view()
        else:
            self.current_month_date = selected_date.replace(day=1)
            self.refresh_calendar()

    def update_selection_visuals(self):
        for i in range(self.days_grid.count()):
            item = self.days_grid.itemAt(i)
            if item:
                widget = item.widget()
                if isinstance(widget, CalendarDayCell):
                    is_sel = (widget.target_date == self.selected_date)
                    if widget.is_selected != is_sel:
                        widget.is_selected = is_sel
                        widget.apply_cell_style()
                        widget.update_day_label_style()

    def update_detail_view(self):
        d = self.selected_date
        tr_date_str = f"{d.day} {MONTHS_TR[d.month]} {d.year}, {DAYS_FULL_TR[d.weekday()]}"
        
        today = date.today()
        if d == today:
            self.lbl_selected_title.setText(f"📋 Bugün — {tr_date_str}")
        elif d == today - timedelta(days=1):
            self.lbl_selected_title.setText(f"📋 Dün — {tr_date_str}")
        elif d == today + timedelta(days=1):
            self.lbl_selected_title.setText(f"📋 Yarın — {tr_date_str}")
        else:
            self.lbl_selected_title.setText(f"📋 {tr_date_str}")

        self.events_list.clear()

        iso_date = self.selected_date.isoformat()
        dow = self.selected_date.weekday()

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                  SELECT t.id, c.code, c.name, COALESCE(t.classroom, c.classroom) AS classroom,
                      t.start_time, t.end_time, c.color_hex
                FROM timetable t
                JOIN courses c ON t.course_id = c.id
                WHERE t.day_of_week = ?
                ORDER BY t.start_time
            """, (dow,))
            for cl in cur.fetchall():
                cur.execute("SELECT 1 FROM calendar_completions WHERE item_type='class' AND item_id=? AND date=?", (cl["id"], iso_date))
                is_completed = bool(cur.fetchone())

                c_color = cl["color_hex"] if cl["color_hex"] else "#38bdf8"
                status_icon = "☑" if is_completed else "☐"
                item = QListWidgetItem(f"{status_icon} 🎓 DERS: {cl['code']} ({cl['start_time']} - {cl['end_time']}) — {cl['classroom']}")
                
                if is_completed:
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                    item.setForeground(QColor("#71717a"))
                else:
                    item.setForeground(QColor(c_color))
                    
                item.setData(Qt.UserRole, {"type": "class", "id": cl["id"], "title": cl["name"], "completed": is_completed})
                self.events_list.addItem(item)

            cur.execute("""
                SELECT a.id, a.title, a.due_date, c.code
                FROM assessments a
                JOIN courses c ON a.course_id = c.id
                WHERE a.due_date LIKE ?
            """, (f"{iso_date}%",))
            for ex in cur.fetchall():
                cur.execute("SELECT 1 FROM calendar_completions WHERE item_type='exam' AND item_id=? AND date=?", (ex["id"], iso_date))
                is_completed = bool(cur.fetchone())

                time_part = ex['due_date'].split()[1] if " " in ex['due_date'] else ""
                status_icon = "☑" if is_completed else "☐"
                item = QListWidgetItem(f"{status_icon} 🎯 SINAV: {ex['code']} - {ex['title']} {time_part}")
                
                if is_completed:
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                    item.setForeground(QColor("#71717a"))
                else:
                    item.setForeground(QColor("#ef4444"))
                    
                item.setData(Qt.UserRole, {"type": "exam", "id": ex["id"], "title": ex["title"], "completed": is_completed})
                self.events_list.addItem(item)

            cur.execute("""
                SELECT id, title, start_time, end_time, category, is_completed
                FROM calendar_events
                WHERE event_date = ?
                ORDER BY start_time ASC
            """, (iso_date,))
            for p in cur.fetchall():
                status_icon = "☑" if p["is_completed"] else "☐"
                time_range = f"[{p['start_time']} - {p['end_time']}] " if p['start_time'] else ""
                cat_color = CATEGORIES.get(p["category"], "#f59e0b")
                
                item = QListWidgetItem(f"{status_icon} {time_range}{p['title']} ({p['category']})")
                
                if p["is_completed"]:
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                    item.setForeground(QColor("#71717a"))
                else:
                    item.setForeground(QColor(cat_color))

                item.setData(Qt.UserRole, {"type": "plan", "id": p["id"], "completed": p["is_completed"], "title": p["title"]})
                self.events_list.addItem(item)

        if self.events_list.count() == 0:
            item = QListWidgetItem("Bu gün için herhangi bir kayıt yok.")
            item.setForeground(QColor("#71717a"))
            item.setData(Qt.UserRole, {"type": "none"})
            self.events_list.addItem(item)

    def dialog_add_event(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Plan Ekle — {self.selected_date.strftime('%d.%m.%Y')}")
        dlg.resize(320, 260)
        lay = QVBoxLayout(dlg)

        title_in = QLineEdit()
        title_in.setPlaceholderText("Plan Başlığı (örn: Mat-1 Soru Çözümü)")

        cat_box = QComboBox()
        for cat in CATEGORIES.keys():
            cat_box.addItem(cat)

        start_in = QLineEdit("14:00")
        start_in.setPlaceholderText("Başlangıç Saati (00:00)")
        end_in = QLineEdit("16:00")
        end_in.setPlaceholderText("Bitiş Saati (00:00)")

        lay.addWidget(QLabel("Başlık:"))
        lay.addWidget(title_in)
        lay.addWidget(QLabel("Kategori:"))
        lay.addWidget(cat_box)
        lay.addWidget(QLabel("Saat Aralığı:"))
        lay.addWidget(start_in)
        lay.addWidget(end_in)

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")
        lay.addWidget(btn_save)

        def save():
            if not title_in.text().strip():
                QMessageBox.warning(dlg, "Uyarı", "Başlık alanı boş bırakılamaz.")
                return
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO calendar_events (title, event_date, start_time, end_time, category)
                    VALUES (?, ?, ?, ?, ?)
                """, (title_in.text().strip(), self.selected_date.isoformat(), start_in.text().strip(), end_in.text().strip(), cat_box.currentText()))
                conn.commit()
                
            play_action_sound("save") # KULLANICI PLANI KAYDEDİLDİ SESİ
            dlg.accept()
            self.refresh_calendar()
            bus.calendar_changed.emit()
            bus.item_saved.emit(f"Takvime '{title_in.text().strip()}' planı eklendi.")
        btn_save.clicked.connect(save)
        dlg.exec()

    def toggle_event_status(self):
        current_item = self.events_list.currentItem()
        if not current_item:
            play_action_sound("error")
            QMessageBox.information(self, "Bilgi", "Lütfen listeden durumunu değiştirmek istediğiniz bir öğeyi seçin.")
            return

        data = current_item.data(Qt.UserRole)
        if not data or data.get("type") == "none":
            return

        is_done = data.get("completed")
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if data["type"] == "plan":
                new_status = 0 if is_done else 1
                cur.execute("UPDATE calendar_events SET is_completed = ? WHERE id = ?", (new_status, data["id"]))
            else:
                if is_done:
                    cur.execute("DELETE FROM calendar_completions WHERE item_type = ? AND item_id = ? AND date = ?", 
                                (data["type"], data["id"], self.selected_date.isoformat()))
                else:
                    cur.execute("INSERT INTO calendar_completions (item_type, item_id, date) VALUES (?, ?, ?)", 
                                (data["type"], data["id"], self.selected_date.isoformat()))
            conn.commit()

        play_action_sound("complete") # PLAN/DERS TAMAMLANDI SESİ
        self.update_detail_view()
        if data["type"] == "plan":
            bus.calendar_changed.emit()

    def delete_event(self):
        current_item = self.events_list.currentItem()
        if not current_item:
            play_action_sound("error")
            QMessageBox.information(self, "Bilgi", "Lütfen sağdaki listeden silmek istediğiniz bir öğeyi seçin.")
            return

        data = current_item.data(Qt.UserRole)
        if not data or data.get("type") == "none":
            return

        confirm = QMessageBox.question(
            self, "Silme Onayı",
            f"'{data.get('title')}' öğesini kalıcı olarak silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                if data["type"] == "plan":
                    cur.execute("DELETE FROM calendar_events WHERE id = ?", (data["id"],))
                elif data["type"] == "class":
                    cur.execute("DELETE FROM timetable WHERE id = ?", (data["id"],))
                elif data["type"] == "exam":
                    cur.execute("DELETE FROM assessments WHERE id = ?", (data["id"],))
                conn.commit()
            play_action_sound("delete")
            self.refresh_calendar()
            bus.item_deleted.emit(f"Takvimden '{data.get('title')}' öğesi silindi.")
            
            if data["type"] == "plan":
                bus.calendar_changed.emit()
            elif data["type"] == "class":
                bus.courses_changed.emit()
            elif data["type"] == "exam":
                bus.assessments_changed.emit()