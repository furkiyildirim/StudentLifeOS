import sys
import os
import shutil
import tempfile
import winreg
import ctypes
import json
from datetime import datetime, date, timedelta

from PySide6.QtWidgets import (
    QApplication, QDialog, QGraphicsDropShadowEffect, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QCheckBox,
    QSystemTrayIcon, QMenu, QStyle, QProgressBar, QGraphicsOpacityEffect,
    QSizePolicy, QComboBox, QScrollArea, QListWidget, QListWidgetItem,
    QMessageBox, QLineEdit, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QUrl, QVariantAnimation, QThread, Signal, QEvent, QSize
from PySide6.QtGui import QCursor, QDesktopServices, QIcon, QAction, QColor, QPixmap, QMovie
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings

from core.database import DatabaseManager
from core.events import bus
from core.sound import play_action_sound
from views.dashboard_view import DashboardView
from views.todo_view import TodoView
from views.calendar_view import CalendarView
from views.timetable_view import TimetableView
from views.vault_view import VaultView
from views.fitness_view import FitnessView
from views.music_view import MusicView
from views.university_view import UniversityView
from views.library_view import LibraryView

try:
    from views.project_view import ProjectView
except ImportError:
    ProjectView = None

# Ses dizini kontrolü
SOUNDS_DIR = "resources/notification_sounds" if os.path.exists("resources/notification_sounds") else "resources/notification_sounds"
if not os.path.exists(SOUNDS_DIR):
    os.makedirs(SOUNDS_DIR)

_SINGLE_INSTANCE_LOCK = None

def ensure_single_instance():
    global _SINGLE_INSTANCE_LOCK
    lock_name = "student_life_os_single_instance.lock"
    lock_path = os.path.join(tempfile.gettempdir(), lock_name)

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
    except FileExistsError:
        try:
            with open(lock_path, "r", encoding="ascii") as lock_file:
                existing_pid = int(lock_file.read().strip())
            
            if os.name != 'nt':
                os.kill(existing_pid, 0)
            else:
                # Windows'ta os.kill(pid, 0) desteklenmediği için yapay bir OSError fırlatıp kilit kontrolüne (except) geçiyoruz
                raise OSError("Windows process check fallback")
                
        except (FileNotFoundError, ProcessLookupError, ValueError, OSError):
            try:
                os.remove(lock_path)
            except PermissionError:
                # [WinError 32] Dosya kilitli ve başka bir işlem tarafından kullanılıyor.
                # Bu, uygulamanın şu anda aktif olarak çalıştığı anlamına gelir.
                return False
            except FileNotFoundError:
                pass
            
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError:
                return False
        else:
            return False

    _SINGLE_INSTANCE_LOCK = fd
    os.write(fd, str(os.getpid()).encode("ascii"))
    return True

def remove_single_instance_lock():
    global _SINGLE_INSTANCE_LOCK
    if _SINGLE_INSTANCE_LOCK is not None:
        try:
            os.close(_SINGLE_INSTANCE_LOCK)
        except OSError:
            pass
        _SINGLE_INSTANCE_LOCK = None

    lock_name = "student_life_os_single_instance.lock"
    lock_path = os.path.join(tempfile.gettempdir(), lock_name)
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass


def remove_autostart_entry():
    startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    legacy_file = os.path.join(startup_dir, "StudentLifeOS.bat")

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, "StudentLifeOS")
            except FileNotFoundError:
                pass
    except OSError:
        pass

    try:
        if os.path.exists(legacy_file):
            os.remove(legacy_file)
    except OSError:
        pass

GLOBAL_QSS = """
QMainWindow { background-color: #0c0a09; }
QWidget { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #f4f4f5; background: transparent; }
QLabel { qproperty-wordWrap: 1; }
#Sidebar { background-color: #0f0d0c; border-right: 1px solid #1c1917; }
#TopNavBar { background-color: #0f0d0c; border-bottom: 1px solid #1c1917; padding: 6px 16px; }
#NavHistButton { background-color: #171412; border: 1px solid #292524; color: #e7e5e4; border-radius: 6px; font-weight: bold; min-width: 32px; min-height: 28px; max-width: 32px; max-height: 28px; }
#NavHistButton:hover { background-color: #262220; color: #38bdf8; border-color: #3f3f46; }
#NavHistButton:disabled { background-color: #12100e; color: #44403c; border-color: #171412; }
#NavButton { text-align: left; padding: 11px 14px; font-size: 13px; font-weight: 500; border-radius: 6px; background: transparent; color: #a8a29e; border: none; margin: 2px 0px; }
#NavButton:hover { background-color: #191614; color: #fafaf9; }
#NavButton:checked { background-color: #211d1a; color: #38bdf8; font-weight: 600; border-left: 3px solid #38bdf8; border-top-left-radius: 0px; border-bottom-left-radius: 0px; }
#Card { background-color: #171412; border: 1px solid #292524; border-radius: 12px; padding: 16px; }
#CardHeader { qproperty-wordWrap: 0; background-color: #1c3042; border: 1px solid #2563eb; border-radius: 7px; font-size: 13px; font-weight: 800; color: #dbeafe; padding: 6px 8px; margin-bottom: 10px; }
QMenu { background-color: #18181b; color: #f4f4f5; border: 1px solid #52525b; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 8px 24px; border-radius: 5px; }
QMenu::item:selected { background-color: #3f3f46; color: #ffffff; }
QComboBox QAbstractItemView { background-color: #18181b; color: #f4f4f5; border: 1px solid #52525b; selection-background-color: #3f3f46; selection-color: #ffffff; padding: 4px; outline: none; }
"""

class WelcomeDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        
        # Arka planı şeffaf ve çerçevesiz yapıyoruz
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        
        # Arka Planı Karartan (Dim) Yarı Saydam Katman
        self.overlay_frame = QFrame(self)
        self.overlay_frame.setStyleSheet("background-color: rgba(9, 9, 11, 210);")
        overlay_lay = QVBoxLayout(self.overlay_frame)
        overlay_lay.setAlignment(Qt.AlignCenter)
        
        # Ortadaki Asıl Tanıtım Kartı (Gölge efekti kaldırıldı)
        self.card = QFrame()
        self.card.setFixedSize(620, 560)
        self.card.setObjectName("WelcomeCard")
        self.card.setStyleSheet("""
            QFrame#WelcomeCard {
                background-color: #171412; 
                border: 1px solid #38bdf8; 
                border-radius: 16px;
            }
            QLabel { border: none; background: transparent; }
        """)
        
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(30, 30, 30, 30)
        card_lay.setSpacing(16)
        
        # Başlık ve Açıklama
        title = QLabel("🎓 Student Life OS Tanıtım Rehberi")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #38bdf8;")
        title.setAlignment(Qt.AlignCenter)
        card_lay.addWidget(title)

        desc = QLabel("Uygulamadaki tüm modüllerin ne işe yaradığını aşağıdan inceleyebilirsiniz:")
        desc.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        desc.setAlignment(Qt.AlignCenter)
        card_lay.addWidget(desc)
        
        # Kaydırılabilir İçerik Alanı
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: 1px solid #292524; background: #12100e; border-radius: 10px; }
            QScrollBar:vertical { background: #171412; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #3f3f46; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #38bdf8; }
        """)
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(12, 12, 12, 12)
        content_lay.setSpacing(12)

        features = [
            ("📊 Kontrol Paneli", "Günlük özetinizi, hava durumunu, çalışma saatlerinizi ve yaklaşan tüm görev/sınavları tek bir ekrandan takip edin."),
            ("📋 Yapılacaklar (To-Do)", "Günlük görevlerinizi önceliklendirerek yönetin. Görevler eklendikçe ilerleme çubuğunuz dolsun."),
            ("📅 Akıllı Takvim", "Sınavlarınızı ve kişisel planlarınızı takvim üzerinde görün. Tamamlanan görevlerin üzerini anında çizin."),
            ("📚 Dersler & Notlar", "Haftalık ders programınızı oluşturun. Sınav notlarınızı girerek dönem (SPA) ve genel ortalamanızı (CGPA) hesaplayın."),
            ("📂 Materyal Havuzu", "PDF, Word ve PowerPoint dosyalarınızı okuyun. Zengin metin editörüyle ders notları tutun."),
            ("🏋️ Spor & Alışkanlık", "Haftalık antrenman programınızı yapın ve 'Zinciri Kırma' mantığıyla günlük alışkanlıklarınızı takip edin."),
            ("🎵 Müzik & Odak", "YouTube Music oynatıcısı ile müzik dinleyin ve Pomodoro sayacı ile odaklanarak çalışın."),
            ("🏫 Üniversite", "Üniversitenizin OBS (Öğrenci Bilgi Sistemi) ve e-posta hesaplarına güvenli tarayıcı üzerinden hızlıca erişin."),
            ("🚀 Projeler", "Uzun soluklu projelerinizi aşamalara bölün, ilerlemeyi çubuktan takip edin ve defter tutun."),
            ("⚙️ Ayarlar", "Bildirim seslerini, hava durumu konumunu, AI API anahtarlarını ayarlayın. Gerektiğinde sistemi sıfırlayın."),
            ("✨ Yapay Zeka Asistanı", "Sağ alt köşedeki yüzer buton ile asistanınıza ulaşın. Derslerinizi, notlarınızı ve programınızı ona sorun!"),
            ("📖 Kitaplığım", "Okuduğunuz, okuyacağınız ve şu an okumakta olduğunuz kitapları takip edin, PDF e-kitaplarınızı tek tıkla açın.")
        ]

        for icon_title, description in features:
            item_frame = QFrame()
            # Hover efekti kaldırıldı, sadece sade bir çerçeve bırakıldı
            item_frame.setStyleSheet("background-color: #1c1917; border: 1px solid #3f3f46; border-radius: 8px;")
            item_lay = QVBoxLayout(item_frame)
            item_lay.setContentsMargins(14, 12, 14, 12)
            item_lay.setSpacing(4)
            
            lbl_t = QLabel(icon_title)
            lbl_t.setStyleSheet("font-size: 14px; font-weight: bold; color: #7dd3fc;")
            
            lbl_d = QLabel(description)
            lbl_d.setStyleSheet("font-size: 12px; color: #d4d4d8;")
            lbl_d.setWordWrap(True)
            
            item_lay.addWidget(lbl_t)
            item_lay.addWidget(lbl_d)
            content_lay.addWidget(item_frame)

        scroll.setWidget(content)
        card_lay.addWidget(scroll)
        
        # Alt Kontroller
        bottom_lay = QHBoxLayout()
        
        self.chk_show_again = QCheckBox("Her açılışta göster")
        self.chk_show_again.setCursor(Qt.PointingHandCursor)
        self.chk_show_again.setStyleSheet("color: #e4e4e7; font-weight: bold; font-size: 13px;")
        
        show_setting = self.get_db_setting('show_welcome_on_startup', '1')
        self.chk_show_again.setChecked(show_setting == '1')
        self.chk_show_again.toggled.connect(self.toggle_startup_setting)
        
        btn_close = QPushButton("🚀 Uygulamaya Devam Et")
        btn_close.setCursor(Qt.PointingHandCursor)
        # Ekstra basılma (pressed) efektleri de kaldırılarak standart görünüme getirildi
        btn_close.setStyleSheet("""
            QPushButton { background-color: #3b82f6; color: white; border-radius: 8px; padding: 12px 20px; font-size: 14px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #2563eb; }
        """)
        btn_close.clicked.connect(self.accept)
        
        bottom_lay.addWidget(self.chk_show_again)
        bottom_lay.addStretch()
        bottom_lay.addWidget(btn_close)
        
        card_lay.addLayout(bottom_lay)
        
        # Kartı yarı saydam arkaya, yarı saydam arkayı da ana düzene ekliyoruz
        overlay_lay.addWidget(self.card)
        main_lay.addWidget(self.overlay_frame)

    # Diyalog ekrana çıkarken ana pencerenin tam boyutlarını alıp üzerine yapışır
    def showEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().geometry())
        super().showEvent(event)

    def get_db_setting(self, key, default='1'):
        try:
            with self.main_window.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,))
                row = cur.fetchone()
                return row[0] if row else default
        except:
            return default

    def toggle_startup_setting(self, checked):
        val = '1' if checked else '0'
        try:
            with self.main_window.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM app_settings WHERE setting_key = 'show_welcome_on_startup'")
                if cur.fetchone():
                    cur.execute("UPDATE app_settings SET setting_value = ? WHERE setting_key = 'show_welcome_on_startup'", (val,))
                else:
                    cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)", ('show_welcome_on_startup', val))
                conn.commit()
                
            if hasattr(self.main_window, 'settings_view'):
                if hasattr(self.main_window.settings_view, 'chk_welcome'):
                    self.main_window.settings_view.chk_welcome.blockSignals(True)
                    self.main_window.settings_view.chk_welcome.setChecked(checked)
                    self.main_window.settings_view.chk_welcome.blockSignals(False)
        except:
            pass

class NotificationPopup(QWidget):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        history = main_window.notification_log
        
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(360)
        
        frame = QFrame(self)
        frame.setStyleSheet("QFrame { background-color: #171412; border: 1px solid #3f3f46; border-radius: 8px; }")
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        
        header_widget = QWidget()
        header_lay = QHBoxLayout(header_widget)
        header_lay.setContentsMargins(16, 12, 16, 12)
        
        header = QLabel("📥 Son Bildirimler")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        
        btn_clear = QPushButton("🗑 Tümünü Sil")
        btn_clear.setCursor(QCursor(Qt.PointingHandCursor))
        btn_clear.setStyleSheet("""
            QPushButton { background-color: transparent; color: #f87171; font-size: 12px; font-weight: bold; border: none; }
            QPushButton:hover { color: #ef4444; text-decoration: underline; }
        """)
        btn_clear.clicked.connect(self.clear_history)
        
        header_lay.addWidget(header)
        header_lay.addStretch()
        if history:
            header_lay.addWidget(btn_clear)
            
        header_widget.setStyleSheet("border-bottom: 1px solid #292524;")
        lay.addWidget(header_widget)
        
        list_widget = QListWidget()
        list_widget.setWordWrap(True)
        list_widget.setStyleSheet("""
            QListWidget { background-color: transparent; border: none; outline: none; padding: 4px; }
            QListWidget::item { padding: 12px; border-bottom: 1px solid #1f1b18; border-radius: 6px; }
            QListWidget::item:hover { background-color: #1c1917; }
            QListWidget::item:selected { background-color: #27272a; }
        """)
        
        if not history:
            item = QListWidgetItem("Henüz bir bildirim yok.")
            item.setForeground(QColor("#71717a"))
            item.setTextAlignment(Qt.AlignCenter)
            list_widget.addItem(item)
        else:
            for time_str, t, m, c in history:
                item = QListWidgetItem(f"[{time_str}] {t}\n{m}")
                item.setForeground(QColor(c))
                list_widget.addItem(item)
                
        list_height = min(400, max(60, list_widget.count() * 65 + 10))
        list_widget.setFixedHeight(list_height)
        lay.addWidget(list_widget)

    def clear_history(self):
        self.main_window.notification_log.clear()
        self.main_window.btn_notif_history.setText("🔔 Bildirimler (0)")
        self.close()

class ToastNotification(QFrame):
    def __init__(self, parent, title, message, color="#38bdf8"):
        super().__init__(parent)
        self.setFixedSize(320, 85)
        self.setStyleSheet(f"""
            QFrame {{ background-color: #18181b; border-left: 5px solid {color}; border-top: 1px solid #27272a; border-right: 1px solid #27272a; border-bottom: 1px solid #27272a; border-radius: 6px; z-index: 9999; }}
            QLabel {{ background: transparent; border: none; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-weight: 800; color: {color}; font-size: 14px;")
        
        lbl_msg = QLabel(message)
        lbl_msg.setStyleSheet("color: #e4e4e7; font-size: 12px;")
        lbl_msg.setWordWrap(True)
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_msg)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.anim_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_in.setDuration(300)
        self.anim_in.setStartValue(0)
        self.anim_in.setEndValue(1)
        self.anim_in.setEasingCurve(QEasingCurve.OutQuad)
        
        self.anim_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_out.setDuration(400)
        self.anim_out.setStartValue(1)
        self.anim_out.setEndValue(0)
        self.anim_out.setEasingCurve(QEasingCurve.InQuad)
        self.anim_out.finished.connect(self.deleteLater)
        
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.anim_out.start)
        
    def show_toast(self):
        parent_rect = self.parent().rect()
        x = (parent_rect.width() - self.width()) // 2
        
        existing_toasts = [w for w in self.parent().children() if isinstance(w, ToastNotification) and w.isVisible() and w != self]
        y = 24 + (len(existing_toasts) * 95)
        
        self.move(x, y)
        self.show()
        self.raise_()
        self.anim_in.start()
        self.timer.start(5000)

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(440, 280)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)

        bg_frame = QFrame()
        bg_frame.setStyleSheet("QFrame { background-color: #000000; border: 1px solid #1e293b; border-radius: 12px; }")
        
        lay = QVBoxLayout(bg_frame)
        lay.setContentsMargins(30, 24, 30, 24)

        self.brand = QLabel("STUDENT LIFE OS")
        self.brand.setWordWrap(False)
        self.brand.setAlignment(Qt.AlignCenter)
        self.brand.setStyleSheet("font-size: 25px; font-weight: 900; letter-spacing: 2px; color: #38bdf8; border: none;")

        self.gif_label = QLabel()
        self.gif_label.setFixedSize(76, 76)
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.gif_label.setStyleSheet("background: transparent; border: none; padding: 0;")
        gif_path = os.path.join("resources", "icons", "splash.gif")
        if os.path.exists(gif_path):
            self.splash_movie = QMovie(gif_path)
            self.splash_movie.setScaledSize(QSize(112, 112))
            self.gif_label.setMovie(self.splash_movie)
            self.splash_movie.start()
        else:
            self.splash_movie = None
        
        version = QLabel("Başlatılıyor...")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color: #71717a; font-size: 11px; font-weight: bold; border: none;")

        self.info = QLabel("Sistem modülleri başlatılıyor...")
        self.info.setAlignment(Qt.AlignCenter)
        self.info.setStyleSheet("color: #a1a1aa; font-size: 11px; border: none; margin-top: 10px;")

        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar { background-color: #27272a; border-radius: 3px; border: none; } QProgressBar::chunk { background-color: #0284c7; border-radius: 3px; }")

        lay.addStretch()
        lay.addWidget(self.gif_label, alignment=Qt.AlignCenter)
        lay.addSpacing(8)
        lay.addWidget(self.brand)
        lay.addWidget(version)
        lay.addSpacing(20)
        lay.addWidget(self.progress)
        lay.addWidget(self.info)
        lay.addStretch()

        main_lay.addWidget(bg_frame)

        self.counter = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.loading)
        self.pulse = QPropertyAnimation(self.gif_label, b"windowOpacity", self)
        self.pulse.setDuration(900)
        self.pulse.setStartValue(0.72)
        self.pulse.setEndValue(1.0)
        self.pulse.setEasingCurve(QEasingCurve.InOutSine)
        self.pulse.setLoopCount(-1)

    def start(self, callback):
        self.callback = callback
        self.show()
        self.pulse.start()
        self.timer.start(15)

    def loading(self):
        self.counter += 1
        self.progress.setValue(self.counter)
        
        if self.counter == 30: self.info.setText("Veritabanı bağlantısı doğrulanıyor...")
        elif self.counter == 60: self.info.setText("Arka plan servisleri ve bildirimler ayarlanıyor...")
        elif self.counter == 85: self.info.setText("Arayüz hazırlanıyor...")

        if self.counter >= 100:
            self.timer.stop()
            self.pulse.stop()
            if self.splash_movie:
                self.splash_movie.stop()
            self.close()
            try:
                play_action_sound("startup")
            except: pass
            self.callback() 
class NetworkWorker(QThread):
    status_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.current_status = True

    def run(self):
        import time
        import socket
        while self.is_running:
            try:
                # 8.8.8.8 (Google DNS) adresine 2 saniyelik zaman aşımı ile hızlı ping atar
                socket.setdefaulttimeout(2)
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
                status = True
            except Exception:
                status = False

            # Durum değiştiğinde arayüze anında sinyal gönderir
            if status != self.current_status:
                self.current_status = status
                self.status_changed.emit(status)
            
            time.sleep(3) # Sistemi yormamak için her 3 saniyede bir kontrol eder

class SettingsView(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.app_name = "StudentLifeOS"
        self.main_window = main_window 
        self.sound_combos = []
        self.init_ui()

    def get_db_setting(self, key, default='1'):
        with self.main_window.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row else default

    def set_db_setting(self, key, value):
        with self.main_window.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM app_settings WHERE setting_key = ?", (key,))
            if cur.fetchone():
                cur.execute("UPDATE app_settings SET setting_value = ? WHERE setting_key = ?", (str(value), key))
            else:
                cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    def create_sound_row(self, label_text, setting_key):
        lay = QHBoxLayout()
        lay.setContentsMargins(8, 4, 0, 4)
        
        lbl = QLabel(label_text)
        lbl.setFixedWidth(200)
        lbl.setStyleSheet("font-weight: bold; color: #e4e4e7;")
        
        cb = QComboBox()
        cb.setStyleSheet("background-color: #27272a; padding: 6px; border-radius: 4px; color: white;")
        cb.addItem("Varsayılan (Windows)")
        
        if os.path.exists(SOUNDS_DIR):
            for f in os.listdir(SOUNDS_DIR):
                if f.endswith(".wav"):
                    cb.addItem(f)
                    
        current_sound = self.get_db_setting(setting_key)
        if not current_sound:
            current_sound = "Varsayılan (Windows)"
            self.set_db_setting(setting_key, current_sound)
            
        index = cb.findText(current_sound)
        if index >= 0:
            cb.setCurrentIndex(index)
            
        cb.currentTextChanged.connect(lambda text, k=setting_key: self.set_db_setting(k, text))
        self.sound_combos.append(cb)
        
        btn_preview = QPushButton("▶ Dinle")
        btn_preview.setCursor(QCursor(Qt.PointingHandCursor))
        btn_preview.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; border-radius: 4px; padding: 6px 12px;")
        btn_preview.clicked.connect(lambda _, box=cb: self.preview_sound(box.currentText()))

        lay.addWidget(lbl)
        lay.addWidget(cb)
        lay.addWidget(btn_preview)
        lay.addStretch()
        return lay

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(20)

        title = QLabel("⚙️ Sistem ve Uygulama Ayarları")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        lay.addWidget(title)

        # Yalnızca Gemini API kutusu
        ai_card = QFrame()
        ai_card.setObjectName("Card")
        a_lay = QVBoxLayout(ai_card)
        
        lbl_ai_title = QLabel("✨ Yapay Zeka API Ayarları")
        lbl_ai_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #3b82f6; margin-bottom: 4px;")
        a_lay.addWidget(lbl_ai_title)
        
        lbl_ai_desc = QLabel("Google AI Studio'dan aldığınız Gemini API Anahtarını girin:")
        lbl_ai_desc.setStyleSheet("color: #a1a1aa; font-size: 11px; margin-bottom: 8px;")
        a_lay.addWidget(lbl_ai_desc)
        
        self.gemini_input = QLineEdit(self.get_db_setting('gemini_api_key', default=""))
        self.gemini_input.setPlaceholderText("Google Gemini API Anahtarı...")
        self.gemini_input.setEchoMode(QLineEdit.Password)
        self.gemini_input.setStyleSheet("background-color: #27272a; border-radius: 6px; padding: 8px; color: white; font-size: 12px; border: 1px solid #3f3f46;")
        a_lay.addWidget(self.gemini_input)
        
        btn_save_api = QPushButton("Anahtarı Kaydet")
        btn_save_api.setCursor(QCursor(Qt.PointingHandCursor))
        btn_save_api.setStyleSheet("background-color: #3b82f6; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold; margin-top: 8px;")
        btn_save_api.clicked.connect(self.save_api_key) # Kaydetme metoduna bağlayın
        a_lay.addWidget(btn_save_api)
        
        lay.addWidget(ai_card)

        notif_card = QFrame()
        notif_card.setObjectName("Card")
        n_lay = QVBoxLayout(notif_card)
        n_lay.setSpacing(12)

        lbl_notif_title = QLabel("🔔 Bildirim ve Ses Tercihleri")
        lbl_notif_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #38bdf8; margin-bottom: 4px;")
        n_lay.addWidget(lbl_notif_title)

        self.chk_welcome = QCheckBox("Uygulama açılışında Tanıtım Ekranını göster")
        self.chk_welcome.setStyleSheet("font-size: 13px; font-weight: bold; color: #e4e4e7; margin-bottom: 8px;")
        self.chk_welcome.setChecked(self.get_db_setting('show_welcome_on_startup', '1') == '1')
        self.chk_welcome.toggled.connect(lambda checked: self.set_db_setting('show_welcome_on_startup', '1' if checked else '0'))
        n_lay.addWidget(self.chk_welcome)

        self.btn_notif = QPushButton()
        self.btn_notif.setCheckable(True)
        self.btn_notif.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_notif.setFixedHeight(45)
        self.btn_notif.setStyleSheet("""
            QPushButton { background-color: #27272a; color: #a1a1aa; border: 2px solid #3f3f46; border-radius: 8px; font-weight: bold; font-size: 14px; text-align: left; padding-left: 16px; }
            QPushButton:hover { background-color: #3f3f46; }
            QPushButton:checked { background-color: #0284c7; color: #ffffff; border: 2px solid #0369a1; }
        """)

        is_global_notif = (self.get_db_setting('notif_global') == '1')
        self.btn_notif.setChecked(is_global_notif)
        self.update_notif_btn_text(is_global_notif)
        self.btn_notif.toggled.connect(self.toggle_global_notif)
        n_lay.addWidget(self.btn_notif)

        class_lay = QHBoxLayout()
        class_lay.setContentsMargins(8, 0, 0, 0)
        self.chk_classes = QCheckBox("Ders Başlangıç Hatırlatıcısı")
        self.chk_classes.setStyleSheet("font-size: 13px; font-weight: bold; color: #e4e4e7;")
        self.chk_classes.setChecked(self.get_db_setting('notif_classes') == '1')
        self.chk_classes.toggled.connect(lambda checked: self.set_db_setting('notif_classes', '1' if checked else '0'))
        
        self.cb_class_time = QComboBox()
        self.cb_class_time.addItems(["5", "10", "15", "30", "45", "60"])
        self.cb_class_time.setCurrentText(self.get_db_setting('notif_classes_time', '15'))
        self.cb_class_time.setStyleSheet("background-color: #27272a; padding: 4px; border-radius: 4px; color: white;")
        self.cb_class_time.currentTextChanged.connect(lambda text: self.set_db_setting('notif_classes_time', text))
        
        class_lay.addWidget(self.chk_classes)
        class_lay.addWidget(self.cb_class_time)
        lbl_class_suffix = QLabel("Dk. Önce Uyarı Ver")
        lbl_class_suffix.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        class_lay.addWidget(lbl_class_suffix)
        class_lay.addStretch()
        n_lay.addLayout(class_lay)

        plan_lay = QHBoxLayout()
        plan_lay.setContentsMargins(8, 0, 0, 0)
        self.chk_plans = QCheckBox("Kişisel Plan Hatırlatıcısı")
        self.chk_plans.setStyleSheet("font-size: 13px; font-weight: bold; color: #e4e4e7;")
        self.chk_plans.setChecked(self.get_db_setting('notif_plans') == '1')
        self.chk_plans.toggled.connect(lambda checked: self.set_db_setting('notif_plans', '1' if checked else '0'))
        
        self.cb_plan_time = QComboBox()
        self.cb_plan_time.addItems(["5", "10", "15", "30", "45", "60"])
        self.cb_plan_time.setCurrentText(self.get_db_setting('notif_plans_time', '15'))
        self.cb_plan_time.setStyleSheet("background-color: #27272a; padding: 4px; border-radius: 4px; color: white;")
        self.cb_plan_time.currentTextChanged.connect(lambda text: self.set_db_setting('notif_plans_time', text))
        
        plan_lay.addWidget(self.chk_plans)
        plan_lay.addWidget(self.cb_plan_time)
        lbl_plan_suffix = QLabel("Dk. Önce Uyarı Ver")
        lbl_plan_suffix.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        plan_lay.addWidget(lbl_plan_suffix)
        plan_lay.addStretch()
        n_lay.addLayout(plan_lay)
        
        n_lay.addSpacing(10)
        n_lay.addLayout(self.create_sound_row("🎓 Ders Bildirim Sesi:", "sound_classes"))
        n_lay.addLayout(self.create_sound_row("⏰ Plan Bildirim Sesi:", "sound_plans"))
        n_lay.addLayout(self.create_sound_row("🍅 Odak Sayacı (Pomodoro):", "sound_pomodoro"))

        self.toggle_sub_notifs(is_global_notif)
        lay.addWidget(notif_card)

        # --- HAVA DURUMU AYAR KARTI ---
        weather_card = QFrame()
        weather_card.setObjectName("Card")
        w_lay = QVBoxLayout(weather_card)
        
        lbl_w_title = QLabel("🌤️ Hava Durumu Seçenekleri")
        lbl_w_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        w_lay.addWidget(lbl_w_title)

        self.chk_weather = QCheckBox("Kontrol Panelinde Hava Durumunu Göster")
        self.chk_weather.setStyleSheet("color: white; font-weight: bold;")
        self.chk_weather.setChecked(self.get_db_setting('weather_enabled', '1') == '1')
        
        # 81 İli barındıran hazır liste
        cities = [
            "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın", "Balıkesir",
            "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli",
            "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari",
            "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir",
            "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir",
            "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat",
            "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman",
            "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce"
        ]

        self.city_combo = QComboBox()
        self.city_combo.addItems(cities)
        self.city_combo.setStyleSheet("background-color: #27272a; border-radius: 6px; padding: 8px; color: white; border: 1px solid #3f3f46;")
        
        # Kayıtlı şehri yükle
        curr_city = self.get_db_setting('weather_city', 'İstanbul')
        if curr_city in ('1', '', 'Otomatik Konum'):
            curr_city = 'İstanbul'
            self.set_db_setting('weather_city', curr_city)
        self.city_combo.setCurrentText(curr_city)

        btn_save_w = QPushButton("Kaydet")
        btn_save_w.setCursor(QCursor(Qt.PointingHandCursor))
        # Tıklama hissiyatı için :pressed durumuna margin/padding kaydırması eklendi
        btn_save_w.setStyleSheet("""
            QPushButton { 
                background-color: #3b82f6; 
                color: white; 
                border-radius: 6px; 
                padding: 10px; 
                font-weight: bold; 
            }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:pressed { 
                background-color: #1d4ed8; 
                padding-top: 12px; 
                padding-bottom: 8px; 
            }
        """)
        
        def save_w():
            # 1. Veritabanı güncellemeleri
            self.set_db_setting('weather_enabled', '1' if self.chk_weather.isChecked() else '0')
            self.set_db_setting('weather_city', self.city_combo.currentText())
            
            # 2. Kontrol Panelini Anında Yenileme
            if hasattr(self.main_window, 'dashboard_view'):
                dash = self.main_window.dashboard_view
                dash.lbl_weather.setText("📍 Yeni konum hava durumu yükleniyor...")
                
                # Eski thread'i UI'dan kopar (Silinmiş C++ objesi hatasını engellemek için try-except kullanıyoruz)
                if hasattr(dash, 'weather_worker'):
                    try:
                        if dash.weather_worker and dash.weather_worker.isRunning():
                            dash.weather_worker.result_ready.disconnect()
                    except RuntimeError:
                        # İş parçacığı zaten kendini imha etmişse hatayı sessizce geç
                        pass
                    except Exception:
                        pass
                        
                    # Yeni isteğin takılmaması için referansı temizle
                    try: del dash.weather_worker
                    except AttributeError: pass
                
                # Sıfırdan taze hava durumu çek
                dash.fetch_weather()
            
            # 3. Kayıt Sesi Çalma
            try:
                from core.sound import play_action_sound
                play_action_sound("save")
            except Exception:
                pass

            # 4. Şık Bildirim Baloncuğu
            if hasattr(self.main_window, 'send_tray_notification'):
                self.main_window.send_tray_notification(
                    "💾 Konum Kaydedildi", 
                    f"Hava durumu konumu '{self.city_combo.currentText()}' olarak güncellendi ve Kontrol Paneline yansıtıldı.", 
                    color="#10b981"
                )
            
        btn_save_w.clicked.connect(save_w)

        w_lay.addWidget(self.chk_weather)
        w_lay.addWidget(self.city_combo)
        w_lay.addWidget(btn_save_w)
        lay.addWidget(weather_card)

        creator_card = QFrame()
        creator_card.setObjectName("Card")
        creator_card.setStyleSheet("#Card { border: 1px solid #3f3f46; }")
        cr_lay = QVBoxLayout(creator_card)
        
        lbl_cr_title = QLabel("👨‍💻 Kurucu ve Geliştirici")
        lbl_cr_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #a8a29e; margin-bottom: 8px;")
        cr_lay.addWidget(lbl_cr_title)
        
        lbl_cr_name = QLabel("Furkan Yıldırım")
        lbl_cr_name.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        cr_lay.addWidget(lbl_cr_name)

        cr_links_lay = QHBoxLayout()
        
        btn_linkedin = QPushButton("🔗 LinkedIn")
        btn_linkedin.setCursor(QCursor(Qt.PointingHandCursor))
        btn_linkedin.setStyleSheet("""
            QPushButton { background-color: #0077b5; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #005582; }
        """)
        btn_linkedin.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.linkedin.com/in/furkan-y-8874631b1/")))

        btn_github = QPushButton("🐙 GitHub")
        btn_github.setCursor(QCursor(Qt.PointingHandCursor))
        btn_github.setStyleSheet("""
            QPushButton { background-color: #24292e; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #111416; }
        """)
        btn_github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/furkiyildirim")))

        cr_links_lay.addWidget(btn_linkedin)
        cr_links_lay.addWidget(btn_github)
        cr_links_lay.addStretch()
        cr_lay.addLayout(cr_links_lay)
        lay.addWidget(creator_card)

        danger_card = QFrame()
        danger_card.setObjectName("Card")
        danger_card.setStyleSheet("#Card { border: 1px solid #7f1d1d; }")
        d_lay = QVBoxLayout(danger_card)
        
        lbl_danger_title = QLabel("⚠️ Tehlikeli Bölge")
        lbl_danger_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f87171; margin-bottom: 4px;")
        d_lay.addWidget(lbl_danger_title)
        
        btn_reset = QPushButton("🗑 Tüm Sistemi Sıfırla (Her Şeyi Sil)")
        btn_reset.setCursor(QCursor(Qt.PointingHandCursor))
        btn_reset.setStyleSheet("background-color: #7f1d1d; color: white; border-radius: 6px; padding: 10px; font-weight: bold;")
        btn_reset.clicked.connect(self.perform_factory_reset)
        d_lay.addWidget(btn_reset)
        
        lay.addWidget(danger_card)
        lay.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def save_api_key(self):
        self.set_db_setting('gemini_api_key', self.gemini_input.text().strip())
        from core.events import bus
        bus.ai_settings_changed.emit()
        QMessageBox.information(self, "Başarılı", "API Anahtarı başarıyla kaydedildi.")

    def preview_sound(self, sound_val):
        try:
            import winsound
            if sound_val and sound_val != "Varsayılan (Windows)":
                path = os.path.join(SOUNDS_DIR, sound_val)
                if os.path.exists(path):
                    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception: pass

    def update_notif_btn_text(self, checked: bool):
        if checked: self.btn_notif.setText("🔔 Sistem Bildirimleri: AÇIK")
        else: self.btn_notif.setText("🔕 Sistem Bildirimleri: KAPALI")

    def toggle_global_notif(self, checked: bool):
        self.update_notif_btn_text(checked)
        self.set_db_setting('notif_global', '1' if checked else '0')
        self.toggle_sub_notifs(checked)

    def toggle_sub_notifs(self, enabled: bool):
        self.chk_classes.setEnabled(enabled)
        self.cb_class_time.setEnabled(enabled)
        self.chk_plans.setEnabled(enabled)
        self.cb_plan_time.setEnabled(enabled)
        for cb in self.sound_combos:
            cb.setEnabled(enabled)

    def logout_web_profiles(self):
        main_window = self.main_window
        active_profiles = []

        for view, profile_names in (
            (main_window, ("yt_profile",)),
            (getattr(main_window, "university_view", None), ("obs_profile", "mail_profile")),
        ):
            if view:
                for profile_name in profile_names:
                    profile = getattr(view, profile_name, None)
                    if profile:
                        active_profiles.append(profile)

        for profile in active_profiles:
            profile.cookieStore().deleteAllCookies()
            profile.clearHttpCache()
            profile.clearAllVisitedLinks()

        for view, webview_names in (
            (main_window, ("yt_webview",)),
            (getattr(main_window, "university_view", None), ("obs_webview", "mail_webview")),
        ):
            if view:
                for webview_name in webview_names:
                    webview = getattr(view, webview_name, None)
                    if webview:
                        webview.setUrl(QUrl("about:blank"))

        profiles_dir = os.path.join(os.getcwd(), "vault_storage")
        if os.path.isdir(profiles_dir):
            for entry in os.listdir(profiles_dir):
                if entry.endswith("_profile"):
                    shutil.rmtree(os.path.join(profiles_dir, entry), ignore_errors=True)

    def perform_factory_reset(self):
        from PySide6.QtWidgets import QMessageBox, QInputDialog
        import shutil
        import os
        from PySide6.QtCore import QUrl
        
        # --- 1. AŞAMA: YAZILI ONAY (GÜVENLİK KONTROLÜ) ---
        text, ok = QInputDialog.getText(
            self, 
            "⚠️ SİSTEM SIFIRLAMA ONAYI", 
            "Tüm verileriniz (dersler, notlar, projeler, kitaplar, materyaller ve ayarlar) kalıcı olarak silinecek.\nBu işlem GERİ ALINAMAZ!\n\n"
            "İşlemi onaylamak için aşağıdaki kutuya büyük harflerle 'SİL' yazın:"
        )
        
        # Eğer kullanıcı "SİL" yazmadıysa veya İptal'e bastıysa işlemi durdur
        if not ok or text.strip() != "SİL":
            if ok: # Kullanıcı giriş yaptı ama kelimeyi yanlış yazdıysa
                QMessageBox.warning(self, "İptal Edildi", "Onay metni hatalı girildi. Sistem sıfırlama işlemi durduruldu.")
            return

        # --- 2. AŞAMA: SİLME İŞLEMLERİ ---
        tables_to_clear = [
            "todo_tasks", "calendar_events", "calendar_completions", 
            "timetable", "courses", "assessments", "notes", 
            "materials", "habits", "habit_logs", "workout_exercises",
            "projects", "project_tasks", "books"
        ]
        
        try:
            # 1. Veritabanı Temizliği
            with self.main_window.db.get_connection() as conn:
                cur = conn.cursor()
                for table in tables_to_clear:
                    try:
                        cur.execute(f"DELETE FROM {table}")
                    except: pass
                conn.commit()
            
            # 2. TÜM WEB TARAYICI OTURUMLARINI KAPAT (Derin Temizlik)
            def force_logout_webview(webview, profile):
                if webview and profile:
                    profile.cookieStore().deleteAllCookies()
                    profile.clearHttpCache()
                    webview.page().runJavaScript("window.localStorage.clear(); window.sessionStorage.clear();")
                    webview.setUrl(QUrl(webview.url().toString()))

            try:
                if hasattr(self.main_window, 'yt_profile'):
                    force_logout_webview(self.main_window.yt_webview, self.main_window.yt_profile)
                
                if hasattr(self.main_window, 'vault_view') and hasattr(self.main_window.vault_view, 'drive_profile'):
                    force_logout_webview(self.main_window.vault_view.drive_webview, self.main_window.vault_view.drive_profile)
                    
                if hasattr(self.main_window, 'university_view'):
                    if hasattr(self.main_window.university_view, 'obs_profile'):
                        force_logout_webview(self.main_window.university_view.obs_webview, self.main_window.university_view.obs_profile)
                    if hasattr(self.main_window.university_view, 'mail_profile'):
                        force_logout_webview(self.main_window.university_view.mail_webview, self.main_window.university_view.mail_profile)
            except Exception as e:
                print(f"Oturumlar kapatılırken hata: {e}")

            # 3. Fiziksel Dosyaları Temizle (vault_storage VE covers)
            for directory in ["vault_storage", os.path.join("resources", "covers")]:
                if os.path.exists(directory):
                    for filename in os.listdir(directory):
                        file_path = os.path.join(directory, filename)
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception: pass
                        
            # 4. Arayüzü ve Bildirimleri Sıfırla
            self.main_window.notification_log.clear()
            self.main_window.btn_notif_history.setText("🔔 Bildirimler (0)")

            try:
                from core.sound import play_action_sound
                play_action_sound("delete")
            except: pass

            from core.events import bus
            bus.habits_changed.emit()
            bus.workouts_changed.emit()
            bus.courses_changed.emit()
            bus.assessments_changed.emit()
            bus.notes_changed.emit()
            bus.calendar_changed.emit()
            
            # 5. Tüm Ekranları Yenile
            if hasattr(self.main_window, 'todo_view'):
                self.main_window.todo_view.load_tasks()
            if hasattr(self.main_window, 'fitness_view'):
                self.main_window.fitness_view.load_habits()
                self.main_window.fitness_view.load_workouts_for_day()
            if hasattr(self.main_window, 'timetable_view'):
                self.main_window.timetable_view.load_schedule()
                self.main_window.timetable_view.load_assessments()
            if hasattr(self.main_window, 'vault_view'):
                self.main_window.vault_view.load_notes()
                self.main_window.vault_view.load_materials()
            if hasattr(self.main_window, 'calendar_view'):
                self.main_window.calendar_view.refresh_calendar()
            if hasattr(self.main_window, 'project_view'):
                self.main_window.project_view.new_project()
                self.main_window.project_view.enable_right_panel(False)
                self.main_window.project_view.load_projects()
            if hasattr(self.main_window, 'library_view'):
                self.main_window.library_view.load_books()
                
            QMessageBox.information(self, "Başarılı", "Sistem başarıyla sıfırlandı. Tüm hesaplardan güvenli bir şekilde çıkış yapıldı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sıfırlama sırasında bir hata oluştu:\n{e}")

class MainWindow(QMainWindow):
    def __init__(self, start_hidden=False):
        super().__init__()
        self.setWindowTitle("Student Life OS")
        
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            self.resize(int(geom.width() * 0.85), int(geom.height() * 0.85))
        else:
            self.resize(1280, 820)
            
        self.setMinimumSize(1020, 700)

        if os.name == 'nt':
            try:
                hwnd = self.winId().__int__()
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(ctypes.c_int(2)),
                    ctypes.sizeof(ctypes.c_int)
                )
            except Exception: pass

        icon_path = "resources/icons/icon.ico" if os.path.exists("resources/icons/icon.ico") else "icon.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.history = []
        self.history_index = -1
        self.is_navigating_history = False
        self.is_sidebar_expanded = True
        
        self.notified_events = set()
        self.notification_log = [] 
        
        self.app_started_time = datetime.now()
        self.notif_queue = []
        self.notif_processing = False

        self.db = DatabaseManager()
        self.setup_database_settings() 
        self.setup_global_yt_player()
        self.setup_system_tray() 
        self.init_ui()
        self.style_open_menus()
        QApplication.instance().installEventFilter(self)
        self.setup_event_listeners()
        self.setup_background_timer()

        # --- ARKA PLANDAN UYANMA SİNYALİ DİNLEYİCİSİ ---
        self.wakeup_file = os.path.join(tempfile.gettempdir(), "student_os_wakeup.txt")
        if os.path.exists(self.wakeup_file):
            try: os.remove(self.wakeup_file)
            except: pass
            
        self.wakeup_timer = QTimer(self)
        self.wakeup_timer.timeout.connect(self.check_wakeup)
        self.wakeup_timer.start(500) # Saniyede 2 kez uyanma komutu var mı diye kontrol eder
    def style_open_menus(self):
        """Açılır seçimleri bulundukları ekranın vurgu rengiyle stillendir."""
        menu_colors = {
            "UniversityView": ("#075985", "#38bdf8", "#e0f2fe"),
            "ProjectView": ("#155e75", "#22d3ee", "#cffafe"),
            "TimetableView": ("#6d28d9", "#a78bfa", "#ede9fe"),
            "CalendarView": ("#166534", "#4ade80", "#dcfce7"),
            "FitnessView": ("#166534", "#4ade80", "#dcfce7"),
            "MusicView": ("#166534", "#4ade80", "#dcfce7"),
            "AIChatWindow": ("#075985", "#38bdf8", "#e0f2fe"),
            "SettingsView": ("#1d4ed8", "#60a5fa", "#dbeafe"),
            "TodoView": ("#075985", "#60a5fa", "#dbeafe"),
            "VaultView": ("#0e7490", "#22d3ee", "#cffafe"),
        }

        for combo in self.findChildren(QComboBox):
            combo.installEventFilter(self)
            color_key = "SettingsView"
            parent = combo.parentWidget()
            while parent:
                class_name = parent.__class__.__name__
                if class_name in menu_colors:
                    color_key = class_name
                    break
                parent = parent.parentWidget()

            background, border, selection = menu_colors[color_key]
            combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: rgba(39, 39, 42, 185);
                    color: #ffffff;
                    border: 1px solid {border};
                    border-radius: 7px;
                    padding: 6px 10px;
                    font-weight: 700;
                }}
                QComboBox:hover {{ border: 2px solid {border}; }}
                QComboBox::drop-down {{ width: 28px; border: none; background: transparent; }}
                QComboBox QAbstractItemView {{
                    background-color: rgba(24, 24, 27, 238);
                    color: #f4f4f5;
                    border: 1px solid {border};
                    selection-background-color: {selection};
                    selection-color: #0c0a09;
                    padding: 4px;
                }}
            """)

    def eventFilter(self, watched, event):
        if isinstance(watched, QComboBox) and watched.isEnabled() and event.type() == QEvent.MouseButtonPress:
            watched.showPopup()
            return True
        return super().eventFilter(watched, event)

    def setup_global_yt_player(self):
        self.yt_webview = QWebEngineView()
        self.yt_webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        profile_path = os.path.join(os.getcwd(), "vault_storage", "ytmusic_profile")
        if not os.path.exists(profile_path):
            os.makedirs(profile_path)
            
        self.yt_profile = QWebEngineProfile("YTMusicProfile", self.yt_webview)
        self.yt_profile.setPersistentStoragePath(profile_path)
        self.yt_profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        
        settings = self.yt_profile.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        
        self.yt_page = QWebEnginePage(self.yt_profile, self.yt_webview)
        self.yt_webview.setPage(self.yt_page)
        self.yt_webview.setUrl(QUrl("https://music.youtube.com/"))

    def setup_database_settings(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT
                )
            """)
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('notif_global', '1')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('notif_classes', '1')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('notif_classes_time', '15')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('notif_plans', '1')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('notif_plans_time', '15')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('semester_start_date', '')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('semester_end_date', '')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('sound_classes', 'Varsayılan (Windows)')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('sound_plans', 'Varsayılan (Windows)')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('sound_pomodoro', 'Varsayılan (Windows)')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('weather_enabled', '1')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('weather_city', 'İstanbul')")
            cur.execute("UPDATE app_settings SET setting_value = 'İstanbul' WHERE setting_key = 'weather_city' AND setting_value IN ('1', '', 'Otomatik Konum')")
            cur.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('show_welcome_on_startup', '1')")
            conn.commit()

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = "resources/icons/icon.ico" if os.path.exists("resources/icons/icon.ico") else "icon.ico"
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        
        tray_menu = QMenu()
        show_action = QAction("📌 Arayüzü Göster", self)
        show_action.triggered.connect(self.show_and_activate)
        quit_action = QAction("🚪 Tamamen Kapat", self)
        quit_action.triggered.connect(QApplication.quit)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def show_and_activate(self):
        self.showMaximized()
        self.raise_()
        self.activateWindow()

        self.check_welcome_screen()
        if not hasattr(self, '_welcome_shown'):
            self._welcome_shown = True

            QTimer.singleShot(1500, lambda: self.send_tray_notification(
                "Sistem Aktif 🚀", 
                "Öğrenci Asistanı başarıyla başlatıldı. Verimli bir gün dileriz!", 
                color="#38bdf8"
            ))
            
            now = datetime.now()
            today_iso = now.date().isoformat()

            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM todo_tasks WHERE is_completed = 0")
                todo_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM calendar_events WHERE event_date = ? AND is_completed = 0", (today_iso,))
                plan_count = cur.fetchone()[0]

            if 6 <= now.hour < 16:
                title = "Güne Başlarken ☀️"
                msg = f"Günaydın! Bugün seni bekleyen {todo_count} görev ve {plan_count} plan var. Verimli bir gün dileriz!"
                color = "#10b981"
                self.notified_events.add(f"morning_{today_iso}") 
            elif 16 <= now.hour < 23:
                title = "Gün Sonu Özeti 🌙"
                msg = f"İyi akşamlar! Bugün tamamlanmamış {todo_count} görevin ve {plan_count} planın kaldı. Göz atmak ister misin?"
                color = "#f59e0b"
                self.notified_events.add(f"eod_{today_iso}") 
            else:
                title = "Sistem Aktif 🚀"
                msg = "Öğrenci Asistanı başarıyla başlatıldı. Çalışmalarında kolaylıklar dileriz!"
                color = "#38bdf8"

            QTimer.singleShot(10000, lambda: self.send_tray_notification(title, msg, color=color, sound_key="sound_plans"))

    def check_wakeup(self):
            # Eğer 2. uygulama bir uyanma dosyası oluşturduysa onu algıla
            if os.path.exists(self.wakeup_file):
                try:
                    os.remove(self.wakeup_file) # Sinyali temizle
                except OSError:
                    pass
                
                # Uygulamayı Qt'nin güvenli yöntemiyle TAM EKRAN olarak öne getir
                self.show_and_activate()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_and_activate()

    def closeEvent(self, event):
        event.ignore()
        self.send_to_background()

    def send_to_background(self):
        self.hide()

    def send_tray_notification(self, title, message, color="#38bdf8", sound_key=None):
        time_str = datetime.now().strftime("%H:%M")
        self.notification_log.insert(0, (time_str, title, message, color))
        if len(self.notification_log) > 20: 
            self.notification_log.pop()
            
        self.btn_notif_history.setText(f"🔔 Bildirimler ({len(self.notification_log)})")

        self.notif_queue.append((title, message, color, sound_key))
        
        if not self.notif_processing:
            self.process_next_notif()

    def process_next_notif(self):
        if not self.notif_queue:
            self.notif_processing = False
            return
            
        self.notif_processing = True
        title, message, color, sound_key = self.notif_queue.pop(0)

        try:
            import winsound
            sound_val = None
            if sound_key:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (sound_key,))
                    row = cur.fetchone()
                    if row and row[0] != "Varsayılan (Windows)":
                        sound_val = row[0]
            
            if sound_val:
                path = os.path.join(SOUNDS_DIR, sound_val)
                if os.path.exists(path):
                    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except: pass

        if self.isVisible():
            toast = ToastNotification(self, title, message, color)
            toast.show_toast()

        QTimer.singleShot(4500, self.process_next_notif)

    def show_notif_history(self):
        self.notif_popup = NotificationPopup(self)
        rect = self.btn_notif_history.rect()
        bottom_right = self.btn_notif_history.mapToGlobal(rect.bottomRight())
        self.notif_popup.move(bottom_right.x() - self.notif_popup.width(), bottom_right.y() + 4)
        self.notif_popup.show()

    def setup_background_timer(self):
        self.notif_timer = QTimer(self)
        self.notif_timer.timeout.connect(self.check_upcoming_events)
        self.notif_timer.start(60000)
        self.check_upcoming_events()

    def check_upcoming_events(self):
        now = datetime.now()

        # İlk 15 saniye boyunca arka plandan gelen hiçbir bildirime izin verme
        if not hasattr(self, 'app_started_time'):
            self.app_started_time = now
            
        if (now - self.app_started_time).total_seconds() < 15:
            return

        # Gece 23:00 ile Sabah 06:00 arasında rahatsız etme modu (sessiz saatler)
        if now.hour >= 23 or now.hour < 6:
            return

        today_iso = now.date().isoformat()
        today_date = now.date()
        today_dow = now.weekday()

        with self.db.get_connection() as conn:
            cur = conn.cursor()

            # --- YENİ: DÖNEM BAŞLANGICI BİLDİRİMİ (Günde 1 Kez) ---
            sem_id = f"semester_start_{today_iso}"
            if sem_id not in self.notified_events:
                try:
                    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'semester_start_date'")
                    row = cur.fetchone()
                    if row and row[0] and row[0] != "0001-01-01":
                        s_date = datetime.strptime(row[0], "%Y-%m-%d").date()
                        rem_days = (s_date - today_date).days
                        
                        if rem_days == 0:
                            self.send_tray_notification("Yeni Dönem Başlıyor! 🎓", "Akademik dönem bugün resmen başladı. Harika bir dönem dileriz!", color="#38bdf8")
                        elif rem_days in [1, 3]:
                            self.send_tray_notification("Dönem Yaklaşıyor ⏳", f"Yeni dönemin başlamasına son {rem_days} gün kaldı. Hazırlıklarını gözden geçir!", color="#f59e0b")
                except Exception: pass
                self.notified_events.add(sem_id)

            # --- YENİ: ÖDÜNÇ KİTAP İADE BİLDİRİMİ (Günde 1 Kez) ---
            books_id = f"books_return_{today_iso}"
            if books_id not in self.notified_events:
                try:
                    cur.execute("SELECT id, title, return_date, return_location FROM books WHERE is_borrowed = 1")
                    for b in cur.fetchall():
                        if not b["return_date"]: continue
                        r_date = datetime.strptime(b["return_date"], "%d.%m.%Y").date()
                        rem_days = (r_date - today_date).days
                        
                        if rem_days == 0:
                            self.send_tray_notification("Kitap İade Günü! 📚", f"'{b['title']}' adlı kitabı BUGÜN teslim etmelisin!\n📍 Konum: {b['return_location']}", color="#ef4444")
                        elif rem_days == 2:
                            self.send_tray_notification("Kitap İadesi Yaklaşıyor ⏳", f"'{b['title']}' kitabını iade etmene son 2 gün kaldı.\n📍 Konum: {b['return_location']}", color="#f59e0b")
                except Exception: pass
                self.notified_events.add(books_id)

            # --- GÜN İÇİ TO-DO ÖZETLERİ (06:00 ile 16:00 Arası) ---
            if 6 <= now.hour < 16:
                morning_id = f"morning_{today_iso}"
                if morning_id not in self.notified_events:
                    cur.execute("SELECT COUNT(*) FROM todo_tasks WHERE is_completed = 0")
                    todo_count = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM calendar_events WHERE event_date = ? AND is_completed = 0", (today_iso,))
                    plan_count = cur.fetchone()[0]
                        
                    if todo_count > 0 or plan_count > 0:
                        self.send_tray_notification("Güne Başlarken ☀️", f"Bugün yapman gereken {todo_count} görev ve {plan_count} plan seni bekliyor. Listeni kontrol etmeyi unutma!", color="#10b981", sound_key="sound_plans")
                    self.notified_events.add(morning_id)

            # --- AKŞAM ÖZETİ (16:00 ile 23:00 Arası) ---
            elif 16 <= now.hour < 23:
                eod_id = f"eod_{today_iso}"
                if eod_id not in self.notified_events:
                    cur.execute("SELECT COUNT(*) FROM todo_tasks WHERE is_completed = 0")
                    todo_count = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM calendar_events WHERE event_date = ? AND is_completed = 0", (today_iso,))
                    plan_count = cur.fetchone()[0]
                        
                    if todo_count > 0 or plan_count > 0:
                        self.send_tray_notification("Gün Sonu Özeti 🌙", f"Bugün tamamlanmamış {todo_count} görevin ve {plan_count} planın var. Göz atmak ister misin?", color="#f59e0b", sound_key="sound_plans")
                    self.notified_events.add(eod_id)

            # --- DERS VE KİŞİSEL PLAN HATIRLATICILARI ---
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'notif_global'")
            if cur.fetchone()[0] == '0': return
            
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'notif_classes'")
            notify_classes = cur.fetchone()[0] == '1'
            
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'notif_plans'")
            notify_plans = cur.fetchone()[0] == '1'

            if notify_classes:
                cur.execute("""
                    SELECT c.code, c.name, t.start_time, c.classroom 
                    FROM timetable t 
                    JOIN courses c ON t.course_id = c.id 
                    WHERE t.day_of_week = ?
                """, (today_dow,))
                for r in cur.fetchall():
                    try:
                        event_time = datetime.strptime(f"{today_iso} {r['start_time']}", "%Y-%m-%d %H:%M")
                        delta_mins = (event_time - now).total_seconds() / 60.0
                        if 0 <= delta_mins <= 15:
                            notif_id = f"class_{r['code']}_{today_iso}_{r['start_time']}"
                            if notif_id not in self.notified_events:
                                self.send_tray_notification(
                                    "Ders Başlıyor 🎓", 
                                    f"{r['code']} - {r['name']} yakında ({r['start_time']}) başlıyor!\nDerslik: {r['classroom']}",
                                    color="#f43f5e",
                                    sound_key="sound_classes"
                                )
                                self.notified_events.add(notif_id)
                    except Exception: pass

            if notify_plans:
                cur.execute("""
                    SELECT id, title, start_time, category 
                    FROM calendar_events 
                    WHERE event_date = ? AND is_completed = 0
                """, (today_iso,))
                for r in cur.fetchall():
                    if not r['start_time']: continue
                    try:
                        event_time = datetime.strptime(f"{today_iso} {r['start_time']}", "%Y-%m-%d %H:%M")
                        delta_mins = (event_time - now).total_seconds() / 60.0
                        if 0 <= delta_mins <= 15:
                            notif_id = f"plan_{r['id']}_{today_iso}_{r['start_time']}"
                            if notif_id not in self.notified_events:
                                self.send_tray_notification(
                                    "Plan Hatırlatıcısı ⏰", 
                                    f"'{r['title']}' planınız yakında ({r['start_time']}) başlıyor!\nKategori: {r['category']}",
                                    color="#10b981",
                                    sound_key="sound_plans"
                                )
                                self.notified_events.add(notif_id)
                    except Exception: pass
    def update_network_ui(self, is_online):
        self.is_online_state = is_online
        if hasattr(self, 'lbl_network_status'):
            if is_online:
                self.lbl_network_status.setText("🟢 Online")
                self.lbl_network_status.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px; padding-right: 12px;")
                self.send_tray_notification("İnternet Bağlantısı 🟢", "Sistem tekrar çevrimiçi oldu.", color="#10b981")
            else:
                self.lbl_network_status.setText("🔴 Offline")
                self.lbl_network_status.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 12px; padding-right: 12px;")
                self.send_tray_notification("Bağlantı Koptu 🔴", "Şu anda çevrimdışı çalışıyorsunuz. Web modülleri kısıtlandı.", color="#ef4444")
    def show_welcome_dialog(self):
            dlg = WelcomeDialog(self)
            dlg.exec()
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # =========================================================================
        # AÇILIP KAPANABİLEN YAN MENÜ (SIDEBAR)
        # =========================================================================
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(230)
        
        sb_lay = QVBoxLayout(self.sidebar)
        sb_lay.setContentsMargins(10, 16, 10, 16)
        sb_lay.setSpacing(6)

        top_sb_row = QHBoxLayout()
        top_sb_row.setContentsMargins(0, 0, 0, 0)
        top_sb_row.setSpacing(8)

        self.btn_toggle_sidebar = QPushButton("☰")
        self.btn_toggle_sidebar.setFixedSize(36, 36)
        self.btn_toggle_sidebar.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_toggle_sidebar.setStyleSheet("""
            QPushButton {
                background-color: #1c1917; 
                border: 1px solid #292524; 
                color: #38bdf8; 
                border-radius: 8px; 
                font-weight: bold; 
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #27272a;
                border-color: #38bdf8;
            }
        """)
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)

        top_sb_row.addWidget(self.btn_toggle_sidebar)
        sb_lay.addLayout(top_sb_row)
        sb_lay.addSpacing(10)

        self.nav_buttons = []
        self.pages_info = [
            ("📊 Kontrol Paneli", 0, "Genel Özet & Görevler"),
            ("📋 Yapılacaklar (To-Do)", 1, "Günlük Görev Takibi"),
            ("📅 Akıllı Takvim", 2, "Aylık/Haftalık Planlayıcı"),
            ("📚 Dersler & Notlar", 3, "Haftalık Program & Harf Notu"),
            ("📂 Materyal Havuzu", 4, "PDF Okuyucu & Metin Editörü"),
            ("🏋️ Spor & Alışkanlık", 5, "Zincir & Antrenman Çizelgesi"),
            ("🎵 Müzik & Odak", 6, "YouTube Music & Pomodoro"),
            ("🏫 Üniversite", 7, "OBS & Öğrenci Mail"),
            ("📖 Kitaplığım", 8, "Okuma Listesi ve Arşiv"), # <-- YENİ EKLENDİ
            ("🚀 Projeler", 9, "Yarışma ve Proje Yönetimi"),
            ("⚙️ Ayarlar", 10, "Sistem ve Bildirimler")
        ]

        for text, idx, _ in self.pages_info:
            btn = QPushButton(text)
            btn.setObjectName("NavButton")
            btn.setProperty("full_text", text)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _, i=idx: self.navigate_to(i))
            sb_lay.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_lay.addStretch()
        
        self.status_lbl = QLabel("● Arka Planda Aktif")
        self.status_lbl.setStyleSheet("color: #10B981; font-size: 11px; padding-left: 4px; margin-top: 8px;")
        sb_lay.addWidget(self.status_lbl)
        sb_lay.addSpacing(10)

        

        action_btn_lay = QVBoxLayout() # Yatay dizilimi dikey olarak değiştirdik
        action_btn_lay.setSpacing(6)

        self.btn_tour = QPushButton("💡 Tanıtım")
        self.btn_tour.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_tour.setStyleSheet("background-color: #27272a; color: #facc15; border-radius: 6px; padding: 8px; font-weight: bold; border: 1px solid #3f3f46;")
        self.btn_tour.clicked.connect(self.show_welcome_dialog)

        self.btn_hide = QPushButton("🔽 Arka Plan")
        self.btn_hide.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_hide.setStyleSheet("background-color: #27272a; color: #ffffff; border-radius: 6px; padding: 8px; font-weight: bold; border: 1px solid #3f3f46;")
        self.btn_hide.clicked.connect(self.send_to_background)

        self.btn_quit = QPushButton("🚪 Çıkış")
        self.btn_quit.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_quit.setStyleSheet("background-color: #9f1239; color: #ffffff; border-radius: 6px; padding: 8px; font-weight: bold; border: 1px solid #e11d48;")
        self.btn_quit.clicked.connect(QApplication.quit)

        action_btn_lay.addWidget(self.btn_tour)
        action_btn_lay.addWidget(self.btn_hide)
        action_btn_lay.addWidget(self.btn_quit)
        sb_lay.addLayout(action_btn_lay)

        main_layout.addWidget(self.sidebar)

        # =========================================================================
        # SAĞ PANEL
        # =========================================================================
        right_panel = QWidget()
        right_lay = QVBoxLayout(right_panel)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("TopNavBar")
        top_bar.setFixedHeight(48)
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(12, 0, 16, 0)
        top_lay.setSpacing(8)

        self.btn_back = QPushButton("◀")
        self.btn_back.setObjectName("NavHistButton")
        self.btn_back.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_back.clicked.connect(self.go_back)

        self.btn_forward = QPushButton("▶")
        self.btn_forward.setObjectName("NavHistButton")
        self.btn_forward.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_forward.clicked.connect(self.go_forward)

           

        top_lay.addWidget(self.btn_back)
        top_lay.addWidget(self.btn_forward)

        self.lbl_current_crumb = QLabel("Kontrol Paneli")
        self.lbl_current_crumb.setStyleSheet("font-size: 13px; font-weight: 600; color: #a8a29e; margin-left: 8px;")
        top_lay.addWidget(self.lbl_current_crumb)
        top_lay.addStretch()

        self.lbl_network_status = QLabel("🟢 Online")
        self.lbl_network_status.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px; padding-right: 12px;")
        top_lay.addWidget(self.lbl_network_status)
        self.is_online_state = True # Sistemin ağ durumunu takip eden değişken
        
        self.btn_notif_history = QPushButton("🔔 Bildirimler (0)")
        self.btn_notif_history.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_notif_history.setStyleSheet("background-color: #27272a; color: #e4e4e7; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        self.btn_notif_history.clicked.connect(self.show_notif_history)
        top_lay.addWidget(self.btn_notif_history)

        right_lay.addWidget(top_bar)

        self.stack = QStackedWidget()
        
        self.dashboard_view = DashboardView(self.db, self)
        self.todo_view = TodoView(self.db)
        self.calendar_view = CalendarView(self.db)
        self.timetable_view = TimetableView(self.db)
        self.vault_view = VaultView(self.db)
        self.fitness_view = FitnessView(self.db)
        
        self.music_view = MusicView(self.db, self)
        self.music_view.yt_layout.addWidget(self.yt_webview)
        
        self.university_view = UniversityView(self.db)
        self.library_view = LibraryView(self.db, self)
        self.project_view = ProjectView(self.db) if ProjectView else QWidget()
        self.settings_view = SettingsView(self)

        self.stack.addWidget(self.dashboard_view)    # 0
        self.stack.addWidget(self.todo_view)         # 1
        self.stack.addWidget(self.calendar_view)     # 2
        self.stack.addWidget(self.timetable_view)    # 3
        self.stack.addWidget(self.vault_view)        # 4
        self.stack.addWidget(self.fitness_view)      # 5
        self.stack.addWidget(self.music_view)        # 6
        self.stack.addWidget(self.university_view)   # 7
        self.stack.addWidget(self.library_view)      # 8
        self.stack.addWidget(self.project_view)      # 9
        self.stack.addWidget(self.settings_view)     # 10
        
        content_container = QWidget()
        content_lay = QHBoxLayout(content_container)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(0)
        
        content_lay.addWidget(self.stack)

        right_lay.addWidget(content_container)
        main_layout.addWidget(right_panel)

        self.navigate_to(0)

        self.network_worker = NetworkWorker()
        self.network_worker.status_changed.connect(self.update_network_ui)
        self.network_worker.start()

        try:
            from views.ai_floating_chat import AIChatWindow
            self.ai_chat_window = AIChatWindow(self, self.db)
            
            self.btn_floating_ai = QPushButton("✦", self)
            self.btn_floating_ai.setFixedSize(56, 56)
            self.btn_floating_ai.setCursor(QCursor(Qt.PointingHandCursor))
            self.btn_floating_ai.setStyleSheet("""
                QPushButton { background-color: #3b82f6; color: white; font-size: 26px; border-radius: 28px; border: none; }
                QPushButton:hover { background-color: #2563eb; }
            """)
            self.btn_floating_ai.clicked.connect(self.toggle_ai_chat)
        except ImportError as e:
            print(f"Yapay Zeka Modülü Yüklenemedi: {e}")

    def toggle_sidebar(self):
        start_w = self.sidebar.width()
        end_w = 68 if self.is_sidebar_expanded else 230

        if self.is_sidebar_expanded:
            self.status_lbl.hide()

            # --- DARALTMA DURUMU ---
            self.btn_tour.setProperty("full_text", self.btn_tour.text())
            self.btn_tour.setText("💡")
            self.btn_tour.setToolTip("Tanıtımı Göster")
            self.btn_tour.setStyleSheet("text-align: center; padding: 8px 0px; background-color: #27272a; border-radius: 6px;")
            
            self.btn_hide.setProperty("full_text", self.btn_hide.text())
            self.btn_hide.setText("🔽")
            self.btn_hide.setToolTip("Arka Plana Al")
            self.btn_hide.setStyleSheet("text-align: center; padding: 8px 0px; background-color: #27272a; border-radius: 6px;")
            
            self.btn_quit.setProperty("full_text", self.btn_quit.text())
            self.btn_quit.setText("🚪")
            self.btn_quit.setToolTip("Çıkış Yap")
            self.btn_quit.setStyleSheet("text-align: center; padding: 8px 0px; background-color: #9f1239; border-radius: 6px;")
            
            
            self.is_sidebar_expanded = False
        else:
            # Üstteki navigasyon butonlarının genişletilmesi
            for btn in self.nav_buttons:
                full_text = btn.property("full_text")
                if full_text:
                    btn.setText(full_text)
                    btn.setToolTip("")
                    btn.setStyleSheet("")
                    
            # Alt kısımdaki (Arka Plan ve Çıkış) butonların genişletilmesi [YENİ EKLENDİ]
            full_hide = self.btn_hide.property("full_text")
            if full_hide: 
                self.btn_hide.setText(full_hide)
                self.btn_hide.setStyleSheet("background-color: #27272a; color: #ffffff; border-radius: 6px; padding: 8px; font-weight: bold; border: 1px solid #3f3f46;")
            
            full_quit = self.btn_quit.property("full_text")
            if full_quit: 
                self.btn_quit.setText(full_quit)
                self.btn_quit.setStyleSheet("background-color: #9f1239; color: #ffffff; border-radius: 6px; padding: 8px; font-weight: bold; border: 1px solid #e11d48;")
            # --- GENİŞLETME DURUMU ---
            full_tour = self.btn_tour.property("full_text")
            if full_tour: 
                self.btn_tour.setText(full_tour)
                self.btn_tour.setStyleSheet("background-color: #27272a; color: #facc15; border-radius: 6px; padding: 8px; font-weight: bold; border: 1px solid #3f3f46;")
            self.is_sidebar_expanded = True

        self.sidebar_anim = QVariantAnimation(self)
        self.sidebar_anim.setDuration(220)
        self.sidebar_anim.setStartValue(start_w)
        self.sidebar_anim.setEndValue(end_w)
        self.sidebar_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.sidebar_anim.valueChanged.connect(lambda val: self.sidebar.setFixedWidth(val))

        if self.is_sidebar_expanded:
            self.sidebar_anim.finished.connect(self.status_lbl.show)

        self.sidebar_anim.start()

    def toggle_ai_chat(self):
        if hasattr(self, 'ai_chat_window') and self.ai_chat_window:
            if self.ai_chat_window.isVisible():
                self.ai_chat_window.hide()
            else:
                self.update_ai_chat_geometry()
                self.ai_chat_window.show()
                self.ai_chat_window.raise_()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Hata", "Yapay Zeka modülü yüklenemedi.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_ai_chat_geometry()

    def update_ai_chat_geometry(self):
        if hasattr(self, 'btn_floating_ai'):
            btn_x = self.width() - self.btn_floating_ai.width() - 30
            btn_y = self.height() - self.btn_floating_ai.height() - 30
            self.btn_floating_ai.move(btn_x, btn_y)
            
            if hasattr(self, 'ai_chat_window'):
                chat_x = btn_x - self.ai_chat_window.width() + self.btn_floating_ai.width()
                chat_y = btn_y - self.ai_chat_window.height() - 15
                self.ai_chat_window.move(chat_x, chat_y)

    def setup_event_listeners(self):
        bus.todo_changed.connect(self.dashboard_view.refresh)
        bus.todo_changed.connect(self.todo_view.load_tasks)
        bus.projects_changed.connect(self.project_view.load_projects)

        bus.habits_changed.connect(self.dashboard_view.refresh)
        bus.habits_changed.connect(self.fitness_view.load_habits)
        
        bus.workouts_changed.connect(self.dashboard_view.refresh)
        bus.workouts_changed.connect(self.fitness_view.load_workouts_for_day)
        
        bus.courses_changed.connect(self.dashboard_view.refresh)
        bus.courses_changed.connect(self.calendar_view.refresh_calendar)
        bus.courses_changed.connect(self.timetable_view.load_schedule)
        bus.courses_changed.connect(self.vault_view.refresh_course_filter)
        bus.study_time_changed.connect(self.dashboard_view.refresh)
        
        bus.assessments_changed.connect(self.dashboard_view.refresh)
        bus.assessments_changed.connect(self.calendar_view.refresh_calendar)
        bus.assessments_changed.connect(self.timetable_view.load_assessments)
        
        bus.notes_changed.connect(self.vault_view.load_notes)
        
        bus.calendar_changed.connect(self.dashboard_view.refresh)
        bus.calendar_changed.connect(self.calendar_view.refresh_calendar)

    def navigate_to(self, index: int):
        # İnternet engeli kaldırıldı
        # Tüm sayfalara çevrimdışı olsa bile giriş yapılmasına izin verir

        if not self.is_navigating_history:
            if self.history and self.history[self.history_index] == index:
                return
            self.history = self.history[:self.history_index + 1]
            self.history.append(index)
            self.history_index = len(self.history) - 1

        self.apply_page_switch(index)
        self.update_nav_controls()

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.is_navigating_history = True
            self.apply_page_switch(self.history[self.history_index])
            self.is_navigating_history = False
            self.update_nav_controls()

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.is_navigating_history = True
            self.apply_page_switch(self.history[self.history_index])
            self.is_navigating_history = False
            self.update_nav_controls()

    def apply_page_switch(self, index: int):
        try:
            play_action_sound("nav")
        except: pass
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        title = self.pages_info[index][0].split(" ", 1)[-1]
        desc = self.pages_info[index][2]
        self.lbl_current_crumb.setText(f"{title}  ›  <span style='color: #71717a; font-weight: normal;'>{desc}</span>")

    def update_nav_controls(self):
        self.btn_back.setEnabled(self.history_index > 0)
        self.btn_forward.setEnabled(self.history_index < len(self.history) - 1)

    def check_welcome_screen(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'show_welcome_on_startup'")
            row = cur.fetchone()
            
            # Eğer değer 1 ise (veya kayıtlı değilse) tanıtımı göster
            if not row or row[0] == "1":
                dlg = WelcomeDialog(self)
                dlg.exec()

if __name__ == "__main__":
    if not ensure_single_instance():
        # Eğer uygulama zaten açıksa (arka plandaysa), uyanma sinyali oluştur ve sessizce kapan
        wakeup_file = os.path.join(tempfile.gettempdir(), "student_os_wakeup.txt")
        try:
            with open(wakeup_file, "w") as f:
                f.write("wake")
        except Exception:
            pass
        sys.exit(0)

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    remove_autostart_entry()
    
    if os.name == 'nt':
        try:
            myappid = 'student.life.os.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            
            # Siyah üst pencere çerçevesi (Koyu Tema)
            hwnd = ctypes.windll.user32.FindWindowW(None, "Student Life OS")
            if hwnd:
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(ctypes.c_int(2)),
                    ctypes.sizeof(ctypes.c_int)
                )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Student Life OS")
    
    icon_path = "resources/icons/icon.ico" if os.path.exists("resources/icons/icon.ico") else "icon.ico"
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    app.setStyleSheet(GLOBAL_QSS)
    
    start_hidden = "--hidden" in sys.argv
    
    if not start_hidden:
        splash = SplashScreen()
        splash.show()
        app.processEvents()
    
    win = MainWindow(start_hidden=start_hidden)
    
    if not start_hidden:
        splash.start(lambda: win.show_and_activate())

    try:
        sys.exit(app.exec())
    finally:
        remove_single_instance_lock()