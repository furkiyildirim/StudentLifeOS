from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QFrame, QComboBox, QScrollArea, QProgressBar, QInputDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont

from core.sound import play_action_sound
from core.events import bus

# =========================================================================
# MODERN GÖREV KARTI (TASK CARD) BİLEŞENİ
# =========================================================================
class TodoTaskCard(QFrame):
    status_toggled = Signal(int, bool)
    deleted = Signal(int)
    edit_requested = Signal(int)

    def __init__(self, t_id, title, priority, is_completed):
        super().__init__()
        self.t_id = t_id
        self.title = title
        self.priority = priority
        self.is_completed = bool(is_completed)
        self.init_ui()

    def init_ui(self):
        self.setObjectName("TaskCard")
        # Tamamlanmış görevleri biraz daha soluk renkte gösteriyoruz
        accent = "#10b981" if self.is_completed else {
            "Yüksek": "#f43f5e", "Normal": "#f59e0b", "Düşük": "#38bdf8"
        }.get(self.priority, "#a855f7")
        bg_color = "#123b35" if self.is_completed else "#142f4a"
        border_color = "#2dd4bf" if self.is_completed else "#60a5fa"
        hover_bg = "#185449" if self.is_completed else "#1b4265"
        hover_border = "#5eead4" if self.is_completed else "#93c5fd"
        
        self.setStyleSheet(f"""
            QFrame#TaskCard {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 10px;
                border-left: 5px solid {accent};
            }}
            QFrame#TaskCard:hover {{
                background-color: {hover_bg};
                border: 1px solid {hover_border};
                border-left: 5px solid {accent};
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(14)

        # 1. Tamamlama Butonu (Yuvarlak Onay Kutusu)
        self.btn_check = QPushButton("✓" if self.is_completed else "")
        self.btn_check.setFixedSize(26, 26)
        self.btn_check.setCursor(QCursor(Qt.PointingHandCursor))
        
        if self.is_completed:
            self.btn_check.setStyleSheet("background-color: #10b981; color: white; border-radius: 13px; font-weight: bold; border: none; font-size: 14px;")
        else:
            self.btn_check.setStyleSheet("background-color: transparent; border: 2px solid #52525b; border-radius: 13px;")
            
        self.btn_check.clicked.connect(lambda: self.status_toggled.emit(self.t_id, self.is_completed))
        lay.addWidget(self.btn_check)

        # 2. Görev Başlığı (Tamamlanmışsa üstü çizili)
        self.lbl_title = QLabel(self.title)
        self.lbl_title.setWordWrap(True)
        font = QFont()
        font.setPointSize(11)
        
        if self.is_completed:
            font.setStrikeOut(True)
            self.lbl_title.setStyleSheet("color: #52525b;")
        else:
            self.lbl_title.setStyleSheet("color: #f4f4f5; font-weight: 500;")
            
        self.lbl_title.setFont(font)
        lay.addWidget(self.lbl_title, stretch=1)

        # 3. Öncelik Rozeti (Badge)
        lbl_prio = QLabel(self.priority)
        lbl_prio.setAlignment(Qt.AlignCenter)
        if self.priority == "Yüksek":
            lbl_prio.setStyleSheet("background-color: rgba(244, 63, 94, 0.15); color: #f43f5e; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        elif self.priority == "Düşük":
            lbl_prio.setStyleSheet("background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        else:
            lbl_prio.setStyleSheet("background-color: rgba(161, 161, 170, 0.15); color: #a1a1aa; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        lay.addWidget(lbl_prio)

        btn_edit = QPushButton("✎")
        btn_edit.setFixedSize(28, 28)
        btn_edit.setCursor(QCursor(Qt.PointingHandCursor))
        btn_edit.setToolTip("Görevi düzenle")
        btn_edit.setStyleSheet("QPushButton { background: transparent; color: #94a3b8; border: none; font-size: 16px; border-radius: 14px; } QPushButton:hover { background: #164e63; color: #7dd3fc; }")
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.t_id))
        lay.addWidget(btn_edit)

        # 5. Silme Butonu
        btn_del = QPushButton("✕")
        btn_del.setFixedSize(28, 28)
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setStyleSheet("""
            QPushButton { background: transparent; color: #71717a; border: none; font-size: 14px; font-weight: bold; border-radius: 14px; }
            QPushButton:hover { background-color: #450a0a; color: #f87171; }
        """)
        btn_del.clicked.connect(lambda: self.deleted.emit(self.t_id))
        lay.addWidget(btn_del)


# =========================================================================
# ANA TO-DO EKRANI
# =========================================================================
class TodoView(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.active_filter = "Tümü"
        self.init_table()
        self.init_ui()

    def init_table(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS todo_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    priority TEXT DEFAULT 'Normal',
                    is_completed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # ÜST BAR VE İLERLEME ÇUBUĞU
        header_lay = QHBoxLayout()
        title = QLabel("✅ Yapılacaklar Listesi")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff;")
        header_lay.addWidget(title)
        
        header_lay.addStretch()
        
        progress_lay = QVBoxLayout()
        self.lbl_progress = QLabel("0 / 0 Görev Tamamlandı")
        self.lbl_progress.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: bold;")
        self.lbl_progress.setAlignment(Qt.AlignRight)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #27272a; border-radius: 3px; border: none; }
            QProgressBar::chunk { background-color: #10b981; border-radius: 3px; }
        """)
        
        progress_lay.addWidget(self.lbl_progress)
        progress_lay.addWidget(self.progress_bar)
        header_lay.addLayout(progress_lay)
        
        main_layout.addLayout(header_lay)

        self.lbl_subtitle = QLabel("Önceliklerini sırala, ilerlemeni takip et ve günü küçük adımlara böl.")
        self.lbl_subtitle.setWordWrap(True)
        self.lbl_subtitle.setMinimumHeight(26)
        self.lbl_subtitle.setStyleSheet("color: #94a3b8; font-size: 12px; margin-top: -8px; padding-bottom: 2px;")
        main_layout.addWidget(self.lbl_subtitle)

        # GÖREV EKLEME KARTI
        add_card = QFrame()
        add_card.setObjectName("Card")
        add_lay = QHBoxLayout(add_card)
        add_lay.setContentsMargins(12, 10, 12, 10)
        add_lay.setSpacing(12)

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Yeni bir görev veya hedef ekle...")
        self.task_input.setFixedHeight(36)
        self.task_input.setStyleSheet("font-size: 14px; padding-left: 10px; background-color: rgba(128,128,128,0.1); border: 1px solid #3f3f46; border-radius: 8px;")

        self.priority_box = QComboBox()
        self.priority_box.addItems(["Düşük", "Normal", "Yüksek"])
        self.priority_box.setCurrentText("Normal")
        self.priority_box.setFixedSize(100, 36)
        self.priority_box.setStyleSheet("background-color: #27272a; border: 1px solid #3f3f46; border-radius: 8px; color: white; padding-left: 8px; font-weight: bold;")

        btn_add = QPushButton("➕  Görev Ekle")
        btn_add.setObjectName("TodoAddButton")
        btn_add.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add.setFixedSize(132, 36)
        btn_add.setStyleSheet("""
            QPushButton#TodoAddButton {
                background-color: #0ea5e9;
                color: #f0f9ff;
                border: 1px solid #38bdf8;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton#TodoAddButton:hover { background-color: #38bdf8; border-color: #7dd3fc; color: #082f49; }
            QPushButton#TodoAddButton:pressed { background-color: #0284c7; padding-top: 8px; padding-bottom: 4px; }
        """)
        btn_add.clicked.connect(self.add_task)

        add_lay.addWidget(self.task_input, stretch=1)
        add_lay.addWidget(self.priority_box)
        add_lay.addWidget(btn_add)
        main_layout.addWidget(add_card)

        filter_lay = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔎 Görevlerde ara...")
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.load_tasks)
        self.search_input.setStyleSheet("QLineEdit { background: #18181b; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 8px; padding: 0 12px; } QLineEdit:focus { border: 1px solid #38bdf8; }")

        self.filter_box = QComboBox()
        self.filter_box.addItems(["Tümü", "Bekleyenler", "Tamamlananlar", "Yüksek Öncelik", "Normal Öncelik", "Düşük Öncelik"])
        self.filter_box.setFixedHeight(36)
        self.filter_box.currentTextChanged.connect(self.load_tasks)
        self.filter_box.setStyleSheet("QComboBox { background: #18181b; color: #e4e4e7; border: 1px solid #3f3f46; border-radius: 8px; padding: 0 10px; } QComboBox::drop-down { border: none; }")
        filter_lay.addWidget(self.search_input, 1)
        filter_lay.addWidget(self.filter_box)
        main_layout.addLayout(filter_lay)

        # GÖREV LİSTESİ (KAYDIRILABİLİR ALAN)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.tasks_content = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_content)
        self.tasks_layout.setContentsMargins(0, 0, 10, 0)
        self.tasks_layout.setSpacing(10)
        self.tasks_layout.addStretch()

        self.scroll_area.setWidget(self.tasks_content)
        main_layout.addWidget(self.scroll_area)

        self.load_tasks()

    def update_progress(self, total, completed):
        self.lbl_progress.setText(f"{completed} / {total} Görev Tamamlandı")
        pct = int((completed / total * 100)) if total > 0 else 0
        self.progress_bar.setValue(pct)
        if pct == 100 and total > 0:
            self.progress_bar.setStyleSheet("QProgressBar { background-color: #27272a; border-radius: 3px; } QProgressBar::chunk { background-color: #3b82f6; border-radius: 3px; }")
        else:
            self.progress_bar.setStyleSheet("QProgressBar { background-color: #27272a; border-radius: 3px; } QProgressBar::chunk { background-color: #10b981; border-radius: 3px; }")

    def load_tasks(self):
        # Eski kartları temizle
        while self.tasks_layout.count() > 1:
            item = self.tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            search = self.search_input.text().strip() if hasattr(self, "search_input") else ""
            filter_text = self.filter_box.currentText() if hasattr(self, "filter_box") else "Tümü"
            query = "SELECT id, title, priority, is_completed FROM todo_tasks WHERE 1=1"
            params = []
            if search:
                query += " AND title LIKE ?"
                params.append(f"%{search}%")
            if filter_text == "Bekleyenler":
                query += " AND is_completed = 0"
            elif filter_text == "Tamamlananlar":
                query += " AND is_completed = 1"
            elif "Öncelik" in filter_text:
                query += " AND priority = ?"
                params.append(filter_text.replace(" Öncelik", ""))
            query += " ORDER BY is_completed ASC, id DESC"
            cur.execute(query, params)
            rows = cur.fetchall()

        total_tasks = len(rows)
        completed_tasks = 0

        for r in rows:
            t_id, title, priority, is_completed = r
            if is_completed:
                completed_tasks += 1

            card = TodoTaskCard(t_id, title, priority, is_completed)
            card.status_toggled.connect(self.toggle_task_status)
            card.deleted.connect(self.delete_task)
            card.edit_requested.connect(self.edit_task)
            
            # Kartı esnek alanın (addStretch) hemen üstüne ekliyoruz
            self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, card)

        self.update_progress(total_tasks, completed_tasks)

        if total_tasks == 0:
            empty = QLabel("Harika! Yapılacak hiçbir göreviniz kalmadı. 🎉")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #71717a; font-size: 14px; font-style: italic; padding: 40px;")
            self.tasks_layout.insertWidget(0, empty)

    def add_task(self):
        text = self.task_input.text().strip()
        if not text:
            return

        priority = self.priority_box.currentText()
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO todo_tasks (title, priority) VALUES (?, ?)", (text, priority))
            conn.commit()

        play_action_sound("save")
        self.task_input.clear()
        self.load_tasks()
        bus.todo_changed.emit()

    def edit_task(self, t_id: int):
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT title, priority FROM todo_tasks WHERE id = ?", (t_id,)).fetchone()
        if not row:
            return
        title, ok = QInputDialog.getText(self, "Görevi Düzenle", "Görev başlığı:", text=row["title"])
        if not ok or not title.strip():
            return
        priorities = ["Düşük", "Normal", "Yüksek"]
        current_priority = row["priority"] if row["priority"] in priorities else "Normal"
        priority, ok = QInputDialog.getItem(self, "Öncelik", "Görev önceliği:", priorities, priorities.index(current_priority), False)
        if not ok:
            return
        with self.db.get_connection() as conn:
            conn.execute("UPDATE todo_tasks SET title = ?, priority = ? WHERE id = ?", (title.strip(), priority, t_id))
            conn.commit()
        play_action_sound("save")
        self.load_tasks()
        bus.todo_changed.emit()

    def toggle_task_status(self, t_id: int, current_status: bool):
        new_status = 0 if current_status else 1
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE todo_tasks SET is_completed = ? WHERE id = ?", (new_status, t_id))
            conn.commit()

        play_action_sound("complete")
        self.load_tasks()
        bus.todo_changed.emit()

    def delete_task(self, t_id: int):
        confirm = QMessageBox.question(self, "Silme Onayı", "Bu görevi silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM todo_tasks WHERE id = ?", (t_id,))
                conn.commit()

            play_action_sound("delete")
            self.load_tasks()
            bus.todo_changed.emit()