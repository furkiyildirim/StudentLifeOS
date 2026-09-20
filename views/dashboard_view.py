import requests
from datetime import datetime, date, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QCheckBox, QScrollArea, QPushButton,
    QProgressBar, QDialog, QLineEdit, QTextEdit, QMessageBox, QToolTip, QComboBox
)
from PySide6.QtCore import Qt, QRectF, QTimer, QThread, Signal
from PySide6.QtNetwork import QNetworkInformation
from PySide6.QtGui import QCursor, QPainter, QColor, QBrush, QPen, QFont
from core.events import bus
from core.sound import play_action_sound

DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
DAYS_SHORT_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

# --- GÜVENLİ HAVA DURUMU İŞ PARÇACĞI ---
class WeatherWorker(QThread):
    result_ready = Signal(str)

    WEATHER_CODES = {
        0: "Açık",
        1: "Çoğunlukla açık",
        2: "Parçalı bulutlu",
        3: "Kapalı",
        45: "Sisli",
        48: "Kırağılı sis",
        51: "Hafif çisenti",
        53: "Çisenti",
        55: "Yoğun çisenti",
        61: "Hafif yağmur",
        63: "Yağmurlu",
        65: "Kuvvetli yağmur",
        71: "Hafif kar",
        73: "Kar yağışlı",
        75: "Kuvvetli kar",
        80: "Sağanak yağış",
        81: "Kuvvetli sağanak",
        82: "Çok kuvvetli sağanak",
        95: "Gök gürültülü fırtına",
        96: "Dolu ihtimali olan fırtına",
        99: "Kuvvetli dolulu fırtına",
    }

    def __init__(self, db):
        super().__init__()
        self.db = db

    def run(self):
        try:
            from core.network import check_internet_connection
            if not check_internet_connection(timeout=5):
                self.result_ready.emit("🔌 Offline")
                return

            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'weather_enabled'")
                w_enabled = cur.fetchone()
                if w_enabled and w_enabled[0] == "0":
                    self.result_ready.emit("") 
                    return
                
                cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'weather_city'")
                m_loc = cur.fetchone()
                selected_city = m_loc[0].strip() if m_loc and m_loc[0] else "İstanbul"
                if selected_city in ("1", "Otomatik Konum"):
                    selected_city = "İstanbul"

            location_params = {
                "count": 1,
                "language": "tr",
                "format": "json",
            }
            location_params["name"] = selected_city
            location_response = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params=location_params,
                timeout=(5, 10),
            )
            location_response.raise_for_status()
            locations = location_response.json().get("results", [])
            if not locations:
                self.result_ready.emit("📍 Şehir bulunamadı")
                return
            location = locations[0]

            weather_response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "current": "temperature_2m,weather_code",
                    "timezone": "auto",
                },
                timeout=(5, 10),
            )
            weather_response.raise_for_status()
            current = weather_response.json()["current"]
            description = self.WEATHER_CODES.get(
                current["weather_code"], "Bilinmeyen hava durumu"
            )
            self.result_ready.emit(
                f"📍 {location['name']}: {current['temperature_2m']}°C, {description}"
            )
        except requests.RequestException:
            self.result_ready.emit("🔌 Offline / Bağlantı Hatası")
        except Exception:
            self.result_ready.emit("📍 Hava durumu alınamadı")

# =========================================================================
# 1. YEREL GRAFİK BİLEŞENLERİ (QPainter Tabanlı Donut ve Bar Chart)
# =========================================================================
class HabitWeeklyBarChart(QWidget):
    def __init__(self, data: list):
        super().__init__()
        self.data = data
        self.setFixedHeight(140)

    def set_data(self, data: list):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        bottom_margin = 25
        top_margin = 15
        chart_height = h - bottom_margin - top_margin

        num_bars = len(self.data)
        if num_bars == 0:
            return

        bar_width = max(18, int((w - (num_bars * 12)) / num_bars))
        gap = int((w - (bar_width * num_bars)) / (num_bars + 1))

        max_val = max([item[1] for item in self.data] + [1])

        for i, (day_lbl, count) in enumerate(self.data):
            x = gap + i * (bar_width + gap)
            bar_h = int((count / max_val) * (chart_height - 10)) if count > 0 else 4
            y = h - bottom_margin - bar_h

            color = QColor("#10b981") if count > 0 else QColor("#27272a")
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, y, bar_width, bar_h, 4, 4)

            if count > 0:
                painter.setPen(QPen(QColor("#f4f4f5")))
                painter.setFont(QFont("Inter", 9, QFont.Bold))
                painter.drawText(QRectF(x - 5, y - 16, bar_width + 10, 14), Qt.AlignCenter, str(count))

            painter.setPen(QPen(QColor("#a1a1aa")))
            painter.setFont(QFont("Inter", 9))
            painter.drawText(QRectF(x - 5, h - bottom_margin + 5, bar_width + 10, 16), Qt.AlignCenter, day_lbl)


class StudyTimeBarChart(QWidget):
    def __init__(self, data=None):
        super().__init__()
        self.data = data or []
        self.setFixedHeight(180)
        self.setMouseTracking(True)

    def set_data(self, data):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.data:
            return

        width = self.width()
        height = self.height()
        left = 12
        right = 12
        top = 18
        bottom = 34
        chart_height = height - top - bottom
        bar_gap = 10
        bar_width = max(18, int((width - left - right - bar_gap * (len(self.data) - 1)) / len(self.data)))
        max_seconds = max([seconds for _, seconds in self.data] + [3600])

        for index, (label, seconds) in enumerate(self.data):
            x = left + index * (bar_width + bar_gap)
            bar_height = max(4, int((seconds / max_seconds) * chart_height)) if seconds else 4
            y = height - bottom - bar_height
            color = QColor("#38bdf8") if seconds else QColor("#27272a")

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, y, bar_width, bar_height, 5, 5)

            if seconds:
                painter.setPen(QPen(QColor("#e4e4e7")))
                painter.setFont(QFont("Inter", 8, QFont.Bold))
                painter.drawText(QRectF(x - 8, y - 16, bar_width + 16, 14), Qt.AlignCenter, self.format_hours(seconds))

            painter.setPen(QPen(QColor("#a1a1aa")))
            painter.setFont(QFont("Inter", 9))
            painter.drawText(QRectF(x - 8, height - bottom + 8, bar_width + 16, 18), Qt.AlignCenter, label)

    @staticmethod
    def format_hours(seconds):
        minutes = round(seconds / 60)
        return f"{minutes / 60:.1f} sa" if minutes >= 60 else f"{minutes} dk"

    def mouseMoveEvent(self, event):
        if not self.data:
            return
        width = self.width()
        left = 12
        bar_gap = 10
        bar_width = max(18, int((width - 24 - bar_gap * (len(self.data) - 1)) / len(self.data)))
        index = int((event.position().x() - left) / (bar_width + bar_gap))
        if 0 <= index < len(self.data):
            label, seconds = self.data[index]
            QToolTip.showText(
                self.mapToGlobal(event.position().toPoint()),
                f"{label}: {self.format_hours(seconds)} çalışma",
                self,
            )
        else:
            QToolTip.hideText()

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)


class AssessmentDonutChart(QWidget):
    def __init__(self, segments: list):
        super().__init__()
        self.segments = segments
        self.setFixedHeight(140)

    def set_segments(self, segments: list):
        self.segments = segments
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = min(self.width() - 140, self.height() - 20)
        rect = QRectF(10, (self.height() - size) / 2, size, size)

        start_angle = 90 * 16
        total = sum([s[1] for s in self.segments])

        if total == 0:
            painter.setPen(QPen(QColor("#27272a"), 14))
            painter.drawArc(rect, 0, 360 * 16)
        else:
            for _, pct, color_hex in self.segments:
                span_angle = int((pct / total) * 360 * 16)
                pen = QPen(QColor(color_hex), 14)
                pen.setCapStyle(Qt.FlatCap)
                painter.setPen(pen)
                painter.drawArc(rect, start_angle, -span_angle)
                start_angle -= span_angle

        leg_x = rect.right() + 20
        leg_y = 15
        painter.setFont(QFont("Inter", 9))

        for title, pct, color_hex in self.segments[:4]:
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(leg_x, leg_y + 3, 10, 10, 2, 2)

            painter.setPen(QPen(QColor("#e4e4e7")))
            painter.drawText(leg_x + 16, leg_y + 12, f"{title} (%{int(pct)})")
            leg_y += 24


# =========================================================================
# 2. KPI ROZETİ VE DASHBOARD
# =========================================================================
class StatBadge(QFrame):
    def __init__(self, icon: str, accent_color: str):
        super().__init__()
        self.accent_color = accent_color
        self.setObjectName("Card")
        self.setStyleSheet(f"""
            QFrame#Card {{
                background-color: #171412;
                border: 1px solid #292524;
                border-radius: 10px;
                padding: 10px 14px;
            }}
            QFrame#Card:hover {{
                border-color: {accent_color};
            }}
        """)
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(12)

        ico_lbl = QLabel(icon)
        ico_lbl.setStyleSheet(f"""
            font-size: 20px;
            background-color: {accent_color}22;
            color: {accent_color};
            border-radius: 8px;
            padding: 6px;
        """)
        lay.addWidget(ico_lbl)

        info_lay = QVBoxLayout()
        info_lay.setSpacing(2)
        
        self.val_lbl = QLabel("-")
        self.val_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #ffffff;")
        
        self.desc_lbl = QLabel("-")
        self.desc_lbl.setStyleSheet("font-size: 11px; color: #a8a29e; font-weight: 500;")
        
        info_lay.addWidget(self.val_lbl)
        info_lay.addWidget(self.desc_lbl)
        lay.addLayout(info_lay)
        lay.addStretch()

    def update_data(self, value: str, label: str):
        self.val_lbl.setText(value)
        self.desc_lbl.setText(label)


class DashboardView(QWidget):
    def __init__(self, db, main_window=None):
        super().__init__()
        self.db = db
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 20)
        main_layout.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        content = QWidget()
        self.content_lay = QVBoxLayout(content)
        self.content_lay.setContentsMargins(0, 0, 0, 0)
        self.content_lay.setSpacing(16)

        # 1. Başlık & Hızlı İşlemler
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        self.lbl_greet = QLabel("İyi Günler! ☁️")
        self.lbl_greet.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        
        self.lbl_clock = QLabel()
        self.lbl_clock.setStyleSheet("font-size: 14px; color: #a1a1aa;")
        
        self.lbl_weather = QLabel("Hava Durumu Yükleniyor...")
        self.lbl_weather.setStyleSheet("font-size: 14px; color: #38bdf8; font-weight: bold;")
        
        self.btn_semester = QPushButton("Dönem Tarihleri Hesaplanıyor...")
        self.btn_semester.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_semester.setStyleSheet("text-align: left; font-size: 13px; color: #fbbf24; font-weight: bold; background: rgba(251, 191, 36, 0.15); padding: 4px 8px; border-radius: 6px; margin-top: 4px; border: 1px solid rgba(251, 191, 36, 0.3);")
        self.btn_semester.clicked.connect(self.dialog_set_semester_dates)
        
        # Sadece temel bilgileri dar kutuya ekliyoruz
        title_box.addWidget(self.lbl_greet)
        title_box.addWidget(self.lbl_clock)
        title_box.addWidget(self.lbl_weather)
        title_box.addWidget(self.btn_semester) 
        
        header_row.addLayout(title_box)
        header_row.addStretch()

        btn_quick_note = QPushButton("✏️  Hızlı Not")
        btn_quick_note.setObjectName("QuickNoteButton")
        btn_quick_note.setMinimumSize(120, 40)
        btn_quick_note.setCursor(QCursor(Qt.PointingHandCursor))
        btn_quick_note.setStyleSheet("QPushButton#QuickNoteButton { background: #1e3a5f; border: 1px solid #60a5fa; color: #dbeafe; border-radius: 9px; padding: 8px 14px; font-weight: 800; } QPushButton#QuickNoteButton:hover { background: #2563eb; color: white; }")
        btn_quick_note.clicked.connect(self.dialog_quick_note)

        btn_quick_plan = QPushButton("➕  Plan Ekle")
        btn_quick_plan.setObjectName("QuickPlanButton")
        btn_quick_plan.setMinimumSize(125, 40)
        btn_quick_plan.setCursor(QCursor(Qt.PointingHandCursor))
        btn_quick_plan.setStyleSheet("QPushButton#QuickPlanButton { background: #166534; border: 1px solid #4ade80; color: #f0fdf4; border-radius: 9px; padding: 8px 14px; font-weight: 800; } QPushButton#QuickPlanButton:hover { background: #22c55e; color: white; }")
        btn_quick_plan.clicked.connect(self.dialog_quick_plan)

        header_row.addWidget(btn_quick_note)
        header_row.addWidget(btn_quick_plan)
        
        # Başlık sırasını ana ekrana ekle
        self.content_lay.addLayout(header_row)

        # --- GÜNÜN SÖZÜ (Tam Genişlikte Yataya Yayılır) ---
        self.lbl_quote = QLabel()
        self.lbl_quote.setWordWrap(True)
        self.lbl_quote.setStyleSheet("font-size: 13.5px; font-style: italic; color: #f59e0b; padding: 4px 0px 8px 0px;")
        
        # Günün sözünü butonların altındaki yepyeni bir tam genişlik satırına ekliyoruz
        self.content_lay.addWidget(self.lbl_quote)
        self.content_lay.addWidget(self.create_section_divider())

        # 2. KPI Rozetleri
        self.kpi_layout = QHBoxLayout()
        self.kpi_layout.setSpacing(12)
        
        self.badge_classes = StatBadge("🎓", "#38bdf8")
        self.badge_exams = StatBadge("🎯", "#f43f5e")
        self.badge_habits = StatBadge("⚡", "#10b981")
        self.badge_workout = StatBadge("🏋️", "#f59e0b")
        
        self.kpi_layout.addWidget(self.badge_classes)
        self.kpi_layout.addWidget(self.badge_exams)
        self.kpi_layout.addWidget(self.badge_habits)
        self.kpi_layout.addWidget(self.badge_workout)
        
        self.content_lay.addLayout(self.kpi_layout)
        self.content_lay.addWidget(self.create_section_divider())

        # 3. Grafik Bölümü (Analitik Kartı)
        self.charts_card = self.create_analytics_card()
        self.content_lay.addWidget(self.charts_card)
        self.content_lay.addWidget(self.create_section_divider())

        self.study_time_card = self.create_study_time_card()
        self.content_lay.addWidget(self.study_time_card)
        self.content_lay.addWidget(self.create_section_divider())

        # 4. Ana Detay Grid Paneli
        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        self.content_lay.addLayout(self.grid)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Günün Sözünü Ayarla
        self._set_daily_quote()

        # --- DİNAMİK ZAMANLAYICILAR ---
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.fetch_weather)
        self.weather_timer.start(1800000)

        self.weather_connection_timer = QTimer(self)
        self.weather_connection_timer.timeout.connect(self.check_weather_connection)
        self.weather_connection_timer.start(15000)
        self.weather_online = None
        self.weather_refresh_pending = False
        self.network_information = None
        self.setup_network_monitor()

        self.fetch_weather()

        self.refresh()

    def _set_daily_quote(self):
        import random
        quotes = [
            "“Her şey seninle başlar.” – Mümin Sekman",
            "“Büyük işler başarmak için önce hayal etmeliyiz, sonra planlamalıyız, sonra inanmalıyız, sonra da harekete geçmeliyiz.”",
            "“Başlamak için mükemmel olmayı beklemeyin. Mükemmel olmak için başlayın.”",
            "“Başarının sırrı, sıradan şeyleri sıra dışı yapmaktır.” – John D. Rockefeller",
            "“Gelecek, bugünden ona hazırlananlara aittir.” – Malcolm X",
            "“Başarısızlık, daha akıllıca başlamak için bir fırsattır.” – Henry Ford",
            "“Zorluklar, karakteri ortaya çıkarır.” – Epiktetos",
            "“Yapabileceğinize de inansanız, yapamayacağınıza da inansanız haklısınız.” – Henry Ford",
            "“Düşüncelerini değiştir, dünyan değişsin.” – Norman Vincent Peale",
            "“Hiçbir zaman pes etme, kaybedenler hep pes edenlerdir.”",
            "“Eğitim, dünyayı değiştirmek için kullanabileceğiniz en güçlü silahtır.” – Nelson Mandela",
            "“Sınırları zorlamadıkça neleri başarabileceğini asla bilemezsin.”"
        ]
        
        # Güne özel rastgeleliği sabitle (Aynı gün içinde hep aynı söz çıkar)
        seed = int(datetime.now().strftime("%Y%m%d"))
        rng = random.Random(seed)
        daily_quote = rng.choice(quotes)
        self.lbl_quote.setText(daily_quote)

    def dialog_set_semester_dates(self):
        from PySide6.QtWidgets import QDateEdit
        from PySide6.QtCore import QDate

        dlg = QDialog(self)
        dlg.setWindowTitle("Dönem Tarihlerini Belirle")
        dlg.resize(300, 150)
        lay = QVBoxLayout(dlg)
        
        start_dt = QDateEdit()
        start_dt.setCalendarPopup(True)
        start_dt.setDisplayFormat("dd.MM.yyyy")
        end_dt = QDateEdit()
        end_dt.setCalendarPopup(True)
        end_dt.setDisplayFormat("dd.MM.yyyy")
        
        s_str, e_str = self._get_semester_bounds()
        if s_str and s_str != "0001-01-01":
            try: start_dt.setDate(QDate.fromString(s_str, "yyyy-MM-dd"))
            except: start_dt.setDate(QDate.currentDate())
        else:
            start_dt.setDate(QDate.currentDate())
            
        if e_str and e_str != "9999-12-31":
            try: end_dt.setDate(QDate.fromString(e_str, "yyyy-MM-dd"))
            except: end_dt.setDate(QDate.currentDate().addMonths(4))
        else:
            end_dt.setDate(QDate.currentDate().addMonths(4))
            
        lay.addWidget(QLabel("Dönem Başlangıç Tarihi:"))
        lay.addWidget(start_dt)
        lay.addWidget(QLabel("Dönem Bitiş Tarihi:"))
        lay.addWidget(end_dt)
        
        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")
        lay.addWidget(btn_save)
        
        def save():
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                s_val = start_dt.date().toString("yyyy-MM-dd")
                e_val = end_dt.date().toString("yyyy-MM-dd")
                
                cur.execute("SELECT 1 FROM app_settings WHERE setting_key = 'semester_start_date'")
                if cur.fetchone():
                    cur.execute("UPDATE app_settings SET setting_value = ? WHERE setting_key = 'semester_start_date'", (s_val,))
                else:
                    cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES ('semester_start_date', ?)", (s_val,))
                    
                cur.execute("SELECT 1 FROM app_settings WHERE setting_key = 'semester_end_date'")
                if cur.fetchone():
                    cur.execute("UPDATE app_settings SET setting_value = ? WHERE setting_key = 'semester_end_date'", (e_val,))
                else:
                    cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES ('semester_end_date', ?)", (e_val,))
                conn.commit()
                
            dlg.accept()
            self.refresh()
            try:
                from core.sound import play_action_sound
                play_action_sound("save")
            except: pass
            
        btn_save.clicked.connect(save)
        dlg.exec()

    def create_section_divider(self):
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.22); border: none; margin: 2px 0;")
        return divider

    def update_clock(self):
        now = datetime.now()
        months = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        
        time_str = now.strftime("%H:%M:%S")
        date_str = f"{now.day} {months[now.month]} {now.year}, {days[now.weekday()]}"
        
        self.lbl_clock.setText(f"Bugünün Akışı — {time_str}  |  {date_str}")

    def fetch_weather(self):
        if hasattr(self, 'weather_worker') and self.weather_worker.isRunning():
            self.weather_refresh_pending = True
            return

        self.weather_refresh_pending = False
        self.weather_worker = WeatherWorker(self.db)
        self.weather_worker.result_ready.connect(self.set_weather_text)
        self.weather_worker.finished.connect(self.on_weather_finished)
        self.weather_worker.finished.connect(self.weather_worker.deleteLater)
        self.weather_worker.start()

    def on_weather_finished(self):
        if self.weather_refresh_pending and self.weather_online is not False:
            self.weather_refresh_pending = False
            QTimer.singleShot(250, self.fetch_weather)

    def setup_network_monitor(self):
        try:
            QNetworkInformation.loadDefaultBackend()
            self.network_information = QNetworkInformation.instance()
            if self.network_information:
                self.network_information.reachabilityChanged.connect(
                    self.handle_network_reachability
                )
        except (ImportError, RuntimeError):
            self.network_information = None

    def handle_network_reachability(self, reachability):
        if reachability == QNetworkInformation.Reachability.Disconnected:
            self.weather_online = False
            self.set_weather_text("🔌 Offline")
        elif reachability in (
            QNetworkInformation.Reachability.Site,
            QNetworkInformation.Reachability.Online,
        ):
            self.weather_online = True
            self.set_weather_text("Hava durumu güncelleniyor...")
            self.weather_refresh_pending = True
            self.fetch_weather()

    def check_weather_connection(self):
        from core.network import check_internet_connection

        online = check_internet_connection(timeout=3)
        if online == self.weather_online:
            return

        self.weather_online = online
        if not online:
            self.set_weather_text("🔌 Offline")
            return

        self.set_weather_text("Hava durumu güncelleniyor...")
        self.weather_refresh_pending = True
        self.fetch_weather()

    def set_weather_text(self, text):
        try:
            if text.startswith("🔌 Offline"):
                self.weather_online = False
            elif text and text != "Hava durumu güncelleniyor...":
                self.weather_online = True
            self.lbl_weather.setText(text)
        except RuntimeError:
            pass

    def create_analytics_card(self):
        card = QFrame()
        card.setObjectName("Card")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(24)

        bar_box = QVBoxLayout()
        bar_title = QLabel("📊 Son 7 Gün Alışkanlıkları")
        bar_title.setWordWrap(False)
        bar_title.setStyleSheet("background: #17324d; border: 1px solid #2563eb; border-radius: 7px; padding: 7px 10px; font-size: 13px; font-weight: 800; color: #dbeafe;")
        self.bar_chart = HabitWeeklyBarChart([])
        bar_box.addWidget(bar_title)
        bar_box.addWidget(self.bar_chart)
        lay.addLayout(bar_box, stretch=3)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #292524;")
        lay.addWidget(sep)

        donut_box = QVBoxLayout()
        donut_title = QLabel("🎯 Sınav Dağılımı")
        donut_title.setWordWrap(False)
        donut_title.setStyleSheet("background: #3b1d68; border: 1px solid #8b5cf6; border-radius: 7px; padding: 7px 10px; font-size: 13px; font-weight: 800; color: #ede9fe;")
        self.donut_chart = AssessmentDonutChart([])
        donut_box.addWidget(donut_title)
        donut_box.addWidget(self.donut_chart)
        lay.addLayout(donut_box, stretch=2)

        return card

    def create_study_time_card(self):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("⏱️ Ders Çalışma Süresi")
        title.setWordWrap(False)
        title.setMinimumWidth(165)
        title.setStyleSheet("background: #134e4a; border: 1px solid #14b8a6; border-radius: 7px; padding: 5px 7px; font-size: 11px; font-weight: 800; color: #ccfbf1;")
        self.study_time_summary = QLabel("Veri yok")
        self.study_time_summary.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 700;")

        btn_open_timer = QPushButton("⏱ Sayacı Aç")
        btn_open_timer.setCursor(QCursor(Qt.PointingHandCursor))
        btn_open_timer.setStyleSheet("background-color: #1c1917; color: #38bdf8; border: 1px solid #38bdf8; border-radius: 5px; padding: 5px 9px; font-weight: 600;")
        btn_open_timer.clicked.connect(self.open_focus_timer)

        self.study_period_combo = QComboBox()
        self.study_period_combo.addItems(["Haftalık", "Aylık", "3 Aylık", "Yıllık", "Tüm Zamanlar"])
        self.study_period_combo.setFixedWidth(130)
        self.study_period_combo.setStyleSheet("QComboBox { background-color: #1d4ed8; color: #dbeafe; border: 1px solid #60a5fa; border-radius: 7px; padding: 6px 8px; font-weight: 800; } QComboBox::drop-down { border: none; }")
        self.study_period_combo.currentIndexChanged.connect(self._update_study_chart)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.study_time_summary)
        header.addWidget(btn_open_timer)
        header.addWidget(self.study_period_combo)
        lay.addLayout(header)

        self.study_time_chart = StudyTimeBarChart([])
        lay.addWidget(self.study_time_chart)
        return card

    def open_focus_timer(self):
        if not self.main_window:
            return
        self.main_window.navigate_to(6)
        if hasattr(self.main_window, "music_view"):
            self.main_window.music_view.tabs.setCurrentIndex(2)

    def _get_semester_bounds(self):
        with self.db.get_connection() as conn:
            rows = conn.execute("""
                SELECT setting_key, setting_value
                FROM app_settings
                WHERE setting_key IN ('semester_start_date', 'semester_end_date')
            """).fetchall()

        settings = {row["setting_key"]: row["setting_value"] for row in rows}
        return (
            settings.get("semester_start_date") or "0001-01-01",
            settings.get("semester_end_date") or "9999-12-31",
        )

    def refresh(self):
        now = datetime.now()
        hour = now.hour
        if 5 <= hour < 12:
            greet = "Günaydın! ☀️"
        elif 12 <= hour < 18:
            greet = "İyi Günler! 🌤️"
        elif 18 <= hour < 23:
            greet = "İyi Akşamlar! 🌙"
        else:
            greet = "İyi Geceler, Geç Saat Çalışması! 🦉"

        self.lbl_greet.setText(greet)

        today_dow = now.weekday()
        today_iso = date.today().isoformat()
        semester_start, semester_end = self._get_semester_bounds()

        # --- DÖNEM SAYAÇ GÜNCELLEMESİ ---
        try:
            if semester_start == "0001-01-01" or semester_end == "9999-12-31" or not semester_start or not semester_end:
                self.btn_semester.setText("⏳ Dönem tarihleri ayarlanmadı (Tıklayın)")
                self.btn_semester.setStyleSheet("text-align: left; font-size: 13px; color: #a1a1aa; font-weight: bold; background: #27272a; padding: 6px 10px; border-radius: 6px; margin-top: 4px; border: none;")
            else:
                s_date = datetime.strptime(semester_start, "%Y-%m-%d").date()
                e_date = datetime.strptime(semester_end, "%Y-%m-%d").date()
                today_d = date.today()
                
                if today_d < s_date:
                    rem = (s_date - today_d).days
                    self.btn_semester.setText(f"⏳ Dönem Başlangıcına: {rem} Gün Kaldı")
                    self.btn_semester.setStyleSheet("text-align: left; font-size: 13px; color: #38bdf8; font-weight: bold; background: rgba(56, 189, 248, 0.15); padding: 6px 10px; border-radius: 6px; margin-top: 4px; border: 1px solid rgba(56, 189, 248, 0.3);")
                elif s_date <= today_d <= e_date:
                    rem = (e_date - today_d).days
                    self.btn_semester.setText(f"⏳ Dönemin Bitmesine: {rem} Gün Kaldı")
                    self.btn_semester.setStyleSheet("text-align: left; font-size: 13px; color: #fbbf24; font-weight: bold; background: rgba(251, 191, 36, 0.15); padding: 6px 10px; border-radius: 6px; margin-top: 4px; border: 1px solid rgba(251, 191, 36, 0.3);")
                else:
                    self.btn_semester.setText("⏳ Dönem Sona Erdi (Yeni tarih seçin)")
                    self.btn_semester.setStyleSheet("text-align: left; font-size: 13px; color: #f43f5e; font-weight: bold; background: rgba(244, 63, 94, 0.15); padding: 6px 10px; border-radius: 6px; margin-top: 4px; border: 1px solid rgba(244, 63, 94, 0.3);")
        except Exception:
            self.btn_semester.setText("⏳ Dönem bilgisi hesaplanamadı")
                
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*)
                FROM timetable
                WHERE day_of_week = ? AND ? BETWEEN ? AND ?
            """, (today_dow, today_iso, semester_start, semester_end))
            c_cnt = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM assessments WHERE due_date >= ?", (today_iso,))
            e_cnt = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM habits")
            h_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM habit_logs WHERE date = ? AND is_completed = 1", (today_iso,))
            h_done = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM workout_exercises WHERE day_of_week = ?", (today_dow,))
            w_cnt = cur.fetchone()[0]

        h_pct = int((h_done / h_total * 100)) if h_total > 0 else 0
        w_text = f"{w_cnt} Hareket" if w_cnt > 0 else "Dinlenme Günü"

        self.badge_classes.update_data(f"{c_cnt} Ders", "Bugünkü Program")
        self.badge_exams.update_data(f"{e_cnt} Aktif", "Gelecek Sınavlar")
        self.badge_habits.update_data(f"%{h_pct}", f"{h_done}/{h_total} Alışkanlık")
        self.badge_workout.update_data(w_text, f"{DAYS_TR[today_dow]} Rutini")

        self._update_charts()
        self._update_study_chart()
        self._rebuild_grid()

    def _update_charts(self):
        today = date.today()
        bar_data = []
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            for i in range(6, -1, -1):
                day_target = today - timedelta(days=i)
                iso_d = day_target.isoformat()
                cur.execute("SELECT COUNT(*) FROM habit_logs WHERE date = ? AND is_completed = 1", (iso_d,))
                cnt = cur.fetchone()[0]
                day_name = DAYS_SHORT_TR[day_target.weekday()]
                bar_data.append((day_name, cnt))

        self.bar_chart.set_data(bar_data)

        segments = []
        colors = ["#38bdf8", "#f43f5e", "#10b981", "#f59e0b", "#a855f7"]
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.title, a.weight
                FROM assessments a
                JOIN courses c ON c.id = a.course_id
                ORDER BY a.due_date ASC
                LIMIT 5
            """)
            for idx, r in enumerate(cur.fetchall()):
                c = colors[idx % len(colors)]
                segments.append((r["title"], r["weight"], c))

        self.donut_chart.set_segments(segments)

    def _update_study_chart(self):
        today = date.today()
        period = self.study_period_combo.currentText()
        is_all_time = period == "Tüm Zamanlar"
        is_yearly = period == "Yıllık"
        is_monthly = period in ("Aylık", "3 Aylık")
        day_count = {"Haftalık": 7, "Aylık": 30, "3 Aylık": 90}.get(period, 365)
        start_date = today - timedelta(days=day_count - 1)
        daily_seconds = {}

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if is_all_time:
                cur.execute("SELECT log_date, seconds FROM study_time_logs ORDER BY log_date ASC")
            else:
                cur.execute(
                    "SELECT log_date, seconds FROM study_time_logs WHERE log_date BETWEEN ? AND ?",
                    (start_date.isoformat(), today.isoformat()),
                )
            daily_seconds = {row["log_date"]: row["seconds"] for row in cur.fetchall()}

        if is_all_time or is_yearly:
            months = {}
            for log_date, seconds in daily_seconds.items():
                month_key = log_date[:7]
                months[month_key] = months.get(month_key, 0) + seconds
            if is_yearly:
                month_limit = (today.replace(day=1) - timedelta(days=335)).strftime("%Y-%m")
                months = {key: value for key, value in months.items() if key >= month_limit}
            chart_data = []
            month_names = ["", "Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
            for month_key in sorted(months):
                year, month = (int(value) for value in month_key.split("-"))
                chart_data.append((f"{month_names[month]} {year}", months[month_key]))
        elif is_monthly:
            chart_data = []
            week_count = (day_count + 6) // 7
            for bucket in range(week_count):
                bucket_start = start_date + timedelta(days=bucket * 7)
                bucket_end = min(today, bucket_start + timedelta(days=6))
                seconds = sum(
                    daily_seconds.get((bucket_start + timedelta(days=offset)).isoformat(), 0)
                    for offset in range((bucket_end - bucket_start).days + 1)
                )
                chart_data.append((f"{bucket + 1}. Hafta", seconds))
        else:
            chart_data = []
            for offset in range(day_count):
                target = start_date + timedelta(days=offset)
                chart_data.append((DAYS_SHORT_TR[target.weekday()], daily_seconds.get(target.isoformat(), 0)))

        total_seconds = sum(seconds for _, seconds in chart_data)
        total_hours = total_seconds / 3600
        period_labels = {
            "Haftalık": "son 7 gün",
            "Aylık": "son 30 gün",
            "3 Aylık": "son 90 gün",
            "Yıllık": "son 12 ay",
            "Tüm Zamanlar": "tüm zamanlar",
        }
        period_label = period_labels[period]
        self.study_time_summary.setText(f"{total_hours:.1f} saat • {period_label}")
        self.study_time_chart.set_data(chart_data)

    def _rebuild_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.grid.addWidget(self.create_timeline_card(), 0, 0)
        self.grid.addWidget(self.create_interactive_habits_card(), 1, 0)
        self.grid.addWidget(self.create_exam_countdown_card(), 0, 1)
        self.grid.addWidget(self.create_workout_focus_card(), 1, 1)

        self.grid.addWidget(self.create_library_card(), 2, 0, 1, 2)
    def create_timeline_card(self):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        title = QLabel("🕒 Günün Akışı")
        title.setObjectName("CardHeader")
        title.setWordWrap(False)
        title.setStyleSheet("background: #1c3042; border: 1px solid #2563eb; border-radius: 7px; padding: 6px 8px; font-size: 13px; font-weight: 800; color: #dbeafe;")
        lay.addWidget(title)

        today_dow = datetime.now().weekday()
        today_iso = date.today().isoformat()
        semester_start, semester_end = self._get_semester_bounds()
        items = []

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                  SELECT c.code, c.name, COALESCE(t.classroom, c.classroom) AS classroom,
                      t.start_time, t.end_time, c.color_hex
                FROM timetable t 
                JOIN courses c ON t.course_id = c.id 
                WHERE t.day_of_week = ? AND ? BETWEEN ? AND ?
            """, (today_dow, today_iso, semester_start, semester_end))
            for r in cur.fetchall():
                items.append({
                    "time": r["start_time"],
                    "title": f"Ders: {r['code']} — {r['name']}",
                    "sub": f"📍 {r['classroom']}",
                    "color": r["color_hex"] if r["color_hex"] else "#38bdf8"
                })

            cur.execute("""
                SELECT title, start_time, category, is_completed 
                FROM calendar_events 
                WHERE event_date = ?
            """, (today_iso,))
            for r in cur.fetchall():
                st = r["start_time"] if r["start_time"] else "--:--"
                items.append({
                    "time": st,
                    "title": f"Plan: {r['title']}",
                    "sub": f"🏷️ {r['category']}" + (" (Tamamlandı)" if r["is_completed"] else ""),
                    "color": "#10b981" if r["is_completed"] else "#f59e0b"
                })

        items.sort(key=lambda x: x["time"])

        if not items:
            lbl = QLabel("Bugün için kayıtlı ders veya plan bulunmuyor.")
            lbl.setStyleSheet("color: #71717a; font-style: italic; padding: 8px 0;")
            lay.addWidget(lbl)
        else:
            for it in items:
                row = QHBoxLayout()
                row.setContentsMargins(8, 6, 8, 6)
                row.setSpacing(10)

                time_lbl = QLabel(f"<b>{it['time']}</b>")
                time_lbl.setFixedWidth(50)
                time_lbl.setStyleSheet(f"color: {it['color']}; font-size: 13px;")

                content_box = QVBoxLayout()
                content_box.setSpacing(2)
                
                main_l = QLabel(it["title"])
                main_l.setWordWrap(True)
                main_l.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 600;")
                
                sub_l = QLabel(it["sub"])
                sub_l.setWordWrap(True)
                sub_l.setStyleSheet("color: #a1a1aa; font-size: 11px;")
                
                content_box.addWidget(main_l)
                content_box.addWidget(sub_l)

                row.addWidget(time_lbl)
                row.addLayout(content_box, stretch=1)

                box = QFrame()
                box.setLayout(row)
                box.setStyleSheet(f"background: #1c1917; border-left: 3px solid {it['color']}; border-radius: 6px;")
                lay.addWidget(box)

        lay.addStretch()
        return card

    def create_interactive_habits_card(self):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        title = QLabel("⚡ Alışkanlık İlerlemesi")
        title.setObjectName("CardHeader")
        title.setWordWrap(False)
        title.setStyleSheet("background: #134e4a; border: 1px solid #14b8a6; border-radius: 7px; padding: 6px 8px; font-size: 13px; font-weight: 800; color: #ccfbf1;")
        lay.addWidget(title)

        today_iso = date.today().isoformat()
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, title FROM habits")
            habits = cur.fetchall()

        if not habits:
            lbl = QLabel("Henüz alışkanlık eklenmedi.")
            lbl.setStyleSheet("color: #71717a; font-style: italic;")
            lay.addWidget(lbl)
        else:
            completed_count = 0
            for h in habits:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT is_completed FROM habit_logs WHERE habit_id = ? AND date = ?", (h["id"], today_iso))
                    row = cur.fetchone()
                    is_done = bool(row and row["is_completed"])
                    if is_done:
                        completed_count += 1

                cb = QCheckBox(h["title"])
                cb.setChecked(is_done)
                cb.toggled.connect(lambda checked, h_id=h["id"]: self._toggle_habit(h_id, checked))
                lay.addWidget(cb)

            pct = int((completed_count / len(habits)) * 100)
            pbar = QProgressBar()
            pbar.setValue(pct)
            pbar.setFixedHeight(6)
            pbar.setTextVisible(False)
            pbar.setStyleSheet("QProgressBar { background: #27272a; border-radius: 3px; } QProgressBar::chunk { background: #10b981; border-radius: 3px; }")
            lay.addSpacing(4)
            lay.addWidget(pbar)

        lay.addStretch()
        return card

    def _toggle_habit(self, habit_id: int, is_checked: bool):
        today_iso = date.today().isoformat()
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if is_checked:
                cur.execute("INSERT OR REPLACE INTO habit_logs (habit_id, date, is_completed) VALUES (?, ?, 1)", (habit_id, today_iso))
            else:
                cur.execute("DELETE FROM habit_logs WHERE habit_id = ? AND date = ?", (habit_id, today_iso))
            conn.commit()

            bus.habits_changed.emit()
        play_action_sound("complete")
        self.refresh()

    def create_exam_countdown_card(self):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        title = QLabel("🎯 Sınavlar & Teslimler")
        title.setObjectName("CardHeader")
        title.setWordWrap(False)
        title.setStyleSheet("background: #3b1d68; border: 1px solid #8b5cf6; border-radius: 7px; padding: 6px 8px; font-size: 13px; font-weight: 800; color: #ede9fe;")
        lay.addWidget(title)

        today = date.today()
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.title, a.due_date, a.weight, c.code 
                FROM assessments a
                JOIN courses c ON a.course_id = c.id
                ORDER BY a.due_date ASC LIMIT 4
            """)
            exams = cur.fetchall()

        if not exams:
            lbl = QLabel("Yakın zamanda planlanmış sınav bulunmuyor.")
            lbl.setStyleSheet("color: #71717a; font-style: italic;")
            lay.addWidget(lbl)
        else:
            for ex in exams:
                try:
                    dt = datetime.strptime(ex["due_date"], "%Y-%m-%d %H:%M").date()
                    days = (dt - today).days
                except Exception:
                    days = 999

                row = QHBoxLayout()
                info = QLabel(f"<b>{ex['code']}</b>: {ex['title']} (%{ex['weight']})")
                info.setWordWrap(True)
                info.setStyleSheet("color: #f4f4f5; font-size: 13px;")

                if days < 0:
                    badge = QLabel("Geçti")
                    badge.setStyleSheet("color: #71717a; font-size: 11px;")
                elif days == 0:
                    badge = QLabel("BUGÜN!")
                    badge.setStyleSheet("background: #e11d48; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;")
                elif days <= 3:
                    badge = QLabel(f"Son {days} Gün!")
                    badge.setStyleSheet("background: #ea580c; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;")
                else:
                    badge = QLabel(f"{days} Gün")
                    badge.setStyleSheet("background: #27272a; color: #a1a1aa; padding: 2px 6px; border-radius: 4px; font-size: 11px;")

                row.addWidget(info, stretch=1)
                row.addWidget(badge)

                container = QFrame()
                container.setLayout(row)
                container.setStyleSheet("background: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 2px 6px;")
                lay.addWidget(container)

        lay.addStretch()
        return card

    def create_workout_focus_card(self):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        today_dow = datetime.now().weekday()
        title = QLabel(f"🏋️ Günün Antrenmanı ({DAYS_TR[today_dow]})")
        title.setObjectName("CardHeader")
        title.setWordWrap(False)
        title.setStyleSheet("background: #4a2a0a; border: 1px solid #f59e0b; border-radius: 7px; padding: 6px 8px; font-size: 13px; font-weight: 800; color: #fef3c7;")
        lay.addWidget(title)

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT exercise_name, sets, reps, weight 
                FROM workout_exercises 
                WHERE day_of_week = ?
            """, (today_dow,))
            exercises = cur.fetchall()

        if not exercises:
            lbl = QLabel("Bugün planlanmış egzersiz yok (Dinlenme Günü).")
            lbl.setStyleSheet("color: #71717a; font-style: italic; padding: 8px 0;")
            lay.addWidget(lbl)
        else:
            total_vol = 0.0
            for ex in exercises:
                w = ex["weight"] if ex["weight"] else 0.0
                total_vol += (ex["sets"] * ex["reps"] * w)

                row = QHBoxLayout()
                e_name = QLabel(f"• {ex['exercise_name']}")
                e_name.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 13px;")
                
                details = QLabel(f"{ex['sets']} x {ex['reps']} @ {w} kg")
                details.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")

                row.addWidget(e_name)
                row.addStretch()
                row.addWidget(details)

                box = QFrame()
                box.setLayout(row)
                box.setStyleSheet("background: #18181b; border-radius: 6px; padding: 4px 8px;")
                lay.addWidget(box)

            if total_vol > 0:
                lbl_vol = QLabel(f"Toplam Hedef Tonaj: <b>{total_vol:.0f} kg</b>")
                lbl_vol.setStyleSheet("color: #a1a1aa; font-size: 12px; margin-top: 4px;")
                lay.addWidget(lbl_vol)

        lay.addStretch()
        return card

    def create_library_card(self):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # Kart Başlığı
        title = QLabel("📖 Kitaplık & Okuma Durumu")
        title.setObjectName("CardHeader")
        title.setWordWrap(False)
        title.setStyleSheet("background: #115e59; border: 1px solid #10b981; border-radius: 7px; padding: 6px 8px; font-size: 13px; font-weight: 800; color: #d1fae5;")
        lay.addWidget(title)

        # Veritabanından İstatistikleri Çekme
        finished_count = 0
        total_pages = 0
        current_books = []
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                # Bitirilen Kitap Sayısı
                cur.execute("SELECT COUNT(*) FROM books WHERE status = 'Okundu'")
                finished_count = cur.fetchone()[0] or 0
                
                # Okunan Toplam Sayfa
                cur.execute("SELECT SUM(page_count) FROM books WHERE status = 'Okundu'")
                total_pages = cur.fetchone()[0] or 0
                
                # Okunmakta Olan TÜM Kitaplar (LIMIT 1 kaldırıldı)
                cur.execute("SELECT title, author, page_count FROM books WHERE status = 'Okunuyor' ORDER BY id DESC")
                current_books = cur.fetchall()
        except Exception:
            pass # Eğer books tablosu henüz yoksa hata vermesini engeller
            
        # İstatistik Etiketi
        lbl_lib_stats = QLabel(f"📚 Bitirilen: {finished_count} Kitap  |  📄 Okunan Toplam: {total_pages} Sayfa")
        lbl_lib_stats.setStyleSheet("color: #a1a1aa; font-size: 12px; font-weight: bold; margin-bottom: 2px;")
        lay.addWidget(lbl_lib_stats)
        
        # Aktif Okunan Kitap(lar) Kutusu
        lbl_current_book = QLabel()
        lbl_current_book.setStyleSheet("""
            QLabel {
                background-color: rgba(16, 185, 129, 0.1); 
                border: 1px solid rgba(16, 185, 129, 0.25); 
                border-radius: 8px; 
                padding: 12px;
            }
        """)
        lbl_current_book.setWordWrap(True)
        
        if current_books:
            html_content = ""
            for i, book in enumerate(current_books):
                b_title = book["title"]
                b_author = book["author"] or "Bilinmeyen Yazar"
                b_pages = book["page_count"] or 0
                
                # Kitapların arasına şık bir ayırıcı çizgi (border) ekleme
                margin_bottom = "8px" if i < len(current_books) - 1 else "0px"
                padding_bottom = "8px" if i < len(current_books) - 1 else "0px"
                border_bottom = "border-bottom: 1px solid rgba(16, 185, 129, 0.25);" if i < len(current_books) - 1 else ""
                
                html_content += f"""
                <div style='margin-bottom: {margin_bottom}; padding-bottom: {padding_bottom}; {border_bottom}'>
                    <div style='margin-bottom: 4px;'><b style='color:#34d399; font-size:14px;'>{b_title}</b></div>
                    <div style='color:#d4d4d8; font-size:12px;'>✍️ {b_author} &nbsp;•&nbsp; 🔖 {b_pages} Sayfa</div>
                </div>
                """
            lbl_current_book.setText(html_content)
        else:
            lbl_current_book.setText(
                "<span style='color:#a1a1aa; font-style:italic;'>Şu an aktif olarak okuduğunuz bir kitap bulunmuyor.<br>Kitaplığınızdan yeni bir serüvene başlayın!</span>"
            )
            
        lay.addWidget(lbl_current_book)
        lay.addStretch()
        return card
    # =========================================================================
    # HIZLI İŞLEM DİYALOGLARI
    # =========================================================================
    def dialog_quick_note(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Hızlı Not Al")
        dlg.resize(360, 260)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)

        title_in = QLineEdit()
        title_in.setPlaceholderText("Not Başlığı (örn: Mat-1 Diferansiyel İpuçları)")
        
        content_in = QTextEdit()
        content_in.setPlaceholderText("Not içeriğini buraya yazın...")

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")

        lay.addWidget(QLabel("Başlık:"))
        lay.addWidget(title_in)
        lay.addWidget(QLabel("İçerik:"))
        lay.addWidget(content_in)
        lay.addWidget(btn_save)

        def save():
            t = title_in.text().strip()
            c = content_in.toPlainText().strip()
            if not t:
                play_action_sound("error")
                QMessageBox.warning(dlg, "Uyarı", "Lütfen bir başlık girin.")
                return

            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO notes (title, content) VALUES (?, ?)", (t, c))
                    conn.commit()
                    bus.notes_changed.emit()
                    bus.item_saved.emit(f"Hızlı not kaydedildi: {t}")
                dlg.accept()
                play_action_sound("save")
                QMessageBox.information(self, "Başarılı", f"'{t}' notu başarıyla kaydedildi! Materyal Havuzu sekmesinden erişebilirsiniz.")
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", f"Not kaydedilemedi: {e}")

        btn_save.clicked.connect(save)
        dlg.exec()

    def dialog_quick_plan(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Bugüne Hızlı Plan Ekle")
        dlg.resize(320, 200)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)

        title_in = QLineEdit()
        title_in.setPlaceholderText("Plan (örn: 2 Saat Kütüphanede Soru Çözümü)")
        
        time_in = QLineEdit("15:00")
        time_in.setPlaceholderText("Saat (Örn: 15:00)")

        btn_save = QPushButton("Ekle")
        btn_save.setObjectName("AccentButton")

        lay.addWidget(QLabel("Plan Başlığı:"))
        lay.addWidget(title_in)
        lay.addWidget(QLabel("Başlangıç Saati:"))
        lay.addWidget(time_in)
        lay.addWidget(btn_save)

        def save():
            t = title_in.text().strip()
            if not t:
                return
            today_iso = date.today().isoformat()
            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO calendar_events (title, event_date, start_time, category) 
                        VALUES (?, ?, ?, 'Ders Çalışma')
                    """, (t, today_iso, time_in.text().strip()))
                    conn.commit()
                    bus.calendar_changed.emit()
                    bus.item_saved.emit(f"Bugüne plan eklendi: {t}")
                play_action_sound("save")
                dlg.accept()
                self.refresh()
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", f"Plan eklenemedi: {e}")

        btn_save.clicked.connect(save)
        dlg.exec()