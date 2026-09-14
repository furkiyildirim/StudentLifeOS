from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QFrame, QComboBox, QScrollArea, QProgressBar
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
        bg_color = "#12100e" if self.is_completed else "#18181b"
        border_color = "#1c1917" if self.is_completed else "#27272a"
        
        self.setStyleSheet(f"""
            QFrame#TaskCard {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            QFrame#TaskCard:hover {{
                border: 1px solid #3f3f46;
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

        # 4. Silme Butonu
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

        # GÖREV EKLEME KARTI
        add_card = QFrame()
        add_card.setObjectName("Card")
        add_lay = QHBoxLayout(add_card)
        add_lay.setContentsMargins(16, 16, 16, 16)
        add_lay.setSpacing(12)

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Yeni bir görev veya hedef ekle...")
        self.task_input.setFixedHeight(40)
        self.task_input.setStyleSheet("font-size: 14px; padding-left: 10px; background-color: rgba(128,128,128,0.1); border: 1px solid #3f3f46; border-radius: 8px;")

        self.priority_box = QComboBox()
        self.priority_box.addItems(["Düşük", "Normal", "Yüksek"])
        self.priority_box.setCurrentText("Normal")
        self.priority_box.setFixedSize(100, 40)
        self.priority_box.setStyleSheet("background-color: #27272a; border: 1px solid #3f3f46; border-radius: 8px; color: white; padding-left: 8px; font-weight: bold;")

        btn_add = QPushButton("Görev Ekle")
        btn_add.setObjectName("AccentButton")
        btn_add.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add.setFixedSize(120, 40)
        btn_add.clicked.connect(self.add_task)

        add_lay.addWidget(self.task_input, stretch=1)
        add_lay.addWidget(self.priority_box)
        add_lay.addWidget(btn_add)
        main_layout.addWidget(add_card)

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
            cur.execute("SELECT id, title, priority, is_completed FROM todo_tasks ORDER BY is_completed ASC, id DESC")
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

    def toggle_task_status(self, t_id: int, current_status: bool):
        new_status = 0 if current_status else 1
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE todo_tasks SET is_completed = ? WHERE id = ?", (new_status, t_id))
            conn.commit()

        play_action_sound("complete")
        self.load_tasks()

    def delete_task(self, t_id: int):
        confirm = QMessageBox.question(self, "Silme Onayı", "Bu görevi silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM todo_tasks WHERE id = ?", (t_id,))
                conn.commit()

            play_action_sound("delete")
            self.load_tasks()