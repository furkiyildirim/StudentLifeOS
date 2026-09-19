import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QTextEdit, QPushButton, QSplitter,
    QMessageBox, QComboBox, QFrame, QLineEdit, QProgressBar,
    QDateEdit, QCheckBox, QScrollArea, QSizePolicy, QGraphicsOpacityEffect, QCalendarWidget
)
from PySide6.QtCore import Qt, QDate, QLocale, QPropertyAnimation, QEasingCurve

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QCursor, QFont
from core.sound import play_action_sound



class ProjectView(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.active_project_id = None
        self.active_task_id = None
        
        self.setup_tables()
        self.init_ui()
        self.load_projects()

    def setup_tables(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT,
                    status TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    notes TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS project_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    title TEXT NOT NULL,
                    is_completed INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)
            task_columns = {row["name"] for row in cur.execute("PRAGMA table_info(project_tasks)")}
            if "notes" not in task_columns:
                cur.execute("ALTER TABLE project_tasks ADD COLUMN notes TEXT DEFAULT ''")
            conn.commit()

    def init_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(24, 24, 24, 24)
        main_lay.setSpacing(16)

        header = QLabel("🚀 Proje Yönetimi")
        header.setStyleSheet("font-size: 24px; font-weight: 800; color: #f8fafc;")
        main_lay.addWidget(header)

        header_hint = QLabel("Projelerini aşamalara böl, ilerlemeyi takip et ve her aşamanın defterini ayrı tut.")
        header_hint.setWordWrap(True)
        header_hint.setMinimumHeight(28)
        header_hint.setStyleSheet("font-size: 12px; color: #94a3b8; margin-top: -8px; padding-bottom: 3px;")
        main_lay.addWidget(header_hint)

        splitter = QSplitter(Qt.Horizontal)

        # ==========================================
        # SOL PANEL: FİLTRE VE PROJE LİSTESİ
        # ==========================================
        left_panel = QFrame()
        left_panel.setStyleSheet("QFrame { background-color: #151311; border: 1px solid #292524; border-radius: 14px; }")
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(16, 16, 16, 16)
        left_lay.setSpacing(10)

        btn_new = QPushButton("➕ Yeni Proje Oluştur")
        btn_new.setCursor(QCursor(Qt.PointingHandCursor))
        btn_new.setStyleSheet("""
            QPushButton { background-color: #38bdf8; color: #082f49; border-radius: 8px; padding: 11px; font-weight: 800; border: none; }
            QPushButton:hover { background-color: #7dd3fc; }
            QPushButton:pressed { padding-top: 12px; padding-bottom: 10px; }
        """)
        btn_new.clicked.connect(self.new_project)
        left_lay.addWidget(btn_new)

        self.filter_category = QComboBox()
        self.project_categories = [
            "Tüm Kategoriler", "Yazılım", "Mobil Uygulama", "Web Geliştirme",
            "Yapay Zeka", "Veri Bilimi", "Siber Güvenlik", "IoT / Donanım",
            "Robotik", "Akademik", "Araştırma", "Yarışma", "Girişimcilik",
            "Tasarım", "Kişisel", "Diğer"
        ]
        self.filter_category.addItems(self.project_categories)
        self.filter_category.setStyleSheet("background-color: #1c1917; color: white; padding: 6px; border-radius: 4px; border: 1px solid #3f3f46;")
        self.filter_category.currentIndexChanged.connect(self.load_projects)
        
        self.filter_status = QComboBox()
        self.filter_status.addItems(["Tüm Durumlar", "Planlanıyor", "Beklemede", "Devam Ediyor", "Tamamlandı", "Arşivlendi"])
        self.filter_status.setStyleSheet("background-color: #1c1917; color: white; padding: 6px; border-radius: 4px; border: 1px solid #3f3f46;")
        self.filter_status.currentIndexChanged.connect(self.load_projects)

        filter_title = QLabel("PROJE KATALOĞU")
        filter_title.setStyleSheet("font-size: 11px; font-weight: 800; letter-spacing: 1px; color: #7dd3fc; margin-top: 6px;")
        left_lay.addWidget(filter_title)
        left_lay.addWidget(QLabel("Kategori:"))
        left_lay.addWidget(self.filter_category)
        left_lay.addWidget(QLabel("Durum:"))
        left_lay.addWidget(self.filter_status)

        self.project_list = QListWidget()
        self.project_list.setSpacing(5)
        self.project_list.setUniformItemSizes(False)
        self.project_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { padding: 12px 10px; border: 1px solid #292524; color: #cbd5e1; border-radius: 8px; background-color: #1c1917; }
            QListWidget::item:hover { background-color: #25211f; border-color: #3f3f46; }
            QListWidget::item:selected { background-color: #082f49; border: 1px solid #0ea5e9; color: #e0f2fe; font-weight: 800; }
        """)
        self.project_list.itemClicked.connect(self.open_project)
        left_lay.addWidget(self.project_list)

        # ==========================================
        # SAĞ PANEL: PROJE DETAYLARI VE KONTROL
        # ==========================================
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("QFrame { background-color: #151311; border: 1px solid #292524; border-radius: 14px; }")
        right_lay = QVBoxLayout(self.right_panel)
        right_lay.setContentsMargins(20, 20, 20, 20)
        right_lay.setSpacing(16)

        self.right_opacity = QGraphicsOpacityEffect(self.right_panel)
        self.right_panel.setGraphicsEffect(self.right_opacity)
        self.right_anim = QPropertyAnimation(self.right_opacity, b"opacity")
        self.right_anim.setDuration(400) # Animasyon hızı (400ms)
        self.right_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # Üst Başlık ve Aksiyonlar
        top_ctrl = QHBoxLayout()
        self.editor_mode = QLabel("PROJE DETAYI")
        self.editor_mode.setStyleSheet("color: #94a3b8; background: #1c1917; border: 1px solid #3f3f46; border-radius: 6px; padding: 6px 9px; font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        top_ctrl.addWidget(self.editor_mode)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Proje Başlığı...")
        self.title_edit.setStyleSheet("QLineEdit { background: #1c1917; border: 1px solid #3f3f46; border-radius: 8px; padding: 8px 12px; font-size: 20px; font-weight: 800; color: #ffffff; } QLineEdit:focus { border: 1px solid #38bdf8; }")
        
        btn_save = QPushButton("💾 Kaydet")
        self.btn_save_project = btn_save
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        btn_save.setStyleSheet("QPushButton { background-color: #10b981; color: white; border-radius: 8px; padding: 9px 16px; font-weight: 800; border: none; } QPushButton:hover { background-color: #34d399; } QPushButton:disabled { background-color: #27272a; color: #71717a; border: 1px solid #3f3f46; }")
        btn_save.clicked.connect(self.save_project)

        btn_delete = QPushButton("🗑 Sil")
        self.btn_delete_project = btn_delete
        btn_delete.setCursor(QCursor(Qt.PointingHandCursor))
        btn_delete.setStyleSheet("QPushButton { background-color: #3f1d24; color: #fda4af; border: 1px solid #7f1d1d; border-radius: 8px; padding: 9px 16px; font-weight: 800; } QPushButton:hover { background-color: #7f1d1d; color: white; }")
        btn_delete.clicked.connect(self.delete_project)

        top_ctrl.addWidget(self.title_edit)
        top_ctrl.addWidget(btn_save)
        top_ctrl.addWidget(btn_delete)
        right_lay.addLayout(top_ctrl)

        # Meta Bilgiler (Kategori, Tarih, Kalan Gün)
        meta_lay = QHBoxLayout()
        
        self.cat_cb = QComboBox()
        self.cat_cb.addItems(self.project_categories[1:])
        self.cat_cb.setStyleSheet(self.filter_category.styleSheet())
        
        self.status_cb = QComboBox()
        self.status_cb.addItems(["Planlanıyor", "Beklemede", "Devam Ediyor", "Tamamlandı", "Arşivlendi"])
        self.status_cb.setStyleSheet(self.filter_category.styleSheet())
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.end_date_edit.setMinimumWidth(135)
        self.end_date_edit.setDate(QDate.currentDate())
        self.configure_date_edit(self.end_date_edit)
        self.end_date_edit.dateChanged.connect(self.update_countdown)
        
        self.lbl_countdown = QLabel("Kalan: -")
        self.lbl_countdown.setStyleSheet("color: #fbbf24; font-weight: bold; font-size: 13px; background-color: #422006; padding: 6px 12px; border-radius: 6px;")
        
        meta_lay.addWidget(QLabel("Kategori:"))
        meta_lay.addWidget(self.cat_cb)
        meta_lay.addWidget(QLabel("Durum:"))
        meta_lay.addWidget(self.status_cb)
        meta_lay.addWidget(QLabel("Bitiş Tarihi:"))
        meta_lay.addWidget(self.end_date_edit)
        meta_lay.addWidget(self.lbl_countdown)
        meta_lay.addStretch()
        right_lay.addLayout(meta_lay)

        # İlerleme Çubuğu
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% tamamlandı")
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #27272a; border-radius: 6px; border: none; color: #e0f2fe; font-size: 10px; font-weight: 800; text-align: center; }
            QProgressBar::chunk { background-color: #0ea5e9; border-radius: 6px; }
        """)
        right_lay.addWidget(self.progress_bar)

        # Görevler ve Notlar Splitter'ı
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # Görev Listesi
        task_widget = QWidget()
        task_lay = QVBoxLayout(task_widget)
        task_lay.setContentsMargins(0, 0, 0, 0)
        task_header = QLabel("📋 Proje Aşamaları")
        task_header.setStyleSheet("font-size: 14px; font-weight: 800; color: #f8fafc;")
        task_lay.addWidget(task_header)
        task_hint = QLabel("Bir aşama seçtiğinde kendi defteri sağda açılır.")
        task_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")
        task_lay.addWidget(task_hint)
        
        task_input_lay = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Yeni görev ekle...")
        self.task_input.setStyleSheet("background-color: #1c1917; border: 1px solid #292524; border-radius: 6px; padding: 6px; color: white;")
        self.task_input.returnPressed.connect(self.add_task)
        
        btn_add_task = QPushButton("Ekle")
        btn_add_task.setStyleSheet("QPushButton { background-color: #27272a; color: #e2e8f0; border: 1px solid #3f3f46; border-radius: 7px; padding: 7px 12px; font-weight: 700; } QPushButton:hover { background-color: #3f3f46; }")
        btn_add_task.clicked.connect(self.add_task)
        
        task_input_lay.addWidget(self.task_input)
        task_input_lay.addWidget(btn_add_task)
        task_lay.addLayout(task_input_lay)

        self.task_list = QListWidget()
        self.task_list.setSpacing(4)
        self.task_list.setStyleSheet("""
            QListWidget { background: #100f0e; border: 1px solid #292524; border-radius: 8px; padding: 6px; }
            QListWidget::item { color: #cbd5e1; padding: 10px 8px; border-radius: 6px; }
            QListWidget::item:hover { background: #27272a; }
            QListWidget::item:selected { background: #082f49; color: #e0f2fe; border: 1px solid #0ea5e9; }
        """)
        self.task_list.itemChanged.connect(self.task_toggled)
        self.task_list.itemClicked.connect(self.open_task_notebook)
        task_lay.addWidget(self.task_list)
        bottom_splitter.addWidget(task_widget)

        # Not Defteri
        notes_widget = QWidget()
        notes_lay = QVBoxLayout(notes_widget)
        notes_lay.setContentsMargins(0, 0, 0, 0)
        self.notes_title = QLabel("📝 Proje Defteri (Sistem Mimarisi, Notlar, Loglar)")
        self.notes_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #f8fafc;")
        notes_lay.addWidget(self.notes_title)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Donanım pin şemaları, model eğitimi parametreleri veya takım görev dağılımlarını buraya not alın...")
        self.notes_edit.setStyleSheet("QTextEdit { background-color: #100f0e; border: 1px solid #292524; border-radius: 8px; padding: 12px; color: #f4f4f5; font-size: 14px; line-height: 1.5; } QTextEdit:focus { border: 1px solid #38bdf8; }")
        notes_lay.addWidget(self.notes_edit)
        self.btn_save_task_notes = QPushButton("💾 Aşama Defterini Kaydet")
        self.btn_save_task_notes.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_save_task_notes.setStyleSheet("QPushButton { background-color: #0ea5e9; color: white; border-radius: 8px; padding: 9px 12px; font-weight: 800; } QPushButton:hover { background-color: #38bdf8; }")
        self.btn_save_task_notes.clicked.connect(self.save_task_notes)
        self.btn_save_task_notes.setVisible(False)
        notes_lay.addWidget(self.btn_save_task_notes)
        bottom_splitter.addWidget(notes_widget)

        bottom_splitter.setSizes([350, 650])
        
        # Splitter'ın dikeyde tüm boş alanı emmesini zorlar, üst menüleri sıkıştırır
        bottom_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_lay.addWidget(bottom_splitter, 1)

        splitter.addWidget(left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([250, 750])
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # '1' değeri, tüm boşluğun bu splitter tarafından doldurulmasını zorlar
        main_lay.addWidget(splitter, 1) 

        self.enable_right_panel(False)

        self.enable_right_panel(False)

    def load_projects(self):
        self.project_list.clear()
        query = "SELECT id, title, status, end_date FROM projects WHERE 1=1"
        params = []
        
        f_cat = self.filter_category.currentText()
        if f_cat != "Tüm Kategoriler":
            query += " AND category = ?"
            params.append(f_cat)
            
        f_status = self.filter_status.currentText()
        if f_status != "Tüm Durumlar":
            query += " AND status = ?"
            params.append(f_status)
            
        query += " ORDER BY end_date ASC"

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            for r in cur.fetchall():
                emoji = "⏳" if r["status"] == "Devam Ediyor" else "✅" if r["status"] == "Tamamlandı" else "📅"
                item = QListWidgetItem(f"{emoji} {r['title']}")
                item.setData(Qt.UserRole, r["id"])
                self.project_list.addItem(item)

    def open_project(self, item):
        self.active_project_id = item.data(Qt.UserRole)
        self.active_task_id = None
        self.editor_mode.setText("PROJE DETAYI")
        self.editor_mode.setStyleSheet("color: #94a3b8; background: #1c1917; border: 1px solid #3f3f46; border-radius: 6px; padding: 6px 9px; font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        self.btn_save_task_notes.setVisible(False)
        self.btn_save_project.setEnabled(True)
        self.btn_delete_project.setEnabled(True)
        self.title_edit.setPlaceholderText("Proje Başlığı...")
        self.notes_title.setText("📝 Proje Defteri (Sistem Mimarisi, Notlar, Loglar)")
        self.enable_right_panel(True)
        
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM projects WHERE id = ?", (self.active_project_id,))
            proj = cur.fetchone()
            
            if proj:
                self.title_edit.setText(proj["title"])
                self.cat_cb.setCurrentText(proj["category"])
                self.status_cb.setCurrentText(proj["status"])
                self.notes_edit.setPlainText(proj["notes"])
                
                if proj["end_date"]:
                    self.end_date_edit.setDate(QDate.fromString(proj["end_date"], "yyyy-MM-dd"))
                else:
                    self.end_date_edit.setDate(QDate.currentDate())
                    
                self.update_countdown()
                self.load_tasks()
        self.right_anim.setStartValue(0.0)
        self.right_anim.setEndValue(1.0)
        self.right_anim.start()
    def new_project(self):
        self.active_project_id = None
        self.active_task_id = None
        self.editor_mode.setText("YENİ PROJE")
        self.editor_mode.setStyleSheet("color: #082f49; background: #38bdf8; border: 1px solid #7dd3fc; border-radius: 6px; padding: 6px 9px; font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        self.enable_right_panel(True)
        self.btn_save_project.setEnabled(True)
        self.btn_delete_project.setEnabled(False)
        self.title_edit.clear()
        self.title_edit.setPlaceholderText("Yeni projenin adını yaz...")
        self.notes_edit.clear()
        self.task_list.clear()
        self.btn_save_task_notes.setVisible(False)
        self.notes_title.setText("📝 Proje Defteri (Sistem Mimarisi, Notlar, Loglar)")
        self.end_date_edit.setDate(QDate.currentDate().addDays(30))
        self.title_edit.setFocus()
        self.update_countdown()
        self.progress_bar.setValue(0)

        self.right_panel.raise_()
        self.right_anim.setStartValue(0.0)
        self.right_anim.setEndValue(1.0)
        self.right_anim.start()

    def save_project(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Hata", "Lütfen bir proje başlığı girin.")
            return

        cat = self.cat_cb.currentText()
        status = self.status_cb.currentText()
        end_dt = self.end_date_edit.date().toString("yyyy-MM-dd")
        notes = self.notes_edit.toPlainText()

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if self.active_project_id:
                if self.active_task_id:
                    project_row = cur.execute(
                        "SELECT notes FROM projects WHERE id = ?",
                        (self.active_project_id,),
                    ).fetchone()
                    notes = project_row["notes"] if project_row else ""
                cur.execute("""
                    UPDATE projects 
                    SET title=?, category=?, status=?, end_date=?, notes=? 
                    WHERE id=?
                """, (title, cat, status, end_dt, notes, self.active_project_id))
            else:
                start_dt = QDate.currentDate().toString("yyyy-MM-dd")
                cur.execute("""
                    INSERT INTO projects (title, category, status, start_date, end_date, notes) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, cat, status, start_dt, end_dt, notes))
                self.active_project_id = cur.lastrowid
            conn.commit()
        play_action_sound("save")
        self.load_projects()

    def delete_project(self):
        if not self.active_project_id: return
        if QMessageBox.question(self, "Onay", "Projeyi ve tüm aşamalarını kalıcı olarak silmek istediğinize emin misiniz?") == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.cursor().execute("DELETE FROM projects WHERE id = ?", (self.active_project_id,))
                conn.commit()
            play_action_sound("delete")
            self.new_project()
            self.enable_right_panel(False)
            self.load_projects()

    def load_tasks(self):
        self.task_list.blockSignals(True)
        self.task_list.clear()
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, title, is_completed, notes FROM project_tasks WHERE project_id = ?", (self.active_project_id,))
            for r in cur.fetchall():
                item = QListWidgetItem(r["title"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if r["is_completed"] else Qt.Unchecked)
                item.setData(Qt.UserRole, r["id"])
                
                # Tamamlanan görevleri gri yap
                if r["is_completed"]:
                    item.setForeground(Qt.gray)
                    
                self.task_list.addItem(item)
        self.task_list.blockSignals(False)
        self.update_progress()

    def open_task_notebook(self, item):
        task_id = item.data(Qt.UserRole)
        with self.db.get_connection() as conn:
            task = conn.execute(
                "SELECT title, notes FROM project_tasks WHERE id = ? AND project_id = ?",
                (task_id, self.active_project_id),
            ).fetchone()
        if not task:
            return

        self.active_task_id = task_id
        self.notes_edit.setPlainText(task["notes"] or "")
        self.notes_title.setText(f"📝 Aşama Defteri: {task['title']}")
        self.btn_save_task_notes.setVisible(True)

    def save_task_notes(self):
        if not self.active_task_id:
            return
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE project_tasks SET notes = ? WHERE id = ? AND project_id = ?",
                (self.notes_edit.toPlainText(), self.active_task_id, self.active_project_id),
            )
            conn.commit()
        play_action_sound("save")

    def add_task(self):
        if not self.active_project_id:
            QMessageBox.warning(self, "Uyarı", "Görev eklemek için önce projeyi kaydedin.")
            return
            
        title = self.task_input.text().strip()
        if title:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO project_tasks (project_id, title) VALUES (?, ?)", (self.active_project_id, title))
                conn.commit()
            self.task_input.clear()
            self.load_tasks()

    def task_toggled(self, item):
        task_id = item.data(Qt.UserRole)
        is_done = 1 if item.checkState() == Qt.Checked else 0
        
        item.setForeground(Qt.gray if is_done else Qt.white)

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE project_tasks SET is_completed = ? WHERE id = ?", (is_done, task_id))
            conn.commit()
            
        self.update_progress()

    def update_progress(self):
        total = self.task_list.count()
        if total == 0:
            self.progress_bar.setValue(0)
            return
            
        completed = sum(1 for i in range(total) if self.task_list.item(i).checkState() == Qt.Checked)
        perc = int((completed / total) * 100)
        self.progress_bar.setValue(perc)

        # %100 olduysa durumu otomatik güncelle
        if perc == 100 and self.status_cb.currentText() != "Tamamlandı":
            self.status_cb.setCurrentText("Tamamlandı")
        elif perc < 100 and self.status_cb.currentText() == "Tamamlandı":
            self.status_cb.setCurrentText("Devam Ediyor")

    def update_countdown(self):
        end_d = self.end_date_edit.date()
        today = QDate.currentDate()
        days_left = today.daysTo(end_d)
        
        if days_left < 0:
            self.lbl_countdown.setText(f"Süre Bitti ({abs(days_left)} gün gecikti)")
            self.lbl_countdown.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 13px; background-color: #450a0a; padding: 6px 12px; border-radius: 6px;")
        elif days_left == 0:
            self.lbl_countdown.setText("Son Gün: Bugün")
            self.lbl_countdown.setStyleSheet("color: #f97316; font-weight: bold; font-size: 13px; background-color: #431407; padding: 6px 12px; border-radius: 6px;")
        else:
            self.lbl_countdown.setText(f"Kalan: {days_left} Gün")
            self.lbl_countdown.setStyleSheet("color: #10b981; font-weight: bold; font-size: 13px; background-color: #064e3b; padding: 6px 12px; border-radius: 6px;")

    def configure_date_edit(self, date_edit):
        turkish_locale = QLocale(QLocale.Turkish, QLocale.Turkey)
        date_edit.setLocale(turkish_locale)
        date_edit.setStyleSheet("""
            QDateEdit, QDateTimeEdit {
                background: #18151f;
                color: #f5f3ff;
                border: 1px solid #8b5cf6;
                border-radius: 8px;
                padding: 7px 8px;
                font-weight: 700;
            }
            QDateEdit:focus, QDateTimeEdit:focus { border: 2px solid #c4b5fd; }
            QDateEdit::down-button, QDateTimeEdit::down-button {
                width: 30px;
                background: #6d28d9;
                border-left: 1px solid #8b5cf6;
                border-top-right-radius: 7px;
                border-bottom-right-radius: 7px;
            }
            QDateEdit::down-button:hover, QDateTimeEdit::down-button:hover { background: #7c3aed; }
        """)
        calendar = date_edit.calendarWidget()
        calendar.setLocale(turkish_locale)
        calendar.setFirstDayOfWeek(Qt.Monday)
        calendar.setGridVisible(True)
        calendar.setStyleSheet("""
            QCalendarWidget { background: #15121d; color: #f5f3ff; border: 1px solid #8b5cf6; border-radius: 10px; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background: #24183a; border-bottom: 1px solid #6d28d9; padding: 4px; }
            QCalendarWidget QToolButton { color: #f5f3ff; background: #3b1d68; border: 1px solid #6d28d9; border-radius: 6px; padding: 6px 9px; font-weight: 800; }
            QCalendarWidget QToolButton:hover { background: #6d28d9; }
            QCalendarWidget QSpinBox { color: #f5f3ff; background: #3b1d68; border: 1px solid #8b5cf6; border-radius: 5px; padding: 4px; }
            QCalendarWidget QAbstractItemView { background: #15121d; color: #e9d5ff; selection-background-color: #7c3aed; selection-color: white; outline: 0; }
            QCalendarWidget QAbstractItemView::item:hover { background: #4c1d95; color: white; }
        """)

    def enable_right_panel(self, state):
        self.btn_save_project.setEnabled(state)
        self.title_edit.setEnabled(state)
        self.cat_cb.setEnabled(state)
        self.status_cb.setEnabled(state)
        self.end_date_edit.setEnabled(state)
        self.task_input.setEnabled(state)
        self.notes_edit.setEnabled(state)