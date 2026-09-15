from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QDialog, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QMessageBox, QHeaderView, QTabWidget,
    QFrame, QScrollArea, QAbstractItemView, QMenu, QStyledItemDelegate, QStyle,
    QDateEdit, QGridLayout, QDateTimeEdit, QCalendarWidget
)
from PySide6.QtGui import QCursor, QColor, QDrag, QBrush
from PySide6.QtCore import Qt, Signal, QMimeData, QByteArray, QDataStream, QIODevice, QTimer, QDate, QDateTime, QLocale
from PySide6.QtGui import QCursor, QColor, QDrag
from core.sound import play_action_sound
from core.events import bus

DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


class TimetableColorDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        background = index.data(Qt.BackgroundRole)
        is_selected = bool(option.state & QStyle.State_Selected)
        if not isinstance(background, QBrush):
            super().paint(painter, option, index)
            return

        painter.save()
        cell_rect = option.rect.adjusted(4, 4, -4, -4)
        painter.fillRect(cell_rect, background)

        foreground = index.data(Qt.ForegroundRole)
        painter.setPen(foreground.color() if isinstance(foreground, QBrush) else QColor("#ffffff"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(
            cell_rect.adjusted(3, 3, -3, -3),
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


# =========================================================================
# 1. SÜRÜKLE - BIRAK VE SAĞ TIK DESTEKLİ TABLO BİLEŞENİ
# =========================================================================
class InteractiveTimetableWidget(QTableWidget):
    slot_moved = Signal(int, int)      # timetable_id, new_day_of_week
    slot_edit = Signal(dict)           # slot_data
    course_details_requested = Signal(dict)  # slot_data
    course_delete = Signal(int)        # course_id
    slot_delete = Signal(int)          # timetable_id

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
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data or not data.get("slot_id"):
            return

        mime_data = QMimeData()
        b_array = QByteArray()
        stream = QDataStream(b_array, QIODevice.WriteOnly)
        stream.writeInt32(data["slot_id"])
        mime_data.setData("application/x-timetable-slot", b_array)

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # ÇÖZÜM: Qt'nin orijinal hücreyi otomatik silmesini engellemek için CopyAction kullanıyoruz.
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
                # ÇÖZÜM: Bırakma eylemini Kopyalama olarak kabul edip, 
                # hücrenin Qt tarafından yok edilmesinin önüne geçiyoruz.
                event.setDropAction(Qt.CopyAction)
                event.accept()
                
                self.slot_moved.emit(slot_id, target_col)
            else:
                event.ignore()
        else:
            event.ignore()

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data or not data.get("slot_id"):
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1c1917;
                border: 1px solid #292524;
                color: #ffffff;
                padding: 4px;
                border-radius: 6px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: white;
            }
        """)

        action_details = menu.addAction("🔎 Ders Detaylarını Göster")
        action_edit = menu.addAction("✏️ Dersi / Saati Düzenle")
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

# =========================================================================
# 2. DEĞERLENDİRME & NOT KARTI BİLEŞENİ
# =========================================================================
class AssessmentCard(QFrame):
    score_updated = Signal(int, float)
    deleted = Signal(int)

    def __init__(self, data: dict):
        super().__init__()
        self.data = data
        self.setObjectName("Card")
        self.setStyleSheet("""
            QFrame#Card {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 10px;
                padding: 12px;
            }
            QFrame#Card:hover {
                border-color: #3f3f46;
            }
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
        lbl_weight.setStyleSheet("""
            background-color: #27272a;
            color: #38bdf8;
            font-weight: 700;
            font-size: 12px;
            padding: 5px 10px;
            border-radius: 6px;
        """)
        lay.addWidget(lbl_weight)

        score = self.data.get("score")
        if score is not None:
            # Harf notu aralıkları
            if score >= 90: letter = "AA"
            elif score >= 85: letter = "BA"
            elif score >= 80: letter = "BB"
            elif score >= 75: letter = "CB"
            elif score >= 65: letter = "CC"
            elif score >= 58: letter = "DC"
            elif score >= 50: letter = "DD"
            else: letter = "FF"
            
            # YÖK dönüşüm formülü: (Not * 3 - 20) / 70
            point_4 = (score * 3 - 20) / 70 if score >= 30 else 0.0
            point_4 = max(0.0, min(4.0, point_4)) # Sınırlandırma
            
            score_text = f"Not: {score:.1f} ({letter}) | {point_4:.2f}"
            score_color = "#10b981" if score >= 60 else "#ef4444"
        else:
            score_text = "Girilmedi"
            score_color = "#71717a"

        lbl_score = QLabel(score_text)
        lbl_score.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 800;
            color: {score_color};
            min-width: 75px;
        """)
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


# =========================================================================
# 3. ANA DERSLER VE NOTLAR GÖRÜNÜMÜ
# =========================================================================
class TimetableView(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        tabs = QTabWidget()
        tabs.addTab(self.create_schedule_tab(), "📅 Haftalık Ders Çizelgesi")
        tabs.addTab(self.create_grades_tab(), "🎯 Sınavlar ve Akademik Not Takibi")
        tabs.addTab(self.create_personal_plan_tab(), "📝 Kişisel Plan") # Yeni eklenen sekme
        layout.addWidget(tabs)

    def create_schedule_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(12)

        # Üst Araç Çubuğu
        top_bar = QHBoxLayout()
        btn_add_course = QPushButton("🎓  Yeni Ders Tanımla")
        btn_add_course.setObjectName("PrimaryCourseButton")
        btn_add_course.setMinimumHeight(42)
        btn_add_course.setMinimumWidth(190)
        btn_add_course.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_course.setStyleSheet("""
            QPushButton#PrimaryCourseButton {
                background-color: #38bdf8;
                color: #082f49;
                border: 1px solid #7dd3fc;
                border-radius: 9px;
                padding: 9px 18px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton#PrimaryCourseButton:hover {
                background-color: #7dd3fc;
                border-color: #bae6fd;
            }
            QPushButton#PrimaryCourseButton:pressed {
                background-color: #0ea5e9;
                padding-top: 11px;
                padding-bottom: 7px;
            }
        """)
        btn_add_course.clicked.connect(self.dialog_add_course)

        btn_add_slot = QPushButton("🕒  Çizelgeye Ders Saati Ekle")
        btn_add_slot.setObjectName("SecondaryScheduleButton")
        btn_add_slot.setMinimumHeight(42)
        btn_add_slot.setMinimumWidth(220)
        btn_add_slot.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_slot.setStyleSheet("""
            QPushButton#SecondaryScheduleButton {
                background-color: #14532d;
                color: #dcfce7;
                border: 1px solid #22c55e;
                border-radius: 9px;
                padding: 9px 16px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton#SecondaryScheduleButton:hover {
                background-color: #166534;
                border-color: #4ade80;
                color: #f0fdf4;
            }
            QPushButton#SecondaryScheduleButton:pressed {
                background-color: #15803d;
                padding-top: 11px;
                padding-bottom: 7px;
            }
        """)
        btn_add_slot.clicked.connect(self.dialog_add_schedule)

        info_lbl = QLabel("💡 İpucu: Dersi başka bir güne sürükleyip bırakabilir veya sağ tıklayarak güncelleyebilirsiniz.")
        info_lbl.setStyleSheet("color: #71717a; font-size: 11px;")

        self.semester_start_edit = QDateEdit()
        self.semester_start_edit.setCalendarPopup(True)
        self.semester_start_edit.setDisplayFormat("dd.MM.yyyy")
        self.semester_start_edit.setMinimumWidth(135)
        self.configure_date_edit(self.semester_start_edit)
        self.semester_start_edit.setStyleSheet("""
            QDateEdit { background: #18151f; color: #f5f3ff; border: 1px solid #8b5cf6; border-radius: 8px; padding: 7px 8px; font-weight: 700; }
            QDateEdit:focus { border: 2px solid #c4b5fd; }
            QDateEdit::down-button { width: 30px; background: #6d28d9; border-left: 1px solid #8b5cf6; border-top-right-radius: 7px; border-bottom-right-radius: 7px; }
            QDateEdit::down-button:hover { background: #7c3aed; }
        """)
        self.semester_start_edit.dateChanged.connect(self.save_semester_start_date)

        self.semester_end_edit = QDateEdit()
        self.semester_end_edit.setCalendarPopup(True)
        self.semester_end_edit.setDisplayFormat("dd.MM.yyyy")
        self.semester_end_edit.setMinimumWidth(135)
        self.configure_date_edit(self.semester_end_edit)
        self.semester_end_edit.setStyleSheet("""
            QDateEdit { background: #18151f; color: #f5f3ff; border: 1px solid #8b5cf6; border-radius: 8px; padding: 7px 8px; font-weight: 700; }
            QDateEdit:focus { border: 2px solid #c4b5fd; }
            QDateEdit::down-button { width: 30px; background: #6d28d9; border-left: 1px solid #8b5cf6; border-top-right-radius: 7px; border-bottom-right-radius: 7px; }
            QDateEdit::down-button:hover { background: #7c3aed; }
        """)
        self.semester_end_edit.dateChanged.connect(self.save_semester_end_date)

        self.semester_warning = QLabel()
        self.semester_warning.setWordWrap(True)
        self.semester_warning.setStyleSheet("color: #fca5a5; font-size: 11px; font-weight: 600; padding: 6px 10px; background-color: rgba(127, 29, 29, 0.35); border: 1px solid rgba(248, 113, 113, 0.35); border-radius: 6px;")
        self.semester_warning.setVisible(False)

        top_bar.addWidget(btn_add_course)
        top_bar.addWidget(btn_add_slot)
        top_bar.addSpacing(10)
        top_bar.addWidget(info_lbl)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("Dönem Başlangıcı:"))
        top_bar.addWidget(self.semester_start_edit)
        top_bar.addWidget(QLabel("Dönem Bitişi:"))
        top_bar.addWidget(self.semester_end_edit)
        lay.addLayout(top_bar)
        lay.addWidget(self.semester_warning)

        # Sürükle-Bırak Destekli Haftalık Grid
        self.table = InteractiveTimetableWidget()
        self.table.setItemDelegate(TimetableColorDelegate(self.table))
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(DAYS_TR)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #1c1917;
                color: #e4e4e7;
                border: 1px solid #292524;
                padding: 8px;
                font-weight: 700;
            }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(Qt.StrongFocus)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0f0d0c;
                border: 1px solid #2b2927;
                border-radius: 12px;
                gridline-color: rgba(255,255,255,0.06);
                color: #f4f4f5;
            }
            QTableWidget::item {
                padding: 6px;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.04);
            }
            QTableWidget::item:selected {
                background-color: rgba(56, 189, 248, 0.15);
                border: 1px solid #38bdf8;
            }
        """)

        # Sinyalleri bağla
        self.table.slot_moved.connect(self.handle_slot_moved)
        self.table.slot_edit.connect(self.dialog_edit_slot)
        self.table.course_details_requested.connect(self.show_course_details)
        self.table.course_delete.connect(self.delete_course)
        self.table.slot_delete.connect(self.delete_slot)

        lay.addWidget(self.table)
        self._ensure_default_semester_dates()
        self.load_schedule()
        return tab

    def _ensure_default_semester_dates(self):
        current_year = QDate.currentDate().year()
        default_start = QDate(current_year, 9, 15).toString("yyyy-MM-dd")
        default_end = QDate(current_year + 1, 1, 31).toString("yyyy-MM-dd")

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES ('semester_start_date', ?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
                WHERE app_settings.setting_value IS NULL OR app_settings.setting_value = ''
            """, (default_start,))
            cur.execute("""
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES ('semester_end_date', ?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
                WHERE app_settings.setting_value IS NULL OR app_settings.setting_value = ''
            """, (default_end,))
            conn.commit()

    def configure_date_edit(self, date_edit):
        turkish_locale = QLocale(QLocale.Turkish, QLocale.Turkey)
        date_edit.setLocale(turkish_locale)
        calendar = date_edit.calendarWidget()
        calendar.setLocale(turkish_locale)
        calendar.setFirstDayOfWeek(Qt.Monday)
        calendar.setGridVisible(True)
        calendar.setStyleSheet("""
            QCalendarWidget { background: #18181b; color: #f4f4f5; }
            QCalendarWidget QToolButton { color: #f4f4f5; background: #27272a; border: none; padding: 6px; font-weight: 700; }
            QCalendarWidget QToolButton:hover { background: #3f3f46; }
            QCalendarWidget QSpinBox { color: #f4f4f5; background: #27272a; }
            QCalendarWidget QAbstractItemView { selection-background-color: #0ea5e9; selection-color: white; }
        """)

    def _get_semester_start_date(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'semester_start_date'")
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return QDate.fromString(str(row[0]), "yyyy-MM-dd")

    def _get_semester_end_date(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'semester_end_date'")
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return QDate.fromString(str(row[0]), "yyyy-MM-dd")

    def save_semester_start_date(self, date_value):
        if not date_value or not date_value.isValid():
            return

        value = date_value.toString("yyyy-MM-dd")
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES ('semester_start_date', ?) "
                "ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
                (value,)
            )
            conn.commit()
        self.refresh_semester_warning()
        bus.courses_changed.emit()

    def save_semester_end_date(self, date_value):
        if not date_value or not date_value.isValid():
            return

        value = date_value.toString("yyyy-MM-dd")
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES ('semester_end_date', ?) "
                "ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
                (value,)
            )
            conn.commit()
        self.refresh_semester_warning()
        bus.courses_changed.emit()

    def refresh_semester_warning(self):
        semester_start_date = self._get_semester_start_date()
        semester_end_date = self._get_semester_end_date()
        if semester_start_date and semester_start_date.isValid():
            self.semester_start_edit.setDate(semester_start_date)
        else:
            self.semester_start_edit.clear()

        if not semester_end_date or not semester_end_date.isValid():
            self.semester_warning.setVisible(False)
            self.semester_end_edit.clear()
            return

        self.semester_end_edit.setDate(semester_end_date)
        today = QDate.currentDate()

        if semester_start_date and semester_start_date.isValid() and today < semester_start_date:
            days_until_start = semester_start_date.daysTo(today) * -1
            text = f"📌 Bugün: {today.toString('dd.MM.yyyy')} | Dönem başlangıcı: {semester_start_date.toString('dd.MM.yyyy')} ({days_until_start} gün kaldı)"
            fg = "#86efac"
            bg = "rgba(20, 83, 45, 0.35)"
            border = "rgba(34, 197, 94, 0.35)"
        elif today > semester_end_date:
            text = f"⚠️ Bugün: {today.toString('dd.MM.yyyy')} | Ders dönemi sona erdi. Programdaki derslerin tamamlanmış olduğunu kontrol edin."
            fg = "#fca5a5"
            bg = "rgba(127, 29, 29, 0.35)"
            border = "rgba(248, 113, 113, 0.35)"
        elif today == semester_end_date:
            text = f"📌 Bugün: {today.toString('dd.MM.yyyy')} | Ders dönemi son günü. Programı kontrol edebilirsiniz."
            fg = "#fcd34d"
            bg = "rgba(120, 53, 15, 0.35)"
            border = "rgba(251, 191, 36, 0.35)"
        else:
            days_left = semester_end_date.daysTo(today) * -1
            text = f"📌 Bugün: {today.toString('dd.MM.yyyy')} | Dönem sonu: {semester_end_date.toString('dd.MM.yyyy')} ({days_left} gün kaldı)"
            if days_left <= 30:
                fg = "#fcd34d"
                bg = "rgba(120, 53, 15, 0.35)"
                border = "rgba(251, 191, 36, 0.35)"
            else:
                fg = "#86efac"
                bg = "rgba(20, 83, 45, 0.35)"
                border = "rgba(34, 197, 94, 0.35)"

        self.semester_warning.setText(text)
        self.semester_warning.setStyleSheet(
            f"color: {fg}; font-size: 11px; font-weight: 600; "
            f"padding: 6px 10px; background-color: {bg}; "
            f"border: 1px solid {border}; border-radius: 6px;"
        )
        self.semester_warning.setVisible(True)

    def load_schedule(self):
        self.refresh_semester_warning()
        self.table.setRowCount(8)
        for r in range(8):
            self.table.setRowHeight(r, 92)
            for c in range(7):
                item = QTableWidgetItem("")
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(r, c, item)

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                  SELECT t.id, t.day_of_week, t.start_time, t.end_time,
                      c.code, c.name,
                      t.instructor, t.instructor_contact, t.classroom,
                      c.color_hex, t.course_id
                FROM timetable t
                JOIN courses c ON t.course_id = c.id
                ORDER BY t.start_time ASC
            """)
            slots = cur.fetchall()

        day_counters = {d: 0 for d in range(7)}
        for s in slots:
            dow = s["day_of_week"]
            row_idx = day_counters[dow]
            if row_idx < 8:
                c_color = s["color_hex"] if s["color_hex"] else "#38bdf8"
                text = f"{s['code']}\n{s['start_time']} - {s['end_time']}\n({s['classroom'] or 'Amfi belirtilmedi'})\n{s['instructor'] or 'Öğretim görevlisi belirtilmedi'}"
                
                # Ders rengini takvimdeki rozetler gibi hücre arka planına uygula.
                bg_color = QColor(c_color)
                if not bg_color.isValid():
                    bg_color = QColor("#38bdf8")
                bg_color.setAlpha(230)
                
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
                item.setForeground(QColor("#ffffff"))
                item.setToolTip(f"{s['name']}\n{DAYS_TR[s['day_of_week']]} • {s['start_time']} - {s['end_time']}\n{(s['classroom'] or 'Amfi belirtilmedi')}\n{(s['instructor'] or 'Öğretim görevlisi belirtilmedi')}\n{(s['instructor_contact'] or 'İletişim bilgisi yok')}")
                
                item.setBackground(QBrush(bg_color))
                
                # Sürükleme ve sağ tık için slot verisini sakla
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
                    "instructor_contact": s["instructor_contact"] or ""
                })
                
                self.table.setItem(row_idx, dow, item)
                day_counters[dow] += 1

    def refresh_slot_cell(self, slot_id: int):
        with self.db.get_connection() as conn:
            slot = conn.execute("""
                SELECT t.id, t.day_of_week, t.start_time, t.end_time,
                       c.code, c.name,
                       t.instructor, t.instructor_contact, t.classroom,
                       c.color_hex, t.course_id
                FROM timetable t
                JOIN courses c ON t.course_id = c.id
                WHERE t.id = ?
            """, (slot_id,)).fetchone()

        if not slot:
            self.load_schedule()
            return

        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                data = item.data(Qt.UserRole) if item else None
                if data and data.get("slot_id") == slot_id:
                    if (
                        data.get("day_of_week") != slot["day_of_week"]
                        or data.get("start_time") != slot["start_time"]
                    ):
                        self.load_schedule()
                        return

                    item.setText(
                        f"{slot['code']}\n{slot['start_time']} - {slot['end_time']}\n"
                        f"({slot['classroom'] or 'Amfi belirtilmedi'})\n"
                        f"{slot['instructor'] or 'Öğretim görevlisi belirtilmedi'}"
                    )
                    item.setToolTip(
                        f"{slot['name']}\n{DAYS_TR[slot['day_of_week']]} • "
                        f"{slot['start_time']} - {slot['end_time']}\n"
                        f"{slot['classroom'] or 'Amfi belirtilmedi'}\n"
                        f"{slot['instructor'] or 'Öğretim görevlisi belirtilmedi'}\n"
                        f"{slot['instructor_contact'] or 'İletişim bilgisi yok'}"
                    )
                    item.setData(Qt.UserRole, {
                        "slot_id": slot["id"],
                        "course_id": slot["course_id"],
                        "code": slot["code"],
                        "name": slot["name"],
                        "day_of_week": slot["day_of_week"],
                        "start_time": slot["start_time"],
                        "end_time": slot["end_time"],
                        "classroom": slot["classroom"] or "",
                        "instructor": slot["instructor"] or "",
                        "instructor_contact": slot["instructor_contact"] or ""
                    })
                    self.table.viewport().update()
                    return

        self.load_schedule()

    def handle_slot_moved(self, slot_id: int, new_day_of_week: int):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE timetable SET day_of_week = ? WHERE id = ?", (new_day_of_week, slot_id))
            conn.commit()
            play_action_sound("save")
        self.load_schedule()
        bus.courses_changed.emit()
        bus.item_saved.emit("Ders programı güncellendi.")

    def dialog_edit_slot(self, slot_data: dict):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Dersi Düzenle — {slot_data['code']}")
        dlg.resize(320, 260)
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

        lay.addWidget(QLabel("Gün:"))
        lay.addWidget(day_box)
        lay.addWidget(QLabel("Başlangıç Saati:"))
        lay.addWidget(start_in)
        lay.addWidget(QLabel("Bitiş Saati:"))
        lay.addWidget(end_in)
        lay.addWidget(QLabel("Derslik / Amfi:"))
        lay.addWidget(room_in)
        lay.addWidget(QLabel("Öğretim Görevlisi:"))
        lay.addWidget(instructor_in)
        lay.addWidget(QLabel("Hoca İletişim Bilgileri:"))
        lay.addWidget(instructor_contact_in)

        btn_save = QPushButton("Güncelle")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        lay.addWidget(btn_save)

        def save():
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE timetable 
                    SET day_of_week = ?, start_time = ?, end_time = ?,
                        classroom = ?, instructor = ?, instructor_contact = ?
                    WHERE id = ?
                """, (day_box.currentData(), start_in.text().strip(), end_in.text().strip(),
                      room_in.text().strip(), instructor_in.text().strip(), instructor_contact_in.text().strip(), slot_data["slot_id"]))
                conn.commit()
            play_action_sound("save")
            dlg.accept()
            self.refresh_slot_cell(slot_data["slot_id"])

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
            bus.item_deleted.emit("Çizelgeden bir ders saati kaldırıldı.")

    def delete_course(self, course_id: int):
        with self.db.get_connection() as conn:
            course = conn.execute(
                "SELECT code, name FROM courses WHERE id = ?", (course_id,)
            ).fetchone()

        if not course:
            return

        confirm = QMessageBox.question(
            self,
            "Dersi Tamamen Sil",
            f"'{course['code']} - {course['name']}' dersini tamamen silmek istiyor musunuz?\n\n"
            "Dersin çizelge ve sınav kayıtları silinir. Bağlı materyaller korunarak genele aktarılır.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE materials SET course_id = NULL WHERE course_id = ?",
                (course_id,)
            )
            conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
            conn.commit()

        self.load_schedule()
        bus.courses_changed.emit()
        bus.assessments_changed.emit()
        bus.notes_changed.emit()
        bus.item_deleted.emit(f"'{course['code']}' dersi tamamen silindi.")

    def show_course_details(self, slot_data: dict):
        with self.db.get_connection() as conn:
            course = conn.execute("""
                SELECT code, name, instructor, instructor_contact, classroom, credit
                FROM courses WHERE id = ?
            """, (slot_data["course_id"],)).fetchone()
            slot = conn.execute("""
                SELECT id, start_time, end_time, instructor, instructor_contact, classroom
                FROM timetable WHERE id = ?
            """, (slot_data.get("slot_id"),)).fetchone()

        if not course:
            return

        slot_instructor = (slot["instructor"] if slot else None) or "Belirtilmemiş"
        slot_contact = (slot["instructor_contact"] if slot else None) or "Belirtilmemiş"
        slot_classroom = (slot["classroom"] if slot else None) or "Belirtilmemiş"

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Ders Detayları - {course['code']}")
        dlg.resize(420, 360)
        dlg.setStyleSheet("QDialog { background-color: #141210; color: #f4f4f5; }")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #1c1917; border: 1px solid #292524; border-radius: 12px; }")
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(14, 12, 14, 12)

        code_label = QLabel(f"{course['code']}")
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
        btn_delete = QPushButton("Dersi Tamamen Sil")
        btn_delete.setStyleSheet("background-color: #1f1b18; color: #fca5a5; border: 1px solid #f43f5e; border-radius: 6px; padding: 7px 10px; font-weight: 600;")
        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet("background-color: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 6px; padding: 7px 10px; font-weight: 600;")
        buttons.addWidget(btn_edit)
        buttons.addWidget(btn_delete)
        buttons.addWidget(btn_close)
        lay.addLayout(buttons)

        btn_close.clicked.connect(dlg.reject)

        def edit_course():
            dlg.accept()
            self.dialog_edit_slot(slot_data)

        def delete_course():
            dlg.reject()
            self.delete_course(slot_data["course_id"])

        btn_edit.clicked.connect(edit_course)
        btn_delete.clicked.connect(delete_course)
        dlg.exec()

    def dialog_edit_course(self, course_id: int):
        with self.db.get_connection() as conn:
            course = conn.execute("""
                SELECT code, name, instructor, instructor_contact, classroom, credit
                FROM courses WHERE id = ?
            """, (course_id,)).fetchone()

        if not course:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Dersi Güncelle - {course['code']}")
        dlg.resize(360, 360)
        lay = QVBoxLayout(dlg)

        code_in = QLineEdit(course["code"])
        code_in.setReadOnly(True)
        code_in.setStyleSheet("background-color: #1c1917; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 6px; padding: 6px;")
        name_in = QLineEdit(course["name"])
        instructor_in = QLineEdit(course["instructor"] or "")
        contact_in = QLineEdit(course["instructor_contact"] or "")
        classroom_in = QLineEdit(course["classroom"] or "")
        credit_in = QSpinBox()
        credit_in.setRange(1, 10)
        credit_in.setValue(int(course["credit"] or 3))

        for label, widget in (
            ("Ders kodu (değiştirilemez):", code_in),
            ("Ders adı:", name_in),
            ("Öğretim görevlisi:", instructor_in),
            ("Hocanın iletişim bilgileri:", contact_in),
            ("Derslik / Amfi:", classroom_in),
        ):
            lay.addWidget(QLabel(label))
            lay.addWidget(widget)
        lay.addWidget(QLabel("Kredi:"))
        lay.addWidget(credit_in)

        btn_save = QPushButton("Güncelle")
        btn_save.setObjectName("AccentButton")
        lay.addWidget(btn_save)

        def save():
            code = code_in.text().strip()
            name = name_in.text().strip()
            if not code or not name:
                QMessageBox.warning(dlg, "Hata", "Ders kodu ve adı boş bırakılamaz.")
                return
            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE courses
                        SET name = ?, instructor = ?, instructor_contact = ?,
                            classroom = ?, credit = ?
                        WHERE id = ?
                    """, (
                        name, instructor_in.text().strip(), contact_in.text().strip(),
                        classroom_in.text().strip(), credit_in.value(), course_id
                    ))
                    conn.commit()
                dlg.accept()
                self.load_schedule()
                bus.courses_changed.emit()
                bus.item_saved.emit(f"'{code}' ders bilgileri güncellendi.")
            except Exception as exc:
                QMessageBox.critical(dlg, "Hata", f"Ders güncellenemedi: {exc}")

        btn_save.clicked.connect(save)
        dlg.exec()

    def dialog_add_course(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Ders Tanımla")
        dlg.resize(320, 280)
        lay = QVBoxLayout(dlg)

        code_in = QLineEdit(); code_in.setPlaceholderText("Ders Kodu (Örn: MATH101)")
        name_in = QLineEdit(); name_in.setPlaceholderText("Ders Adı (Örn: Calculus I)")
        inst_in = QLineEdit(); inst_in.setPlaceholderText("Öğretim Üyesi")
        contact_in = QLineEdit(); contact_in.setPlaceholderText("Hocanın iletişim bilgileri")
        room_in = QLineEdit(); room_in.setPlaceholderText("Derslik / Amfi")
        cred_in = QSpinBox(); cred_in.setValue(3); cred_in.setPrefix("Kredi: ")

        cred_in = QSpinBox(); cred_in.setValue(3); cred_in.setPrefix("Kredi: ")

        # --- YENİ RENK SEÇİM KUTUSU ---
        color_box = QComboBox()
        color_box.setStyleSheet("background-color: #27272a; padding: 6px; border-radius: 4px; color: white;")
        
        # Okunabilir renk isimleri ve hex kodları
        colors = [
            ("Mavi", "#38bdf8"),
            ("Zümrüt Yeşili", "#10b981"),
            ("Mor", "#a855f7"),
            ("Turuncu", "#f59e0b"),
            ("Kırmızı", "#f43f5e"),
            ("Sarı", "#eab308"),
            ("Pembe", "#ec4899"),
            ("Okyanus", "#0ea5e9")
        ]
        
        for name, hex_code in colors:
            color_box.addItem(name, hex_code)
            idx = color_box.count() - 1
            # Qt.DecorationRole sayesinde ismin yanına otomatik renk kutucuğu (ikon) eklenir
            color_box.setItemData(idx, QColor(hex_code), Qt.DecorationRole)
        # ------------------------------

        lay.addWidget(code_in)

        lay.addWidget(code_in)
        lay.addWidget(name_in)
        lay.addWidget(inst_in)
        lay.addWidget(contact_in)
        lay.addWidget(room_in)
        lay.addWidget(cred_in)
        lay.addWidget(QLabel("Renk Rozeti:"))
        lay.addWidget(color_box)

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        lay.addWidget(btn_save)

        def save():
            if not code_in.text().strip() or not name_in.text().strip():
                QMessageBox.warning(dlg, "Hata", "Ders kodu ve adı boş bırakılamaz.")
                return
            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                                                INSERT INTO courses (code, name, instructor, instructor_contact, classroom, credit, color_hex)
                                                VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (code_in.text().strip(), name_in.text().strip(), inst_in.text().strip(),
                                                    contact_in.text().strip(), room_in.text().strip(), cred_in.value(), color_box.currentData()))
                    conn.commit()
                dlg.accept()
                self.load_schedule()
                bus.courses_changed.emit()
                bus.item_saved.emit(f"'{code_in.text().strip()}' dersi başarıyla tanımlandı.")   
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", f"Ders kaydedilemedi: {e}")

        btn_save.clicked.connect(save)
        dlg.exec()

    def dialog_add_schedule(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, code, name, instructor, instructor_contact, classroom FROM courses")
            courses = cur.fetchall()

        if not courses:
            QMessageBox.information(self, "Bilgi", "Önce bir ders tanımlamalısınız.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Çizelgeye Ders Saati Ekle")
        dlg.resize(320, 320)
        lay = QVBoxLayout(dlg)

        c_box = QComboBox()
        for c in courses:
            c_box.addItem(f"{c['code']} - {c['name']}", c['id'])

        day_box = QComboBox()
        for i, d in enumerate(DAYS_TR):
            day_box.addItem(d, i)

        start_in = QLineEdit("09:30")
        end_in = QLineEdit("11:20")
        instructor_in = QLineEdit()
        instructor_contact_in = QLineEdit()
        room_in = QLineEdit()

        def load_course_defaults(index):
            course = courses[index]
            instructor_in.setText(course["instructor"] or "")
            instructor_contact_in.setText(course["instructor_contact"] or "")
            room_in.setText(course["classroom"] or "")

        c_box.currentIndexChanged.connect(load_course_defaults)
        load_course_defaults(0)

        lay.addWidget(QLabel("Ders:"))
        lay.addWidget(c_box)
        lay.addWidget(QLabel("Gün:"))
        lay.addWidget(day_box)
        lay.addWidget(QLabel("Saat Aralığı:"))
        lay.addWidget(start_in)
        lay.addWidget(end_in)
        lay.addWidget(QLabel("Derslik / Amfi:"))
        lay.addWidget(room_in)
        lay.addWidget(QLabel("Öğretim Görevlisi:"))
        lay.addWidget(instructor_in)
        lay.addWidget(QLabel("Hoca İletişim Bilgileri:"))
        lay.addWidget(instructor_contact_in)

        btn_save = QPushButton("Ekle")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        lay.addWidget(btn_save)

        def save():
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO timetable
                        (course_id, day_of_week, start_time, end_time, instructor, instructor_contact, classroom)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (c_box.currentData(), day_box.currentData(), start_in.text().strip(),
                      end_in.text().strip(), instructor_in.text().strip(), instructor_contact_in.text().strip(), room_in.text().strip()))
                conn.commit()
            play_action_sound("save")
            dlg.accept()
            self.load_schedule()
            bus.courses_changed.emit()
            bus.item_saved.emit("Çizelgeye yeni ders saati eklendi.")
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

        summary_card = QFrame()
        summary_card.setObjectName("Card")
        sum_lay = QHBoxLayout(summary_card)
        sum_lay.setContentsMargins(16, 12, 16, 12)

        self.lbl_gpa = QLabel("Ağırlıklı Not Ortalaması: -")
        self.lbl_gpa.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff;")

        self.lbl_letter = QLabel("Harf Notu: -")
        self.lbl_letter.setStyleSheet("font-size: 14px; font-weight: 700; color: #10b981; margin-left: 16px;")

        btn_add_assessment = QPushButton("📅  Yeni Sınav / Değerlendirme")
        btn_add_assessment.setObjectName("AssessmentAddButton")
        btn_add_assessment.setMinimumSize(225, 42)
        btn_add_assessment.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_assessment.setStyleSheet("""
            QPushButton#AssessmentAddButton {
                background-color: #9a3412;
                color: #fff7ed;
                border: 1px solid #fb923c;
                border-radius: 9px;
                padding: 9px 16px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton#AssessmentAddButton:hover {
                background-color: #c2410c;
                border-color: #fdba74;
            }
            QPushButton#AssessmentAddButton:pressed {
                background-color: #7c2d12;
                padding-top: 11px;
                padding-bottom: 7px;
            }
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

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.id, a.course_id, a.title, a.weight, a.score, a.due_date, c.code
                FROM assessments a
                JOIN courses c ON a.course_id = c.id
                ORDER BY a.due_date ASC
            """)
            rows = cur.fetchall()

        total_weight = 0.0
        total_points = 0.0

        for r in rows:
            data = dict(r)
            card = AssessmentCard(data)
            card.score_updated.connect(self.update_score)
            card.deleted.connect(self.delete_assessment)
            self.assessments_lay.insertWidget(self.assessments_lay.count() - 1, card)

            if data["score"] is not None:
                total_points += (data["score"] * (data["weight"] / 100.0))
                total_weight += data["weight"]

        if not rows:
            empty = QLabel("Henüz eklenmiş bir sınav veya ödev bulunmuyor.")
            empty.setStyleSheet("color: #71717a; font-style: italic; padding: 20px;")
            self.assessments_lay.insertWidget(0, empty)

        if total_weight > 0:
            avg = (total_points / total_weight) * 100.0
            letter = self.calculate_letter_grade(avg)
            
            # YÖK dönüşüm formülü (Genel GPA için)
            gpa_4 = (avg * 3 - 20) / 70 if avg >= 30 else 0.0
            gpa_4 = max(0.0, min(4.0, gpa_4))
            
            self.lbl_gpa.setText(f"Not Ortalaması: {avg:.2f}/100  |  GPA: {gpa_4:.2f}/4.00")
            self.lbl_letter.setText(f"Tahmini Harf: {letter}")
        else:
            self.lbl_gpa.setText("Ağırlıklı Not Ortalaması: -")
            self.lbl_letter.setText("Tahmini Harf: -")

    def calculate_letter_grade(self, score: float) -> str:
        if score >= 90: return "AA (4.00)"
        elif score >= 85: return "BA (3.50)"
        elif score >= 80: return "BB (3.00)"
        elif score >= 75: return "CB (2.50)"
        elif score >= 65: return "CC (2.00)"
        elif score >= 58: return "DC (1.50)"
        elif score >= 50: return "DD (1.00)"
        else: return "FF (0.00)"

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
            bus.item_deleted.emit("Bir sınav veya değerlendirme silindi.")

    def dialog_add_assessment(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, code FROM courses")
            courses = cur.fetchall()

        if not courses:
            QMessageBox.information(self, "Bilgi", "Önce en az bir ders tanımlamalısınız.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Değerlendirme / Sınav")
        dlg.resize(320, 240)
        lay = QVBoxLayout(dlg)

        c_box = QComboBox()
        for c in courses:
            c_box.addItem(c["code"], c["id"])

        title_in = QLineEdit()
        title_in.setPlaceholderText("Başlık (Örn: Ara Sınav, Proje-1)")

        weight_in = QDoubleSpinBox()
        weight_in.setRange(1, 100)
        weight_in.setValue(40.0)
        weight_in.setPrefix("Ağırlık: %")

        date_in = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        date_in.setCalendarPopup(True)
        date_in.setDisplayFormat("dd.MM.yyyy HH:mm")
        date_in.setMinimumWidth(180)
        self.configure_date_edit(date_in)

        lay.addWidget(QLabel("Ders:"))
        lay.addWidget(c_box)
        lay.addWidget(title_in)
        lay.addWidget(weight_in)
        lay.addWidget(QLabel("Tarih & Saat:"))
        lay.addWidget(date_in)

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        lay.addWidget(btn_save)

        def save():
            t = title_in.text().strip()
            if not t:
                return
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
            bus.item_saved.emit(f"Yeni sınav/değerlendirme eklendi: {t}")

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

        # Tablo satır sayısını tüm gün için 24 yapıyoruz
        self.plan_table = QTableWidget(24, 7)
        self.plan_table.setItemDelegate(PersonalPlanDelegate(self.plan_table))
        self.plan_table.setHorizontalHeaderLabels(DAYS_TR)
        self.personal_plan_loading = False
        self.personal_plan_save_timer = QTimer(self)
        self.personal_plan_save_timer.setSingleShot(True)
        self.personal_plan_save_timer.timeout.connect(
            lambda: self.save_personal_plan(notify=False)
        )
        
        # 00:00'dan 23:00'a kadar tüm saatler (gece 24 = 00:00)
        hours = [f"{h:02d}:00" for h in range(24)]
        self.plan_table.setVerticalHeaderLabels(hours)
        
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.plan_table.verticalHeader().setDefaultSectionSize(58)
        self.plan_table.setWordWrap(True)
        self.plan_table.setTextElideMode(Qt.ElideRight)
        self.plan_table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.EditKeyPressed |
            QAbstractItemView.SelectedClicked
        )
        self.plan_table.itemChanged.connect(self.refresh_personal_plan_cell)
        self.plan_table.itemChanged.connect(self.schedule_personal_plan_save)
        
        self.plan_table.setStyleSheet("""
            QTableWidget { background-color: #141210; color: #f4f4f5; gridline-color: #292524; border: 1px solid #292524; border-radius: 8px; }
            QHeaderView::section { background-color: #1c1917; color: #a1a1aa; padding: 4px; border: 1px solid #292524; font-weight: bold; }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background-color: #1f1b18; border: 1px solid #38bdf8; }
        """)
        lay.addWidget(self.plan_table)
        
        self.load_personal_plan()
        return tab

    def refresh_personal_plan_cell(self, item):
        if item.text().strip():
            item.setToolTip(item.text())
        else:
            item.setToolTip("")
            row = item.row()
            column = item.column()

            def clear_empty_cell():
                current_item = self.plan_table.item(row, column)
                if current_item is item and not current_item.text().strip():
                    self.plan_table.takeItem(row, column)
                    self.plan_table.clearSelection()
                    self.plan_table.setCurrentCell(-1, -1)
                    self.plan_table.viewport().repaint()

            QTimer.singleShot(0, clear_empty_cell)
        self.plan_table.viewport().repaint()

    def schedule_personal_plan_save(self, item):
        if not self.personal_plan_loading:
            self.personal_plan_save_timer.start(500)

    def load_personal_plan(self):
        self.personal_plan_loading = True
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            # Tablo yoksa otomatik oluşturur
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
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                item.setToolTip(row["content"])
                self.plan_table.setItem(row["hour_row"], row["day_col"], item)
            self.personal_plan_loading = False

    def save_personal_plan(self, notify=True):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM personal_plan")
            
            # Kaydetme döngüsünü de 24 satıra göre güncelliyoruz
            for r in range(24):
                for c in range(7):
                    item = self.plan_table.item(r, c)
                    if item and item.text().strip():
                        cur.execute("INSERT INTO personal_plan (day_col, hour_row, content) VALUES (?, ?, ?)", 
                                    (c, r, item.text().strip()))
            conn.commit()

        self.personal_plan_loading = True
        self.plan_table.clearContents()
        self.load_personal_plan()
        self.plan_table.clearSelection()
        self.plan_table.setCurrentCell(-1, -1)
        self.plan_table.viewport().repaint()
            
        try:
            play_action_sound("save")
        except Exception:
            pass
        if notify:
            bus.item_saved.emit("Kişisel plan başarıyla güncellendi.")