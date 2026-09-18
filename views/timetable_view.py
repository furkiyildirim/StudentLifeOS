from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QDialog, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QMessageBox, QHeaderView, QTabWidget,
    QFrame, QScrollArea, QAbstractItemView, QMenu, QStyledItemDelegate, QStyle,
    QDateEdit, QGridLayout, QDateTimeEdit, QCalendarWidget
)

from PySide6.QtGui import QCursor, QColor, QDrag, QBrush
from PySide6.QtCore import Qt, Signal, QMimeData, QByteArray, QDataStream, QIODevice, QTimer, QDate, QDateTime, QLocale
from core.sound import play_action_sound
from core.events import bus

DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

COLORS_PALETTE = [
    ("Açık Mavi", "#38bdf8"), ("Zümrüt Yeşili", "#10b981"), ("Mor", "#a855f7"),
    ("Turuncu", "#f59e0b"), ("Kırmızı", "#f43f5e"), ("Sarı", "#eab308"),
    ("Pembe", "#ec4899"), ("Okyanus", "#0ea5e9"), ("Gece Mavisi", "#1e3a8a"),
    ("Gül Kurusu", "#be123c"), ("Orman Yeşili", "#15803d"), ("Koyu Mor", "#581c87"),
    ("Turkuaz", "#14b8a6"), ("Kiremit", "#b91c1c"), ("Altın", "#ca8a04"),
    ("Gri", "#71717a"), ("Lila", "#c084fc"), ("Gece Siyahı", "#171717")
]

class TimetableColorDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        background = index.data(Qt.BackgroundRole)
        is_selected = bool(option.state & QStyle.State_Selected)
        if not isinstance(background, QBrush):
            super().paint(painter, option, index)
            return

        painter.save()
        cell_rect = option.rect.adjusted(4, 4, -4, -4)
        
        bg_color = background.color()
        bg_color.setAlpha(50)  
        painter.fillRect(cell_rect, bg_color)
        
        border_color = background.color()
        border_color.setAlpha(255)
        painter.fillRect(cell_rect.x(), cell_rect.y(), 3, cell_rect.height(), border_color)

        foreground = index.data(Qt.ForegroundRole)
        painter.setPen(foreground.color() if isinstance(foreground, QBrush) else QColor("#ffffff"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        painter.drawText(
            cell_rect.adjusted(6, 3, -3, -3), 
            Qt.AlignCenter | Qt.TextWordWrap,
            str(index.data(Qt.DisplayRole) or "")
        )

        if is_selected:
            painter.save()
            painter.setPen(QColor("#38bdf8"))
            painter.drawRect(cell_rect.adjusted(1, 1, -2, -2))
            painter.restore()
            
        painter.restore()

class PersonalPlanDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        def clear_model_value(text):
            if not text:
                index.model().setData(index, "", Qt.EditRole)
        editor.textChanged.connect(clear_model_value)
        return editor
    def paint(self, painter, option, index):
        text = index.data(Qt.DisplayRole)
        is_selected = bool(option.state & QStyle.State_Selected)
        
        painter.save()
        cell_rect = option.rect.adjusted(2, 2, -2, -2)
        
        if text:
            # 1. Yarı saydam arka plan (Mor tonu)
            bg_color = QColor("#8b5cf6")
            bg_color.setAlpha(40)
            painter.fillRect(cell_rect, bg_color)
            
            # 2. Sol belirteç çizgisi
            border_color = QColor("#8b5cf6")
            painter.fillRect(cell_rect.x(), cell_rect.y(), 3, cell_rect.height(), border_color)
            
            # 3. Metin
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                cell_rect.adjusted(8, 2, -4, -2), 
                Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
                str(text)
            )
        else:
            # Boş hücreyi varsayılan çiz
            super().paint(painter, option, index)
            
        # 4. Seçim efekti
        if is_selected:
            painter.save()
            painter.setPen(QColor("#38bdf8"))
            painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
            painter.restore()
            
        painter.restore()

class PersonalPlanTableWidget(QTableWidget):
    def keyPressEvent(self, event):
        # 'Delete' veya 'Backspace' tuşlarına basıldığında seçili hücreleri anında siler
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in self.selectedItems():
                item.setText("")
        else:
            super().keyPressEvent(event)

class InteractiveTimetableWidget(QTableWidget):
    slot_moved = Signal(int, int)
    slot_edit = Signal(dict)
    course_details_requested = Signal(dict)
    course_delete = Signal(int)
    slot_delete = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.doubleClicked.connect(self.on_double_click)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        data = item.data(Qt.UserRole)
        if not data or not data.get("slot_id"): return

        mime_data = QMimeData()
        b_array = QByteArray()
        stream = QDataStream(b_array, QIODevice.WriteOnly)
        stream.writeInt32(data["slot_id"])
        mime_data.setData("application/x-timetable-slot", b_array)

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-timetable-slot"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-timetable-slot"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-timetable-slot"):
            b_array = event.mimeData().data("application/x-timetable-slot")
            stream = QDataStream(b_array, QIODevice.ReadOnly)
            slot_id = stream.readInt32()

            pos = event.position().toPoint()
            target_col = self.columnAt(pos.x())
            if 0 <= target_col < 7:
                event.setDropAction(Qt.CopyAction)
                event.accept()
                self.slot_moved.emit(slot_id, target_col)
            else:
                event.ignore()
        else:
            event.ignore()

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item: return
        data = item.data(Qt.UserRole)
        if not data or not data.get("slot_id"): return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #1c1917; border: 1px solid #292524; color: #ffffff; padding: 4px; border-radius: 6px; }
            QMenu::item { padding: 6px 16px; border-radius: 4px; }
            QMenu::item:selected { background-color: #0284c7; color: white; }
        """)

        action_details = menu.addAction("🔎 Ders Detaylarını Göster")
        action_edit = menu.addAction("✏️ Dersi / Hücreyi Düzenle")
        action_delete_course = menu.addAction("🗑 Dersi Tamamen Sil")
        action_delete = menu.addAction("🗑 Çizelgeden Kaldır")

        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == action_details:
            self.course_details_requested.emit(data)
        elif action == action_edit:
            self.slot_edit.emit(data)
        elif action == action_delete_course:
            self.course_delete.emit(data["course_id"])
        elif action == action_delete:
            self.slot_delete.emit(data["slot_id"])

    def on_double_click(self, index):
        item = self.item(index.row(), index.column())
        if item:
            data = item.data(Qt.UserRole)
            if data and data.get("slot_id"):
                self.course_details_requested.emit(data)

class AssessmentCard(QFrame):
    score_updated = Signal(int, float)
    deleted = Signal(int)

    def __init__(self, data: dict):
        super().__init__()
        self.data = data
        self.setObjectName("Card")
        self.setStyleSheet("""
            QFrame#Card { background-color: #18181b; border: 1px solid #27272a; border-radius: 10px; padding: 12px; }
            QFrame#Card:hover { border-color: #3f3f46; }
        """)
        self.init_ui()

    def init_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(16)

        info_lay = QVBoxLayout()
        info_lay.setSpacing(2)
        
        c_code = self.data.get("code", "")
        title_text = self.data.get("title", "")
        lbl_title = QLabel(f"<b>{c_code}:</b> {title_text}")
        lbl_title.setStyleSheet("font-size: 14px; color: #ffffff;")
        
        due = self.data.get("due_date", "")
        lbl_date = QLabel(f"📅 Teslim / Sınav Tarihi: {due}")
        lbl_date.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        
        info_lay.addWidget(lbl_title)
        info_lay.addWidget(lbl_date)
        lay.addLayout(info_lay, stretch=2)

        weight = self.data.get("weight", 0.0)
        lbl_weight = QLabel(f"Ağırlık: %{weight:.0f}")
        lbl_weight.setStyleSheet("background-color: #27272a; color: #38bdf8; font-weight: 700; font-size: 12px; padding: 5px 10px; border-radius: 6px;")
        lay.addWidget(lbl_weight)

        score = self.data.get("score")
        if score is not None:
            if score >= 90: letter = "AA"
            elif score >= 85: letter = "BA"
            elif score >= 80: letter = "BB"
            elif score >= 75: letter = "CB"
            elif score >= 65: letter = "CC"
            elif score >= 58: letter = "DC"
            elif score >= 50: letter = "DD"
            else: letter = "FF"
            
            point_4 = (score * 3 - 20) / 70 if score >= 30 else 0.0
            point_4 = max(0.0, min(4.0, point_4))
            
            score_text = f"Not: {score:.1f} ({letter}) | {point_4:.2f}"
            score_color = "#10b981" if score >= 60 else "#ef4444"
        else:
            score_text = "Girilmedi"
            score_color = "#71717a"

        lbl_score = QLabel(score_text)
        lbl_score.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {score_color}; min-width: 75px;")
        lbl_score.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl_score)

        btn_score = QPushButton("Notu Güncelle" if score is not None else "Not Gir")
        btn_score.setCursor(QCursor(Qt.PointingHandCursor))
        btn_score.setStyleSheet("padding: 5px 12px; font-size: 12px; font-weight: 600;")
        btn_score.clicked.connect(self.dialog_enter_score)
        lay.addWidget(btn_score)

        btn_del = QPushButton("🗑")
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setStyleSheet("background: transparent; color: #71717a; border: none; font-size: 14px;")
        btn_del.clicked.connect(lambda: self.deleted.emit(self.data["id"]))
        lay.addWidget(btn_del)

    def dialog_enter_score(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Not Değerini Girin")
        dlg.resize(260, 140)
        lay = QVBoxLayout(dlg)

        spin = QDoubleSpinBox()
        spin.setRange(0, 100)
        curr = self.data.get("score")
        spin.setValue(curr if curr is not None else 80.0)
        spin.setSuffix(" / 100")
        
        lay.addWidget(QLabel("Aldığınız Not:"))
        lay.addWidget(spin)

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        lay.addWidget(btn_save)

        def save():
            self.score_updated.emit(self.data["id"], spin.value())
            dlg.accept()

        btn_save.clicked.connect(save)
        dlg.exec()

class TimetableView(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        
        # Gelecek 6 yılı ve geçmiş 3 yılı dinamik olarak oluştur (Toplam 10 yıllık menzil)
        curr_y = QDate.currentDate().year()
        if QDate.currentDate().month() < 8: curr_y -= 1
        self.default_year = f"{curr_y}-{curr_y+1}"
        self.years_list = [f"{y}-{y+1}" for y in range(curr_y - 3, curr_y + 7)]
        
        self.run_migrations()
        self.init_ui()

    def run_migrations(self):
        """Veritabanına Dönem sütunlarını ekler ve 'UNIQUE' (Benzersizlik) kısıtlamasını kaldırır."""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys = OFF")
            
            migrations = [
                "ALTER TABLE courses ADD COLUMN term TEXT DEFAULT 'Güz'",
                f"ALTER TABLE courses ADD COLUMN year TEXT DEFAULT '{self.default_year}'",
                "ALTER TABLE timetable ADD COLUMN cell_color TEXT"
            ]
            for mig in migrations:
                try: cur.execute(mig)
                except Exception: pass
            
            # UNIQUE Hatasını çözmek için 'courses' tablosu kısıtlama olmadan yeniden yaratılıyor
            cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='courses'")
            create_sql = cur.fetchone()
            if create_sql and "UNIQUE" in create_sql[0].upper():
                try:
                    cur.execute("""
                        CREATE TABLE courses_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            code TEXT, name TEXT, instructor TEXT, 
                            instructor_contact TEXT, classroom TEXT, 
                            credit INTEGER, color_hex TEXT, 
                            year TEXT, term TEXT
                        )
                    """)
                    cur.execute("""
                        INSERT INTO courses_new (id, code, name, instructor, instructor_contact, classroom, credit, color_hex, year, term) 
                        SELECT id, code, name, instructor, instructor_contact, classroom, credit, color_hex, year, term FROM courses
                    """)
                    cur.execute("DROP TABLE courses")
                    cur.execute("ALTER TABLE courses_new RENAME TO courses")
                except Exception as e:
                    print("Migration Error:", e)
                    
            cur.execute("PRAGMA foreign_keys = ON")
            conn.commit()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        tabs = QTabWidget()
        tabs.addTab(self.create_schedule_tab(), "📅 Haftalık Ders Çizelgesi")
        tabs.addTab(self.create_grades_tab(), "🎯 Sınavlar ve Akademik Not Takibi")
        tabs.addTab(self.create_personal_plan_tab(), "📝 Kişisel Plan")
        layout.addWidget(tabs)

    def create_schedule_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(12)

        top_bar = QHBoxLayout()
        btn_add_course = QPushButton("🎓  Yeni Ders Tanımla")
        btn_add_course.setObjectName("PrimaryCourseButton")
        btn_add_course.setMinimumHeight(42)
        btn_add_course.setMinimumWidth(190)
        btn_add_course.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_course.setStyleSheet("""
            QPushButton#PrimaryCourseButton { background-color: #38bdf8; color: #082f49; border: 1px solid #7dd3fc; border-radius: 9px; padding: 9px 18px; font-size: 13px; font-weight: 800; }
            QPushButton#PrimaryCourseButton:hover { background-color: #7dd3fc; border-color: #bae6fd; }
        """)
        btn_add_course.clicked.connect(self.dialog_add_course)

        btn_add_slot = QPushButton("🕒  Çizelgeye Ders Ekle")
        btn_add_slot.setObjectName("SecondaryScheduleButton")
        btn_add_slot.setMinimumHeight(42)
        btn_add_slot.setMinimumWidth(200)
        btn_add_slot.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_slot.setStyleSheet("""
            QPushButton#SecondaryScheduleButton { background-color: #14532d; color: #dcfce7; border: 1px solid #22c55e; border-radius: 9px; padding: 9px 16px; font-size: 13px; font-weight: 800; }
            QPushButton#SecondaryScheduleButton:hover { background-color: #166534; border-color: #4ade80; color: #f0fdf4; }
        """)
        btn_add_slot.clicked.connect(self.dialog_add_schedule)

        self.filter_year = QComboBox()
        self.filter_year.addItems(self.years_list)
        self.filter_year.setCurrentText(self.default_year)
        self.filter_year.setStyleSheet("background-color: #27272a; color: white; border-radius: 6px; padding: 8px; font-weight: bold;")
        self.filter_year.currentTextChanged.connect(self.load_schedule)

        self.filter_term = QComboBox()
        self.filter_term.addItems(["Güz", "Bahar", "Yaz"])
        
        # Otomatik olarak Güz veya Bahar dönemini belirle
        curr_month = QDate.currentDate().month()
        if 2 <= curr_month <= 6: self.filter_term.setCurrentText("Bahar")
        elif 7 <= curr_month <= 8: self.filter_term.setCurrentText("Yaz")
        else: self.filter_term.setCurrentText("Güz")
        
        self.filter_term.setStyleSheet("background-color: #27272a; color: white; border-radius: 6px; padding: 8px; font-weight: bold;")
        self.filter_term.currentTextChanged.connect(self.load_schedule)

        top_bar.addWidget(btn_add_course)
        top_bar.addWidget(btn_add_slot)
        top_bar.addSpacing(16)
        lbl_filter = QLabel("📌 Dönem Filtresi:")
        lbl_filter.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        top_bar.addWidget(lbl_filter)
        top_bar.addWidget(self.filter_year)
        top_bar.addWidget(self.filter_term)
        top_bar.addStretch()
        lay.addLayout(top_bar)

        self.table = InteractiveTimetableWidget()
        self.table.setItemDelegate(TimetableColorDelegate(self.table))
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(DAYS_TR)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: #1c1917; color: #e4e4e7; border: 1px solid #292524; padding: 8px; font-weight: 700; }")
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #0f0d0c; border: 1px solid #2b2927; border-radius: 12px; gridline-color: rgba(255,255,255,0.06); color: #f4f4f5; }
            QTableWidget::item { padding: 6px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04); }
            QTableWidget::item:selected { background-color: rgba(56, 189, 248, 0.15); border: 1px solid #38bdf8; }
        """)

        self.table.slot_moved.connect(self.handle_slot_moved)
        self.table.slot_edit.connect(self.dialog_edit_slot)
        self.table.course_details_requested.connect(self.show_course_details)
        self.table.course_delete.connect(self.delete_course)
        self.table.slot_delete.connect(self.delete_slot)

        lay.addWidget(self.table)
        self.load_schedule()
        return tab

    def load_schedule(self):
        self.table.setRowCount(8)
        for r in range(8):
            self.table.setRowHeight(r, 92)
            for c in range(7):
                item = QTableWidgetItem("")
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(r, c, item)

        selected_year = self.filter_year.currentText()
        selected_term = self.filter_term.currentText()

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                  SELECT t.id, t.day_of_week, t.start_time, t.end_time, t.cell_color,
                      c.code, c.name, c.credit,
                      t.instructor, t.instructor_contact, t.classroom,
                      c.color_hex, t.course_id
                FROM timetable t
                JOIN courses c ON t.course_id = c.id
                WHERE c.year = ? AND c.term = ?
                ORDER BY t.start_time ASC
            """, (selected_year, selected_term))
            slots = cur.fetchall()

        day_counters = {d: 0 for d in range(7)}
        for s in slots:
            dow = s["day_of_week"]
            row_idx = day_counters[dow]
            if row_idx < 8:
                c_color = s["cell_color"] if s["cell_color"] else (s["color_hex"] if s["color_hex"] else "#38bdf8")
                text = f"{s['code']}\n{s['start_time']} - {s['end_time']}\n({s['classroom'] or 'Amfi belirtilmedi'})\n{s['instructor'] or 'Hoca girilmedi'}"
                
                bg_color = QColor(c_color)
                if not bg_color.isValid(): bg_color = QColor("#38bdf8")
                bg_color.setAlpha(230)
                
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
                item.setForeground(QColor("#ffffff"))
                item.setToolTip(f"{s['name']} (Kredi: {s['credit']})\n{DAYS_TR[s['day_of_week']]} • {s['start_time']} - {s['end_time']}")
                item.setBackground(QBrush(bg_color))
                
                item.setData(Qt.UserRole, {
                    "slot_id": s["id"],
                    "course_id": s["course_id"],
                    "code": s["code"],
                    "name": s["name"],
                    "day_of_week": s["day_of_week"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "classroom": s["classroom"] or "",
                    "instructor": s["instructor"] or "",
                    "instructor_contact": s["instructor_contact"] or "",
                    "cell_color": s["cell_color"] or "",
                    "credit": s["credit"] or 3
                })
                
                self.table.setItem(row_idx, dow, item)
                day_counters[dow] += 1

    def handle_slot_moved(self, slot_id: int, new_day_of_week: int):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE timetable SET day_of_week = ? WHERE id = ?", (new_day_of_week, slot_id))
            conn.commit()
            play_action_sound("save")
        self.load_schedule()
        bus.courses_changed.emit()

    def dialog_edit_slot(self, slot_data: dict):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Hücre & Ders Düzenle — {slot_data['code']}")
        dlg.resize(340, 380)
        lay = QVBoxLayout(dlg)

        lbl = QLabel(f"<b>{slot_data['code']} — {slot_data['name']}</b>")
        lbl.setStyleSheet("font-size: 14px; color: #38bdf8;")
        lay.addWidget(lbl)

        day_box = QComboBox()
        for i, d in enumerate(DAYS_TR):
            day_box.addItem(d, i)
        day_box.setCurrentIndex(slot_data["day_of_week"])

        start_in = QLineEdit(slot_data["start_time"])
        end_in = QLineEdit(slot_data["end_time"])
        room_in = QLineEdit(slot_data["classroom"])
        instructor_in = QLineEdit(slot_data["instructor"])
        instructor_contact_in = QLineEdit(slot_data.get("instructor_contact", ""))

        credit_in = QSpinBox()
        credit_in.setRange(0, 20)
        credit_in.setValue(int(slot_data.get("credit", 3)))

        color_box = QComboBox()
        color_box.setStyleSheet("background-color: #27272a; padding: 6px; border-radius: 4px; color: white;")
        color_box.addItem("Dersin Varsayılan Rengini Kullan", "")
        
        for name, hex_code in COLORS_PALETTE:
            color_box.addItem(name, hex_code)
            idx = color_box.count() - 1
            color_box.setItemData(idx, QColor(hex_code), Qt.DecorationRole)
            
        current_cell_color = slot_data.get("cell_color") or ""
        idx = color_box.findData(current_cell_color)
        if idx >= 0: color_box.setCurrentIndex(idx)

        grid = QGridLayout()
        grid.addWidget(QLabel("Gün:"), 0, 0); grid.addWidget(day_box, 0, 1)
        grid.addWidget(QLabel("Başlangıç:"), 1, 0); grid.addWidget(start_in, 1, 1)
        grid.addWidget(QLabel("Bitiş:"), 2, 0); grid.addWidget(end_in, 2, 1)
        grid.addWidget(QLabel("Derslik:"), 3, 0); grid.addWidget(room_in, 3, 1)
        grid.addWidget(QLabel("Ders Kredisi:"), 4, 0); grid.addWidget(credit_in, 4, 1)
        grid.addWidget(QLabel("Hücre Özel Rengi:"), 5, 0); grid.addWidget(color_box, 5, 1)
        
        lay.addLayout(grid)
        lay.addWidget(QLabel("Öğretim Görevlisi:")); lay.addWidget(instructor_in)
        
        btn_save = QPushButton("Güncelle")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        lay.addWidget(btn_save)

        def save():
            selected_color = color_box.currentData()
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE timetable 
                    SET day_of_week = ?, start_time = ?, end_time = ?,
                        classroom = ?, instructor = ?, instructor_contact = ?, cell_color = ?
                    WHERE id = ?
                """, (day_box.currentData(), start_in.text().strip(), end_in.text().strip(),
                      room_in.text().strip(), instructor_in.text().strip(), instructor_contact_in.text().strip(), 
                      selected_color, slot_data["slot_id"]))
                
                cur.execute("UPDATE courses SET credit = ? WHERE id = ?", (credit_in.value(), slot_data["course_id"]))
                conn.commit()
                
            play_action_sound("save")
            dlg.accept()
            self.load_schedule()
            bus.courses_changed.emit()

        btn_save.clicked.connect(save)
        dlg.exec()

    def delete_slot(self, slot_id: int):
        confirm = QMessageBox.question(self, "Onay", "Bu ders saatini çizelgeden silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM timetable WHERE id = ?", (slot_id,))
                conn.commit()
            play_action_sound("delete")
            self.load_schedule()
            bus.courses_changed.emit()

    def delete_course(self, course_id: int):
        confirm = QMessageBox.question(self, "Dersi Tamamen Sil", "Bu dersi tamamen silmek istiyor musunuz?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                conn.execute("UPDATE materials SET course_id = NULL WHERE course_id = ?", (course_id,))
                conn.execute("DELETE FROM timetable WHERE course_id = ?", (course_id,))
                conn.execute("DELETE FROM assessments WHERE course_id = ?", (course_id,))
                conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
                conn.commit()
            self.load_schedule()
            bus.courses_changed.emit()
            bus.assessments_changed.emit()

    def show_course_details(self, slot_data: dict):
        try:
            with self.db.get_connection() as conn:
                course = conn.execute("""
                    SELECT code, name, instructor, instructor_contact, classroom, credit, year, term, color_hex
                    FROM courses WHERE id = ?
                """, (slot_data["course_id"],)).fetchone()
                
                slot = conn.execute("""
                    SELECT id, start_time, end_time, instructor, instructor_contact, classroom
                    FROM timetable WHERE id = ?
                """, (slot_data.get("slot_id"),)).fetchone()

            if not course: return

            slot_instructor = (slot["instructor"] if slot else None) or "Belirtilmemiş"
            slot_contact = (slot["instructor_contact"] if slot else None) or "Belirtilmemiş"
            slot_classroom = (slot["classroom"] if slot else None) or "Belirtilmemiş"

            dlg = QDialog(self)
            dlg.setWindowTitle(f"Ders Detayları - {course['code']}")
            dlg.resize(440, 380)
            dlg.setStyleSheet("QDialog { background-color: #141210; color: #f4f4f5; }")
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(18, 18, 18, 18)
            lay.setSpacing(12)

            header = QFrame()
            header.setStyleSheet("QFrame { background-color: #1c1917; border: 1px solid #292524; border-radius: 12px; }")
            header_lay = QVBoxLayout(header)
            header_lay.setContentsMargins(14, 12, 14, 12)

            # Sözlük erişimlerini güvenli hale getirdik (.keys() kontrolü ile)
            term_info = f"{course['year']} - {course['term']} Dönemi" if 'year' in course.keys() else ""
            
            code_label = QLabel(f"{course['code']}   |   <span style='color: #a1a1aa; font-weight: 500;'>{term_info}</span>")
            code_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #7dd3fc; letter-spacing: 1px;")
            title_label = QLabel(f"{course['name']}")
            title_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
            
            header_lay.addWidget(code_label)
            header_lay.addWidget(title_label)
            lay.addWidget(header)

            info = QFrame()
            info.setStyleSheet("QFrame { background-color: #18181b; border: 1px solid #27272a; border-radius: 12px; }")
            info_lay = QGridLayout(info)
            info_lay.setContentsMargins(12, 12, 12, 12)
            info_lay.setHorizontalSpacing(16)
            info_lay.setVerticalSpacing(10)

            rows = [
                ("Kredi", f"{course['credit'] or 0}"),
                ("Derslik", slot_classroom),
                ("Saat", f"{slot['start_time'] if slot and slot['start_time'] else slot_data.get('start_time', '')} - {slot['end_time'] if slot and slot['end_time'] else slot_data.get('end_time', '')}"),
                ("Hoca", slot_instructor),
                ("İletişim", slot_contact),
            ]

            for i, (label, value) in enumerate(rows):
                row_bg = QFrame()
                row_bg.setStyleSheet("QFrame { background: rgba(255,255,255,0.02); border-radius: 8px; }")
                row_lay = QHBoxLayout(row_bg)
                row_lay.setContentsMargins(10, 8, 10, 8)

                title_widget = QLabel(label)
                title_widget.setStyleSheet("font-size: 11px; color: #a1a1aa; font-weight: 700;")
                value_widget = QLabel(str(value))
                value_widget.setWordWrap(True)
                value_widget.setStyleSheet("font-size: 13px; color: #f4f4f5; font-weight: 600;")

                row_lay.addWidget(title_widget)
                row_lay.addStretch()
                row_lay.addWidget(value_widget)
                info_lay.addWidget(row_bg, i, 0, 1, 2)

            lay.addWidget(info)

            buttons = QHBoxLayout()
            btn_edit = QPushButton("Düzenle")
            btn_edit.setObjectName("AccentButton")
            btn_edit.setCursor(QCursor(Qt.PointingHandCursor))
            
            btn_copy = QPushButton("🔄 Döneme Kopyala")
            btn_copy.setStyleSheet("background-color: #0ea5e9; color: #ffffff; border-radius: 6px; padding: 7px 10px; font-weight: 600;")
            btn_copy.setCursor(QCursor(Qt.PointingHandCursor))
            
            btn_delete = QPushButton("Dersi Sil")
            btn_delete.setStyleSheet("background-color: #1f1b18; color: #fca5a5; border: 1px solid #f43f5e; border-radius: 6px; padding: 7px 10px; font-weight: 600;")
            btn_delete.setCursor(QCursor(Qt.PointingHandCursor))
            
            btn_close = QPushButton("Kapat")
            btn_close.setStyleSheet("background-color: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 6px; padding: 7px 10px; font-weight: 600;")
            btn_close.setCursor(QCursor(Qt.PointingHandCursor))
            
            buttons.addWidget(btn_edit)
            buttons.addWidget(btn_copy)
            buttons.addWidget(btn_delete)
            buttons.addWidget(btn_close)
            lay.addLayout(buttons)

            btn_close.clicked.connect(dlg.reject)

            def edit_course():
                dlg.accept()
                # Arayüz kilitlenmesini engellemek için 0.1 saniye gecikme ile açıyoruz
                QTimer.singleShot(100, lambda: self.dialog_edit_slot(slot_data))

            def copy_course():
                dlg.accept()
                QTimer.singleShot(100, lambda: self.dialog_copy_course(slot_data["course_id"]))

            def delete_course():
                dlg.reject()
                QTimer.singleShot(100, lambda: self.delete_course(slot_data["course_id"]))

            btn_edit.clicked.connect(edit_course)
            btn_copy.clicked.connect(copy_course)
            btn_delete.clicked.connect(delete_course)
            dlg.exec()
            
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Arayüz Hatası", f"Detay ekranı açılırken hata oluştu:\n{e}\n\nDetay:\n{traceback.format_exc()}")
    def dialog_copy_course(self, course_id: int):
        try:
            with self.db.get_connection() as conn:
                row = conn.execute("""
                    SELECT code, name, instructor, instructor_contact, classroom, credit, color_hex, year, term
                    FROM courses WHERE id = ?
                """, (course_id,)).fetchone()

            if not row: return
            
            # sqlite3.Row objesini standart Python Sözlüğüne (Dict) çevirerek sessiz hataları önlüyoruz
            course = dict(row)

            dlg = QDialog(self)
            dlg.setWindowTitle("Dersi Başka Döneme Kopyala")
            dlg.resize(360, 380)
            lay = QVBoxLayout(dlg)

            info_lbl = QLabel(f"<b>{course.get('code', '')} - {course.get('name', '')}</b> dersini yeni bir döneme aktarıyorsunuz. Saat/Program bilgisi kopyalanmaz, yalnızca ders tanımı aktarılır.")
            info_lbl.setWordWrap(True)
            info_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; margin-bottom: 10px;")
            lay.addWidget(info_lbl)

            year_box = QComboBox()
            year_box.addItems(self.years_list)
            year_box.setCurrentText(str(course.get("year", "")) if course.get("year") else self.default_year)

            term_box = QComboBox()
            term_box.addItems(["Güz", "Bahar", "Yaz"])
            term_box.setCurrentText(self.filter_term.currentText())

            code_in = QLineEdit(str(course.get("code", "")))  
            name_in = QLineEdit(str(course.get("name", "")))
            
            cred_in = QSpinBox()
            cred_in.setRange(0, 20)
            # Eğer eski veritabanı kayıtlarında kredi boş bırakıldıysa (None/Empty) güvenle 3 olarak ata
            try:
                credit_val = int(course.get("credit", 3) or 3)
            except (ValueError, TypeError):
                credit_val = 3
            cred_in.setValue(credit_val)

            color_box = QComboBox()
            color_box.setStyleSheet("background-color: #27272a; padding: 6px; border-radius: 4px; color: white;")
            for name, hex_code in COLORS_PALETTE:
                color_box.addItem(name, hex_code)
                idx = color_box.count() - 1
                color_box.setItemData(idx, QColor(hex_code), Qt.DecorationRole)
            
            idx = color_box.findData(course.get("color_hex", ""))
            if idx >= 0: color_box.setCurrentIndex(idx)

            grid = QGridLayout()
            grid.addWidget(QLabel("Yeni Yıl:"), 0, 0); grid.addWidget(year_box, 0, 1)
            grid.addWidget(QLabel("Yeni Dönem:"), 1, 0); grid.addWidget(term_box, 1, 1)
            grid.addWidget(QLabel("Ders Kodu:"), 2, 0); grid.addWidget(code_in, 2, 1)
            grid.addWidget(QLabel("Ders Adı:"), 3, 0); grid.addWidget(name_in, 3, 1)
            grid.addWidget(QLabel("Kredi:"), 4, 0); grid.addWidget(cred_in, 4, 1)
            grid.addWidget(QLabel("Renk:"), 5, 0); grid.addWidget(color_box, 5, 1)
            lay.addLayout(grid)

            btn_save = QPushButton("Kopyala ve Ekle")
            btn_save.setObjectName("AccentButton")
            btn_save.setCursor(QCursor(Qt.PointingHandCursor))
            lay.addWidget(btn_save)

            def save():
                new_code = code_in.text().strip()
                if not new_code:
                    QMessageBox.warning(dlg, "Uyarı", "Ders kodu boş bırakılamaz.")
                    return
                try:
                    with self.db.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO courses (code, name, instructor, instructor_contact, classroom, credit, color_hex, year, term)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (new_code, name_in.text().strip(), 
                              course.get("instructor", ""), 
                              course.get("instructor_contact", ""), 
                              course.get("classroom", ""), 
                              cred_in.value(), 
                              color_box.currentData(), 
                              year_box.currentText(), 
                              term_box.currentText()))
                        conn.commit()
                    
                    try: 
                        from core.sound import play_action_sound
                        play_action_sound("save")
                    except: 
                        pass
                    
                    dlg.accept()
                    self.filter_year.setCurrentText(year_box.currentText())
                    self.filter_term.setCurrentText(term_box.currentText())
                    self.load_schedule()
                    from core.events import bus
                    bus.courses_changed.emit()
                    
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    QMessageBox.critical(dlg, "Veritabanı Hatası", f"Ders kopyalanamadı.\n\nHata Özeti:\n{e}\n\nDetay:\n{error_details}")

            btn_save.clicked.connect(save)
            dlg.exec()
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMessageBox.critic

    def dialog_add_course(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Ders Tanımla")
        dlg.resize(320, 340)
        lay = QVBoxLayout(dlg)

        code_in = QLineEdit(); code_in.setPlaceholderText("Ders Kodu (Örn: MATH101)")
        name_in = QLineEdit(); name_in.setPlaceholderText("Ders Adı (Örn: Calculus I)")
        inst_in = QLineEdit(); inst_in.setPlaceholderText("Öğretim Üyesi")
        room_in = QLineEdit(); room_in.setPlaceholderText("Derslik / Amfi")
        cred_in = QSpinBox(); cred_in.setValue(3); cred_in.setPrefix("Kredi: ")

        year_box = QComboBox()
        year_box.addItems(self.years_list)
        year_box.setCurrentText(self.filter_year.currentText())

        term_box = QComboBox()
        term_box.addItems(["Güz", "Bahar", "Yaz"])
        term_box.setCurrentText(self.filter_term.currentText())

        color_box = QComboBox()
        color_box.setStyleSheet("background-color: #27272a; padding: 6px; border-radius: 4px; color: white;")
        for name, hex_code in COLORS_PALETTE:
            color_box.addItem(name, hex_code)
            idx = color_box.count() - 1
            color_box.setItemData(idx, QColor(hex_code), Qt.DecorationRole)

        lay.addWidget(QLabel("Ders Kodu ve Adı:")); lay.addWidget(code_in); lay.addWidget(name_in)
        lay.addWidget(QLabel("Eğitmen ve Sınıf:")); lay.addWidget(inst_in); lay.addWidget(room_in)
        
        grid = QGridLayout()
        grid.addWidget(QLabel("Kredi:"), 0, 0); grid.addWidget(cred_in, 0, 1)
        grid.addWidget(QLabel("Yıl:"), 1, 0); grid.addWidget(year_box, 1, 1)
        grid.addWidget(QLabel("Dönem:"), 2, 0); grid.addWidget(term_box, 2, 1)
        grid.addWidget(QLabel("Ana Renk:"), 3, 0); grid.addWidget(color_box, 3, 1)
        lay.addLayout(grid)

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        lay.addWidget(btn_save)

        def save():
            if not code_in.text().strip(): return
            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO courses (code, name, instructor, classroom, credit, color_hex, year, term)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (code_in.text().strip(), name_in.text().strip(), inst_in.text().strip(),
                          room_in.text().strip(), cred_in.value(), color_box.currentData(), 
                          year_box.currentText(), term_box.currentText()))
                    conn.commit()
                dlg.accept()
                self.load_schedule()
                bus.courses_changed.emit()
            except Exception as e:
                pass

        btn_save.clicked.connect(save)
        dlg.exec()

    def dialog_add_schedule(self):
        sel_year = self.filter_year.currentText()
        sel_term = self.filter_term.currentText()
        
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            # YENİ: Yalnızca arayüzdeki filtrede seçili olan dönemin dersleri gösterilir!
            cur.execute("SELECT id, code, name FROM courses WHERE year = ? AND term = ? ORDER BY code ASC", (sel_year, sel_term))
            courses = cur.fetchall()

        if not courses: 
            QMessageBox.information(self, "Bilgi", f"Seçili dönemde ({sel_year} - {sel_term}) tanımlı ders yok.\nÖnce 'Yeni Ders Tanımla' butonuyla ders ekleyin.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Çizelgeye Ders Saati Ekle")
        dlg.resize(320, 240)
        lay = QVBoxLayout(dlg)

        c_box = QComboBox()
        for c in courses: c_box.addItem(f"{c['code']} - {c['name']}", c['id'])

        day_box = QComboBox()
        for i, d in enumerate(DAYS_TR): day_box.addItem(d, i)

        start_in = QLineEdit("09:30")
        end_in = QLineEdit("11:20")
        room_in = QLineEdit()

        lay.addWidget(QLabel("Ders:")); lay.addWidget(c_box)
        lay.addWidget(QLabel("Gün ve Saatler:")); lay.addWidget(day_box)
        lay.addWidget(start_in); lay.addWidget(end_in)
        lay.addWidget(QLabel("Derslik / Amfi:")); lay.addWidget(room_in)

        btn_save = QPushButton("Ekle")
        btn_save.setObjectName("AccentButton")
        lay.addWidget(btn_save)

        def save():
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO timetable (course_id, day_of_week, start_time, end_time, classroom)
                    VALUES (?, ?, ?, ?, ?)
                """, (c_box.currentData(), day_box.currentData(), start_in.text().strip(), end_in.text().strip(), room_in.text().strip()))
                conn.commit()
            dlg.accept()
            self.load_schedule()
            bus.courses_changed.emit()

        btn_save.clicked.connect(save)
        dlg.exec()

    # -------------------------------------------------------------------------
    # TAB 2: SINAVLAR VE AKADEMİK NOT TAKİBİ
    # -------------------------------------------------------------------------
    def create_grades_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(14)

        filter_bar = QHBoxLayout()
        lbl_filter = QLabel("📌 Sınav & Not Filtresi:")
        lbl_filter.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        
        self.grades_filter_year = QComboBox()
        self.grades_filter_year.addItem("Tüm Yıllar")
        self.grades_filter_year.addItems(self.years_list)
        self.grades_filter_year.setStyleSheet("background-color: #27272a; color: white; border-radius: 6px; padding: 6px; font-weight: bold;")
        self.grades_filter_year.currentTextChanged.connect(self.load_assessments)

        self.grades_filter_term = QComboBox()
        self.grades_filter_term.addItems(["Tüm Dönemler", "Güz", "Bahar", "Yaz"])
        self.grades_filter_term.setStyleSheet("background-color: #27272a; color: white; border-radius: 6px; padding: 6px; font-weight: bold;")
        self.grades_filter_term.currentTextChanged.connect(self.load_assessments)

        filter_bar.addWidget(lbl_filter)
        filter_bar.addWidget(self.grades_filter_year)
        filter_bar.addWidget(self.grades_filter_term)
        filter_bar.addStretch()
        lay.addLayout(filter_bar)

        summary_card = QFrame()
        summary_card.setObjectName("Card")
        sum_lay = QHBoxLayout(summary_card)
        sum_lay.setContentsMargins(16, 12, 16, 12)

        self.lbl_gpa = QLabel("Dönem Ort. (SPA): -  |  Genel Ort. (CGPA): -")
        self.lbl_gpa.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff;")

        self.lbl_letter = QLabel("Kredi (Dönem/Genel): -")
        self.lbl_letter.setStyleSheet("font-size: 14px; font-weight: 700; color: #10b981; margin-left: 16px;")

        btn_add_assessment = QPushButton("📅  Yeni Sınav / Değerlendirme")
        btn_add_assessment.setObjectName("AssessmentAddButton")
        btn_add_assessment.setMinimumSize(225, 42)
        btn_add_assessment.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_assessment.setStyleSheet("""
            QPushButton#AssessmentAddButton { background-color: #9a3412; color: #fff7ed; border: 1px solid #fb923c; border-radius: 9px; padding: 9px 16px; font-size: 13px; font-weight: 800; }
            QPushButton#AssessmentAddButton:hover { background-color: #c2410c; border-color: #fdba74; }
        """)
        btn_add_assessment.clicked.connect(self.dialog_add_assessment)

        sum_lay.addWidget(self.lbl_gpa)
        sum_lay.addWidget(self.lbl_letter)
        sum_lay.addStretch()
        sum_lay.addWidget(btn_add_assessment)
        lay.addWidget(summary_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        self.assessments_content = QWidget()
        self.assessments_lay = QVBoxLayout(self.assessments_content)
        self.assessments_lay.setContentsMargins(0, 0, 0, 0)
        self.assessments_lay.setSpacing(10)
        self.assessments_lay.addStretch()

        scroll.setWidget(self.assessments_content)
        lay.addWidget(scroll)

        self.load_assessments()
        return tab

    def load_assessments(self):
        while self.assessments_lay.count() > 1:
            item = self.assessments_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        selected_year = self.grades_filter_year.currentText()
        selected_term = self.grades_filter_term.currentText()

        query = """
            SELECT a.id, a.course_id, a.title, a.weight, a.score, a.due_date, 
                   c.code, c.credit, c.term, c.year, c.name
            FROM assessments a
            JOIN courses c ON a.course_id = c.id
        """
        params = []
        conditions = []
        
        if selected_year != "Tüm Yıllar":
            conditions.append("c.year = ?")
            params.append(selected_year)
        if selected_term != "Tüm Dönemler":
            conditions.append("c.term = ?")
            params.append(selected_term)
            
        if conditions: query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY c.year DESC, c.term DESC, c.code ASC, a.due_date ASC"

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            
            cur.execute("""
                SELECT a.score, a.weight, c.code, c.credit, c.year, c.term
                FROM assessments a JOIN courses c ON a.course_id = c.id
            """)
            all_rows = cur.fetchall()

        def calc_gpa_from_rows(data_rows):
            course_map = {}
            for r in data_rows:
                c_code = r["code"]
                if c_code not in course_map: course_map[c_code] = {"score": 0.0, "weight": 0.0, "credit": r["credit"] or 0}
                if r["score"] is not None:
                    course_map[c_code]["score"] += r["score"] * (r["weight"] / 100.0)
                    course_map[c_code]["weight"] += r["weight"]
                    
            t_points = 0.0
            t_credits = 0.0
            for c_code, data in course_map.items():
                if data["weight"] > 0:
                    avg = (data["score"] / data["weight"]) * 100.0
                    gpa_4 = max(0.0, min(4.0, (avg * 3 - 20) / 70 if avg >= 30 else 0.0))
                    t_points += (gpa_4 * data["credit"])
                    t_credits += data["credit"]
            return t_points, t_credits

        genel_points, genel_credits = calc_gpa_from_rows(all_rows)
        donem_points, donem_credits = calc_gpa_from_rows(rows)

        grouped_assessments = {}
        for r in rows:
            data = dict(r)
            yt_key = f"{data['year'] or self.default_year} - {data['term'] or 'Güz'}"
            c_code = data["code"]
            
            if yt_key not in grouped_assessments: grouped_assessments[yt_key] = []
            grouped_assessments[yt_key].append(data)

        # Dönemlere göre başlıkları oluştur (Yanına Dönem Ortalamasını Yaz)
        for yt_key, items in grouped_assessments.items():
            # O döneme ait ortalamayı hesapla
            term_points, term_credits = calc_gpa_from_rows(items)
            term_gpa = term_points / term_credits if term_credits > 0 else 0.0
            term_gpa_str = f" | Dönem Ortalaması (SPA): {term_gpa:.2f}" if term_credits > 0 else " | Henüz Not Girilmedi"

            lbl_yt = QLabel(f"🗓️ {yt_key} Dönemi {term_gpa_str}")
            lbl_yt.setStyleSheet("font-size: 16px; font-weight: 900; color: #f59e0b; margin-top: 16px; border-bottom: 2px solid #f59e0b; padding-bottom: 4px;")
            self.assessments_lay.insertWidget(self.assessments_lay.count() - 1, lbl_yt)
            
            # Dersleri kendi içinde tekrar grupla
            course_grouped = {}
            for data in items:
                c_code = data["code"]
                if c_code not in course_grouped:
                    course_grouped[c_code] = []
                course_grouped[c_code].append(data)

            for c_code, c_items in course_grouped.items():
                c_credit = c_items[0]["credit"] or 0
                lbl_category = QLabel(f"📚 {c_code} Değerlendirmeleri (Kredi: {c_credit})")
                lbl_category.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8; margin-top: 8px; margin-left: 10px;")
                self.assessments_lay.insertWidget(self.assessments_lay.count() - 1, lbl_category)
                
                for data in c_items:
                    card = AssessmentCard(data)
                    card.score_updated.connect(self.update_score)
                    card.deleted.connect(self.delete_assessment)
                    self.assessments_lay.insertWidget(self.assessments_lay.count() - 1, card)

        if not rows:
            empty = QLabel("Seçilen döneme ait sınav veya ödev bulunmuyor.")
            empty.setStyleSheet("color: #71717a; font-style: italic; padding: 20px;")
            self.assessments_lay.insertWidget(0, empty)

        g_gpa_text = f"{genel_points/genel_credits:.2f}" if genel_credits > 0 else "-"
        d_gpa_text = f"{donem_points/donem_credits:.2f}" if donem_credits > 0 else "-"
        
        self.lbl_gpa.setText(f"Seçili Dönem Ort. (SPA): {d_gpa_text}  |  Genel Ort. (CGPA): {g_gpa_text}")
        self.lbl_letter.setText(f"Kredi (Dönem/Genel): {donem_credits:.1f} / {genel_credits:.1f}")
    def update_score(self, assessment_id: int, score: float):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE assessments SET score = ? WHERE id = ?", (score, assessment_id))
            conn.commit()
        self.load_assessments()
        bus.assessments_changed.emit()

    def delete_assessment(self, assessment_id: int):
        confirm = QMessageBox.question(self, "Onay", "Bu değerlendirmeyi silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))
                conn.commit()
            self.load_assessments()
            bus.assessments_changed.emit()

    def dialog_add_assessment(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, code, year, term FROM courses ORDER BY year DESC, term DESC")
            courses = cur.fetchall()

        if not courses: return

        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Değerlendirme / Sınav")
        dlg.resize(320, 240)
        lay = QVBoxLayout(dlg)

        c_box = QComboBox()
        for c in courses:
            c_box.addItem(f"[{c['term']}] {c['code']}", c["id"])

        title_in = QLineEdit()
        title_in.setPlaceholderText("Başlık (Örn: Ara Sınav, Proje-1)")

        weight_in = QDoubleSpinBox()
        weight_in.setRange(1, 100)
        weight_in.setValue(40.0)
        weight_in.setPrefix("Ağırlık: %")

        date_in = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        date_in.setDisplayFormat("dd.MM.yyyy HH:mm")

        lay.addWidget(QLabel("Ders:")); lay.addWidget(c_box)
        lay.addWidget(title_in); lay.addWidget(weight_in)
        lay.addWidget(QLabel("Tarih & Saat:")); lay.addWidget(date_in)

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")
        lay.addWidget(btn_save)

        def save():
            t = title_in.text().strip()
            if not t: return
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO assessments (course_id, title, weight, due_date)
                    VALUES (?, ?, ?, ?)
                """, (c_box.currentData(), t, weight_in.value(), date_in.dateTime().toString("yyyy-MM-dd HH:mm")))
                conn.commit()

            dlg.accept()
            self.load_assessments()
            bus.assessments_changed.emit()

        btn_save.clicked.connect(save)
        dlg.exec()

    def create_personal_plan_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(12)

        top_bar = QHBoxLayout()
        lbl_title = QLabel("Kişisel Çalışma ve Etkinlik Planı")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        
        btn_save = QPushButton("💾 Planı Kaydet")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        btn_save.clicked.connect(self.save_personal_plan)
        
        top_bar.addWidget(lbl_title)
        top_bar.addStretch()
        top_bar.addWidget(btn_save)
        lay.addLayout(top_bar)

        # STANDART QTableWidget YERİNE ÖZEL SINIFIMIZI KULLANIYORUZ
        self.plan_table = PersonalPlanTableWidget(24, 7)
        self.plan_table.setItemDelegate(PersonalPlanDelegate(self.plan_table))
        self.plan_table.setHorizontalHeaderLabels(DAYS_TR)
        self.personal_plan_loading = False
        
        hours = [f"{h:02d}:00" for h in range(24)]
        self.plan_table.setVerticalHeaderLabels(hours)
        
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.plan_table.horizontalHeader().setStretchLastSection(True)
        self.plan_table.horizontalHeader().setDefaultSectionSize(120)
        
        self.plan_table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.plan_table.verticalHeader().setDefaultSectionSize(55)
        
        self.plan_table.setSelectionMode(QTableWidget.SingleSelection)
        self.plan_table.setSelectionBehavior(QTableWidget.SelectItems)
        
        # SAĞ TIK MENÜSÜ BAĞLANTISI
        self.plan_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plan_table.customContextMenuRequested.connect(self.show_plan_context_menu)
        
        self.plan_table.setStyleSheet("""
            QTableWidget { background-color: #141210; color: #f4f4f5; gridline-color: #292524; border: 1px solid #292524; border-radius: 8px; }
            QHeaderView::section { background-color: #1c1917; color: #a1a1aa; padding: 4px; border: 1px solid #292524; font-weight: bold; }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background-color: #1f1b18; border: 1px solid #38bdf8; }
        """)
        lay.addWidget(self.plan_table)
        
        self.load_personal_plan()
        return tab
    
    def show_plan_context_menu(self, pos):
            item = self.plan_table.itemAt(pos)
            if not item: return
    
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu { background-color: #1c1917; border: 1px solid #292524; color: #ffffff; padding: 4px; border-radius: 6px; }
                QMenu::item { padding: 6px 16px; border-radius: 4px; }
                QMenu::item:selected { background-color: #0284c7; color: white; }
            """)
    
            action_clear = menu.addAction("🧹 İçeriği Temizle")
            action_copy = menu.addAction("📋 Kopyala")
            action_paste = menu.addAction("📥 Yapıştır")
    
            action = menu.exec(self.plan_table.viewport().mapToGlobal(pos))
            if action == action_clear:
                item.setText("")
            elif action == action_copy:
                QApplication.clipboard().setText(item.text())
            elif action == action_paste:
                item.setText(QApplication.clipboard().text())
    def load_personal_plan(self):
        for r in range(24):
            for c in range(7):
                empty_item = QTableWidgetItem("")
                self.plan_table.setItem(r, c, empty_item)

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS personal_plan (
                    day_col INTEGER,
                    hour_row INTEGER,
                    content TEXT,
                    UNIQUE(day_col, hour_row)
                )
            """)
            cur.execute("SELECT day_col, hour_row, content FROM personal_plan")
            for row in cur.fetchall():
                item = QTableWidgetItem(row["content"])
                self.plan_table.setItem(row["hour_row"], row["day_col"], item)

    def save_personal_plan(self, notify=True):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM personal_plan")
            
            for r in range(24):
                for c in range(7):
                    item = self.plan_table.item(r, c)
                    if item and item.text().strip():
                        cur.execute("INSERT INTO personal_plan (day_col, hour_row, content) VALUES (?, ?, ?)", 
                                    (c, r, item.text().strip()))
            conn.commit()

        try: play_action_sound("save")
        except: pass
        if notify: bus.item_saved.emit("Kişisel plan başarıyla güncellendi.")