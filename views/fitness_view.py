from datetime import date, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QFrame, QScrollArea, QSplitter, QProgressBar
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from core.events import bus
from core.sound import play_action_sound

DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# =========================================================================
# 1. BİLEŞEN: DİNAMİK DOLAN BARLI ALIŞKANLIK KARTI
# =========================================================================
class HabitCard(QFrame):
    status_toggled = Signal(int, bool)
    deleted = Signal(int)

    def __init__(self, habit_id: int, title: str, completed_dates: set, created_at_str: str = None, target_days: int = 30):
        super().__init__()
        self.habit_id = habit_id
        self.title = title
        self.completed_dates = completed_dates
        self.target_days = target_days
        
        if created_at_str:
            self.created_date = date.fromisoformat(created_at_str)
        else:
            self.created_date = date.today()
            
        self.setObjectName("Card")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # --- ÜST SATIR (Değişmedi) ---
        top_row = QHBoxLayout()
        lbl_title = QLabel(self.title)
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        top_row.addWidget(lbl_title)
        top_row.addStretch()

        streak = self.calculate_streak()
        lbl_streak = QLabel(f"🔥 {streak} Gün Seri")
        lbl_streak.setStyleSheet("background-color: #451a03; color: #f97316; font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 6px; border: 1px solid #7c2d12;")
        top_row.addWidget(lbl_streak)

        today_str = date.today().isoformat()
        is_today_done = today_str in self.completed_dates

        btn_check = QPushButton("✓ Tamamlandı" if is_today_done else "Tamamla")
        btn_check.setCursor(QCursor(Qt.PointingHandCursor))
        btn_check.setFixedHeight(28)
        btn_check.setStyleSheet("background-color: #059669; color: white; font-weight: bold; border-radius: 6px; padding: 0 12px;" if is_today_done else "background-color: #27272a; color: #d4d4d8; border-radius: 6px; padding: 0 12px;")
        btn_check.clicked.connect(lambda: self.status_toggled.emit(self.habit_id, is_today_done))
        top_row.addWidget(btn_check)

        btn_del = QPushButton("✕")
        btn_del.setFixedSize(28, 28)
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setStyleSheet("background: transparent; color: #71717a; border: none; font-size: 14px; font-weight: bold;")
        btn_del.clicked.connect(lambda: self.deleted.emit(self.habit_id))
        top_row.addWidget(btn_del)
        layout.addLayout(top_row)

        # --- ORTA SATIR: YÜZDE HESABI ---
        today = date.today()
        valid_completions = 0
        for i in range(self.target_days):
            d = self.created_date + timedelta(days=i)
            if d.isoformat() in self.completed_dates:
                valid_completions += 1
                
        pct = int((valid_completions / self.target_days) * 100)

        bar_box = QVBoxLayout()
        bar_box.setSpacing(4)
        bar_info = QHBoxLayout()
        lbl_bar_text = QLabel(f"Hedef Başarısı ({self.target_days} Gün):")
        lbl_bar_text.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        lbl_pct = QLabel(f"%{pct} ({valid_completions} gün tamamlandı)")
        lbl_pct.setStyleSheet("font-size: 11px; font-weight: bold; color: #10b981;")
        bar_info.addWidget(lbl_bar_text)
        bar_info.addStretch()
        bar_info.addWidget(lbl_pct)
        bar_box.addLayout(bar_info)

        pbar = QProgressBar()
        pbar.setValue(pct)
        pbar.setFixedHeight(8)
        pbar.setTextVisible(False)
        pbar.setStyleSheet("QProgressBar { background-color: #27272a; border-radius: 4px; } QProgressBar::chunk { background-color: #10b981; border-radius: 4px; }")
        bar_box.addWidget(pbar)
        layout.addLayout(bar_box)

        # --- ALT SATIR: 1. GÜNDEN HEDEFE KADAR AKAN KUTUCUKLAR ---
        dots_container = QVBoxLayout()
        dots_container.setSpacing(4)
        
        max_cols = 30 # Çok uzun hedeflerde (örn: 90) taşmayı engellemek için alt satıra geçer
        current_row = QHBoxLayout()
        current_row.setSpacing(4)
        
        for i in range(self.target_days):
            d = self.created_date + timedelta(days=i)
            is_done = d.isoformat() in self.completed_dates
            
            dot = QFrame()
            dot.setFixedSize(12, 12)
            
            if is_done:
                dot.setStyleSheet("background-color: #10b981; border-radius: 3px;")
                dot.setToolTip(f"{i+1}. Gün ({d.strftime('%d.%m.%Y')}): Tamamlandı 🎉")
            elif d > today:
                dot.setStyleSheet("background-color: #27272a; border-radius: 3px;") # Gelecek günler
                dot.setToolTip(f"{i+1}. Gün ({d.strftime('%d.%m.%Y')}): Bekliyor")
            else:
                dot.setStyleSheet("background-color: #ef4444; border-radius: 3px;") # Kaçırılmış günler
                dot.setToolTip(f"{i+1}. Gün ({d.strftime('%d.%m.%Y')}): İhmal Edildi ❌")

            current_row.addWidget(dot)
            
            # Satır sonu geldiyse veya son elemansa yeni satıra geç
            if (i + 1) % max_cols == 0 or (i + 1) == self.target_days:
                current_row.addStretch()
                dots_container.addLayout(current_row)
                current_row = QHBoxLayout()
                current_row.setSpacing(4)

        layout.addLayout(dots_container)

    def calculate_streak(self):
        streak = 0
        cur = date.today()
        if cur.isoformat() not in self.completed_dates:
            cur -= timedelta(days=1)
        while cur.isoformat() in self.completed_dates:
            streak += 1
            cur -= timedelta(days=1)
        return streak


# =========================================================================
# 2. BİLEŞEN: EGZERSİZ KARTI
# =========================================================================
class ExerciseRowCard(QFrame):
    edit_requested = Signal(dict)
    delete_requested = Signal(int)

    def __init__(self, data: dict):
        super().__init__()
        self.data = data
        self.setObjectName("Card")
        self.setStyleSheet("""
            QFrame#Card {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame#Card:hover {
                border-color: #3f3f46;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(14)

        lbl_name = QLabel(f"🏋️ {self.data['exercise_name']}")
        lbl_name.setStyleSheet("font-size: 14px; font-weight: 700; color: #38bdf8;")
        layout.addWidget(lbl_name)

        layout.addStretch()

        badge_sets = QLabel(f"{self.data['sets']} Set")
        badge_sets.setStyleSheet("background: #27272a; color: #e4e4e7; font-weight: bold; font-size: 12px; padding: 4px 8px; border-radius: 4px;")
        
        badge_reps = QLabel(f"{self.data['reps']} Tekrar")
        badge_reps.setStyleSheet("background: #27272a; color: #e4e4e7; font-weight: bold; font-size: 12px; padding: 4px 8px; border-radius: 4px;")

        w_val = self.data.get('weight', 0.0)
        badge_weight = QLabel(f"{w_val} kg" if w_val > 0 else "Vücut Ağırlığı")
        badge_weight.setStyleSheet("background: #1e293b; color: #38bdf8; font-weight: bold; font-size: 12px; padding: 4px 8px; border-radius: 4px;")

        layout.addWidget(badge_sets)
        layout.addWidget(badge_reps)
        layout.addWidget(badge_weight)

        btn_edit = QPushButton("Düzenle")
        btn_edit.setCursor(QCursor(Qt.PointingHandCursor))
        btn_edit.setStyleSheet("padding: 4px 10px; font-size: 12px;")
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.data))

        btn_del = QPushButton("Sil")
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setStyleSheet("background-color: #7f1d1d; color: white; border-radius: 4px; padding: 4px 10px; font-size: 12px;")
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self.data["id"]))

        layout.addWidget(btn_edit)
        layout.addWidget(btn_del)


# =========================================================================
# 3. ANA FITNESS VIEW EKRANI
# =========================================================================
class FitnessView(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.selected_dow = date.today().weekday()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        splitter = QSplitter(Qt.Horizontal)

        habits_container = QFrame()
        habits_lay = QVBoxLayout(habits_container)
        habits_lay.setContentsMargins(0, 0, 10, 0)
        habits_lay.setSpacing(12)

        h_header = QHBoxLayout()
        lbl_h_title = QLabel("⚡ Alışkanlık Zinciri")
        lbl_h_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        
        btn_add_habit = QPushButton("+ Alışkanlık")
        btn_add_habit.setObjectName("AccentButton")
        btn_add_habit.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_habit.clicked.connect(self.dialog_add_habit)

        h_header.addWidget(lbl_h_title)
        h_header.addStretch()
        h_header.addWidget(btn_add_habit)
        habits_lay.addLayout(h_header)

        self.habits_scroll = QScrollArea()
        self.habits_scroll.setWidgetResizable(True)
        self.habits_scroll.setStyleSheet("background: transparent; border: none;")
        
        self.habits_content = QWidget()
        self.habits_content_layout = QVBoxLayout(self.habits_content)
        self.habits_content_layout.setContentsMargins(0, 0, 0, 0)
        self.habits_content_layout.setSpacing(10)
        self.habits_content_layout.addStretch()
        
        self.habits_scroll.setWidget(self.habits_content)
        habits_lay.addWidget(self.habits_scroll)
        splitter.addWidget(habits_container)

        workout_container = QFrame()
        w_lay = QVBoxLayout(workout_container)
        w_lay.setContentsMargins(10, 0, 0, 0)
        w_lay.setSpacing(12)

        w_header = QHBoxLayout()
        lbl_w_title = QLabel("🏋️ Spor ve Antrenman Takvimi")
        lbl_w_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")

        btn_add_ex = QPushButton("+ Hareket Ekle")
        btn_add_ex.setObjectName("AccentButton")
        btn_add_ex.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_ex.clicked.connect(self.dialog_add_exercise)

        w_header.addWidget(lbl_w_title)
        w_header.addStretch()
        w_header.addWidget(btn_add_ex)
        w_lay.addLayout(w_header)

        days_bar = QHBoxLayout()
        days_bar.setSpacing(4)
        self.day_buttons = []

        for idx, d_name in enumerate(DAYS_TR):
            btn_d = QPushButton(d_name[:3])
            btn_d.setCheckable(True)
            btn_d.setCursor(QCursor(Qt.PointingHandCursor))
            btn_d.setFixedHeight(30)
            btn_d.setStyleSheet("""
                QPushButton {
                    background-color: #1c1917;
                    color: #a8a29e;
                    border: 1px solid #292524;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #292524;
                    color: #ffffff;
                }
                QPushButton:checked {
                    background-color: #0284c7;
                    color: #ffffff;
                    border-color: #0284c7;
                    font-weight: 700;
                }
            """)
            btn_d.clicked.connect(lambda _, day_idx=idx: self.select_day(day_idx))
            days_bar.addWidget(btn_d)
            self.day_buttons.append(btn_d)

        w_lay.addLayout(days_bar)

        self.lbl_day_info = QLabel()
        self.lbl_day_info.setStyleSheet("font-size: 14px; font-weight: 700; color: #38bdf8; margin-top: 4px;")
        w_lay.addWidget(self.lbl_day_info)

        self.workout_scroll = QScrollArea()
        self.workout_scroll.setWidgetResizable(True)
        self.workout_scroll.setStyleSheet("background: transparent; border: none;")

        self.workout_content = QWidget()
        self.workout_content_layout = QVBoxLayout(self.workout_content)
        self.workout_content_layout.setContentsMargins(0, 0, 0, 0)
        self.workout_content_layout.setSpacing(8)
        self.workout_content_layout.addStretch()

        self.workout_scroll.setWidget(self.workout_content)
        w_lay.addWidget(self.workout_scroll)

        splitter.addWidget(workout_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        self.select_day(self.selected_dow)
        self.load_habits()

    def load_habits(self):
        while self.habits_content_layout.count() > 1:
            item = self.habits_content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            
            try:
                cur.execute("ALTER TABLE habits ADD COLUMN created_at TEXT")
                cur.execute("UPDATE habits SET created_at = ? WHERE created_at IS NULL", (date.today().isoformat(),))
                conn.commit()
            except: pass

            # YENİ SÜTUN YAMASI
            try:
                cur.execute("ALTER TABLE habits ADD COLUMN target_days INTEGER")
                cur.execute("UPDATE habits SET target_days = 28 WHERE target_days IS NULL")
                conn.commit()
            except: pass

            cur.execute("SELECT id, title, created_at, target_days FROM habits ORDER BY id DESC")
            habits = cur.fetchall()

            for h in habits:
                cur.execute("SELECT date FROM habit_logs WHERE habit_id = ? AND is_completed = 1", (h["id"],))
                completed_dates = {row[0] for row in cur.fetchall()}
                
                created_val = h["created_at"] if "created_at" in h.keys() else None
                # Veritabanında hedef gün boşsa varsayılan olarak 28 ata
                target_val = h["target_days"] if "target_days" in h.keys() and h["target_days"] else 28

                card = HabitCard(h["id"], h["title"], completed_dates, created_val, target_val)
                card.status_toggled.connect(self.toggle_habit)
                card.deleted.connect(self.delete_habit)
                self.habits_content_layout.insertWidget(self.habits_content_layout.count() - 1, card)

        if not habits:
            empty = QLabel("Henüz alışkanlık eklenmedi. Yukarıdan ekleyebilirsiniz.")
            empty.setStyleSheet("color: #71717a; font-style: italic; padding: 20px;")
            self.habits_content_layout.insertWidget(0, empty)

    def toggle_habit(self, habit_id: int, current_status: bool):
        today_str = date.today().isoformat()
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if current_status:
                cur.execute("DELETE FROM habit_logs WHERE habit_id = ? AND date = ?", (habit_id, today_str))
            else:
                cur.execute("INSERT OR REPLACE INTO habit_logs (habit_id, date, is_completed) VALUES (?, ?, 1)", (habit_id, today_str))
            conn.commit()

        play_action_sound("complete") # ZİNCİR / ALIŞKANLIK TAMAMLANDI SESİ
        self.load_habits()
        bus.habits_changed.emit()
        bus.item_saved.emit("Alışkanlık durumu güncellendi.")

    def delete_habit(self, habit_id: int):
        confirm = QMessageBox.question(self, "Onay", "Bu alışkanlığı silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
                conn.commit()
            self.load_habits()
            bus.habits_changed.emit()
            bus.item_deleted.emit("Bir alışkanlık silindi.")

    def dialog_add_habit(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Alışkanlık Belirle")
        dlg.resize(320, 180) # Biraz büyüttük
        lay = QVBoxLayout(dlg)

        inp = QLineEdit()
        inp.setPlaceholderText("Alışkanlık Adı (örn: 30 Dk Kitap Okuma)")
        lay.addWidget(inp)
        
        # YENİ: Hedef gün seçici
        spin_days = QSpinBox()
        spin_days.setRange(7, 365) # 7 günden 1 yıla kadar hedeflenebilir
        spin_days.setValue(30)
        spin_days.setPrefix("Hedeflenen Süre: ")
        spin_days.setSuffix(" Gün")
        spin_days.setStyleSheet("padding: 4px;")
        lay.addWidget(spin_days)

        btn = QPushButton("Kaydet")
        btn.setObjectName("AccentButton")
        lay.addWidget(btn)

        def save():
            text = inp.text().strip()
            if not text: return
            
            target_d = spin_days.value()
            today_iso = date.today().isoformat()
            
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                # target_days değerini de gönderiyoruz
                cur.execute("INSERT INTO habits (title, created_at, target_days) VALUES (?, ?, ?)", (text, today_iso, target_d))
                conn.commit()
                
            try:
                play_action_sound("save")
            except: pass
            
            dlg.accept()
            self.load_habits()
            from core.events import bus
            bus.habits_changed.emit()

        btn.clicked.connect(save)
        dlg.exec()

    def select_day(self, day_idx: int):
        self.selected_dow = day_idx
        for i, btn in enumerate(self.day_buttons):
            btn.setChecked(i == day_idx)

        self.lbl_day_info.setText(f"📋 {DAYS_TR[day_idx]} Günü Antrenmanı")
        self.load_workouts_for_day()

    def load_workouts_for_day(self):
        while self.workout_content_layout.count() > 1:
            item = self.workout_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, day_of_week, exercise_name, sets, reps, weight 
                FROM workout_exercises 
                WHERE day_of_week = ?
                ORDER BY id ASC
            """, (self.selected_dow,))
            exercises = cur.fetchall()

            for ex in exercises:
                data = dict(ex)
                card = ExerciseRowCard(data)
                card.edit_requested.connect(self.dialog_edit_exercise)
                card.delete_requested.connect(self.delete_exercise)
                self.workout_content_layout.insertWidget(self.workout_content_layout.count() - 1, card)

        if not exercises:
            empty = QLabel(f"{DAYS_TR[self.selected_dow]} için planlanmış egzersiz yok (Dinlenme Günü).")
            empty.setStyleSheet("color: #71717a; font-style: italic; padding: 20px;")
            self.workout_content_layout.insertWidget(0, empty)

    def dialog_add_exercise(self):
        self._open_exercise_dialog(None)

    def dialog_edit_exercise(self, ex_data: dict):
        self._open_exercise_dialog(ex_data)

    def _open_exercise_dialog(self, ex_data: dict = None):
        is_edit = ex_data is not None
        dlg = QDialog(self)
        dlg.setWindowTitle("Egzersizi Düzenle" if is_edit else f"Yeni Hareket Ekle — {DAYS_TR[self.selected_dow]}")
        dlg.resize(320, 240)
        lay = QVBoxLayout(dlg)

        name_in = QLineEdit()
        name_in.setPlaceholderText("Hareket Adı (örn: Incline Dumbbell Press)")

        sets_in = QSpinBox(); sets_in.setRange(1, 20); sets_in.setValue(4); sets_in.setPrefix("Set: ")
        reps_in = QSpinBox(); reps_in.setRange(1, 100); reps_in.setValue(10); reps_in.setPrefix("Tekrar: ")
        weight_in = QDoubleSpinBox(); weight_in.setRange(0, 500); weight_in.setValue(20.0); weight_in.setPrefix("Ağırlık: "); weight_in.setSuffix(" kg")

        if is_edit:
            name_in.setText(ex_data["exercise_name"])
            sets_in.setValue(ex_data["sets"])
            reps_in.setValue(ex_data["reps"])
            weight_in.setValue(ex_data["weight"])

        lay.addWidget(QLabel("Hareket:"))
        lay.addWidget(name_in)
        lay.addWidget(sets_in)
        lay.addWidget(reps_in)
        lay.addWidget(weight_in)

        btn_save = QPushButton("Güncelle" if is_edit else "Kaydet")
        btn_save.setObjectName("AccentButton")
        lay.addWidget(btn_save)

        def save():
            name_text = name_in.text().strip()
            if not name_text:
                return
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                if is_edit:
                    cur.execute("""
                        UPDATE workout_exercises 
                        SET exercise_name = ?, sets = ?, reps = ?, weight = ?
                        WHERE id = ?
                    """, (name_text, sets_in.value(), reps_in.value(), weight_in.value(), ex_data["id"]))
                else:
                    cur.execute("""
                        INSERT INTO workout_exercises (day_of_week, exercise_name, sets, reps, weight)
                        VALUES (?, ?, ?, ?, ?)
                    """, (self.selected_dow, name_text, sets_in.value(), reps_in.value(), weight_in.value()))
                conn.commit()
                
            play_action_sound("save") # YENİ EGZERSİZ KAYDEDİLDİ SESİ
            dlg.accept()
            self.load_workouts_for_day()
            bus.workouts_changed.emit()
            bus.item_saved.emit(f"Antrenmana '{name_text}' hareketi eklendi.")

        btn_save.clicked.connect(save)
        dlg.exec()

    def delete_exercise(self, ex_id: int):
        confirm = QMessageBox.question(self, "Onay", "Bu egzersizi silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM workout_exercises WHERE id = ?", (ex_id,))
                conn.commit()
            self.load_workouts_for_day()
            bus.workouts_changed.emit()
            bus.item_deleted.emit("Antrenman hareketi silindi.")