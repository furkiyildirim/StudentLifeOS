import os
import shutil
import random
import wave
import contextlib
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QLineEdit, QTabWidget, QGraphicsDropShadowEffect,
    QListWidget, QListWidgetItem, QSlider, QFileDialog, QStackedWidget, QMessageBox, QMenu,
    QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QUrl, QTimer, QRectF, Signal, QSize
from PySide6.QtGui import QCursor, QPainter, QColor, QPen, QFont, QIcon, QPixmap, QAction
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from core.events import bus
from core.sound import play_action_sound

# =========================================================================
# MİNİMALİST POMODORO SAYACI (MERKEZİ VE HASSAS)
# =========================================================================
class SmoothCircularTimer(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(400, 400)
        self.time_left = 25 * 60
        self.total_time = 25 * 60 
        self.color = QColor("#38bdf8") 
        self.mode_text = "ÇALIŞMA"

    def update_state(self, time_left: int, total_time: int, color_hex: str, mode_text: str):
        self.time_left = time_left
        self.total_time = total_time
        if color_hex:
            self.color = QColor(color_hex)
        self.mode_text = mode_text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        radius = min(w, h) / 2 - 24
        cx, cy = w / 2, h / 2
        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        # Arka plan halkası
        painter.setPen(QPen(QColor("#27272a"), 8, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)

        # İlerleme (Renkli) halkası
        ratio = self.time_left / float(self.total_time) if self.total_time > 0 else 0
        ratio = max(0.0, min(1.0, ratio)) 

        pen_fg = QPen(self.color, 8)
        pen_fg.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_fg)
        
        span_angle = int(-ratio * 360 * 16) 
        painter.drawArc(rect, 90 * 16, span_angle)

        # Süre Metni
        mins, secs = divmod(self.time_left, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        
        painter.setPen(QColor("#ffffff"))
        font_time = QFont("Inter", 64, QFont.Bold)
        painter.setFont(font_time)
        
        text_rect = QRectF(cx - radius, cy - 60, radius * 2, 100)
        painter.drawText(text_rect, Qt.AlignCenter, time_str)

        # Alt Başlık / Mod Metni
        painter.setPen(QColor("#a1a1aa"))
        font_mode = QFont("Inter", 14, QFont.Bold)
        font_mode.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        painter.setFont(font_mode)
        
        mode_rect = QRectF(cx - radius, cy + 40, radius * 2, 40)
        painter.drawText(mode_rect, Qt.AlignCenter, self.mode_text)


# =========================================================================
# ANA MÜZİK VE ODAK GÖRÜNÜMÜ
# =========================================================================
class MusicView(QWidget):
    def __init__(self, db, main_window=None):
        super().__init__()
        self.db = db
        self.main_window = main_window
        
        self.pomodoro_state = "WORK" 
        self.is_timer_running = False
        self.current_round = 1
        self.total_rounds = 4
        
        self.work_time = 25 * 60
        self.short_break_time = 5 * 60
        self.long_break_time = 15 * 60
        self.current_time_left = self.work_time
        self.current_total_time = self.work_time

        # Manuel kaydetmek üzere biriktirilen saniye
        self.unsaved_study_seconds = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timer_tick)

        self.duration_timer = QTimer(self)
        self.duration_timer.setInterval(500)
        self.duration_timer.timeout.connect(self.check_media_duration)
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.5) 
        
        self.player.positionChanged.connect(self.update_slider_position)
        self.player.durationChanged.connect(self.update_slider_duration)
        self.player.mediaStatusChanged.connect(self.handle_media_status)
        
        self.is_slider_pressed = False
        self.current_track_index = -1
        
        self.is_shuffle = False
        self.is_repeat = False
        self.shuffle_played_tracks = set()
        self.shuffle_recent_tracks = []
        
        self.music_dir = os.path.join(os.getcwd(), "resources", "musics")
        self.cover_dir = os.path.join(os.getcwd(), "resources", "covers")
        os.makedirs(self.music_dir, exist_ok=True)
        os.makedirs(self.cover_dir, exist_ok=True)
        
        self.setup_tables()

        self.active_playlist_id = None
        self.current_playlist_tracks = []

        self.init_ui()
        self.load_playlists()

    def setup_tables(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cover_path TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER,
                    file_path TEXT NOT NULL,
                    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def extract_cover_from_mp3(self, mp3_path, dest_cover_path):
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, APIC
            audio = MP3(mp3_path, ID3=ID3)
            if audio.tags:
                for tag in audio.tags.values():
                    if isinstance(tag, APIC):
                        with open(dest_cover_path, "wb") as f:
                            f.write(tag.data)
                        return True
        except Exception:
            pass
        return False

    def get_tinted_icon(self, icon_path, color_hex):
        pixmap = QPixmap(icon_path)
        if pixmap.isNull(): return QIcon()
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color_hex))
        painter.end()
        return QIcon(pixmap)

    def get_default_cover(self):
        pixmap = QPixmap(100, 100)
        pixmap.fill(QColor("#27272a"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#1db954"))
        painter.setFont(QFont("Inter", 32, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "🎵")
        painter.end()
        return QIcon(pixmap)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        header = QLabel("🎵 Müzik & Odak Alanı")
        header.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")
        main_layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_local_music_tab(), "💾 Yerel Müzikler")
        self.tabs.addTab(self.create_youtube_tab(), "🎧 YouTube Music")
        self.tabs.addTab(self.create_focus_tab(), "🍅 İnteraktif Odak Sayacı")
        
        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs)

    # =========================================================================
    # YEREL MÜZİK
    # =========================================================================
    def create_local_music_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(10)

        playlist_header = QHBoxLayout()
        lbl_p_title = QLabel("📚 Çalma Listelerim")
        lbl_p_title.setStyleSheet("font-weight: bold; color: #a1a1aa; font-size: 14px;")
        playlist_header.addWidget(lbl_p_title)
        playlist_header.addStretch()
        
        btn_new_playlist = QPushButton("➕ Yeni Liste")
        btn_new_playlist.setCursor(QCursor(Qt.PointingHandCursor))
        btn_new_playlist.setStyleSheet("background-color: #1db954; color: #121212; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        btn_new_playlist.clicked.connect(self.create_new_playlist)
        
        btn_del_playlist = QPushButton("🗑️ Seçili Listeyi Sil")
        btn_del_playlist.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del_playlist.setStyleSheet("background-color: transparent; border: 1px solid #ef4444; color: #ef4444; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        btn_del_playlist.clicked.connect(self.delete_playlist)
        
        playlist_header.addWidget(btn_new_playlist)
        playlist_header.addWidget(btn_del_playlist)
        lay.addLayout(playlist_header)

        self.playlists_view = QListWidget()
        self.playlists_view.setViewMode(QListWidget.IconMode)
        self.playlists_view.setFlow(QListWidget.LeftToRight)
        self.playlists_view.setWrapping(False) 
        self.playlists_view.setDragDropMode(QListWidget.NoDragDrop)
        self.playlists_view.setDragEnabled(False)
        self.playlists_view.setAcceptDrops(False)
        self.playlists_view.setDropIndicatorShown(False)
        self.playlists_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.playlists_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.playlists_view.setIconSize(QSize(100, 100))
        self.playlists_view.setGridSize(QSize(132, 138))
        self.playlists_view.setFixedHeight(170)
        self.playlists_view.setSpacing(15)
        self.playlists_view.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { background-color: #18181b; border-radius: 8px; padding: 8px; color: white; }
            QListWidget::item:selected { background-color: #27272a; border: 2px solid #1db954; }
            QListWidget::item:hover { background-color: #27272a; }
        """)
        self.playlists_view.itemClicked.connect(self.on_playlist_clicked)
        lay.addWidget(self.playlists_view)

        self.playlist_widget = QListWidget()
        self.playlist_widget.setDragDropMode(QListWidget.NoDragDrop)
        self.playlist_widget.setDragEnabled(False)
        self.playlist_widget.setAcceptDrops(False)
        self.playlist_widget.setDropIndicatorShown(False)
        self.playlist_widget.setSpacing(2)
        self.playlist_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.playlist_widget.setStyleSheet("""
            QListWidget { background-color: #121212; border-radius: 8px; border: 1px solid #27272a; padding: 10px; color: #e4e4e7; font-size: 14px; }
            QListWidget::item { padding: 12px; border-radius: 6px; margin-bottom: 4px; border-bottom: 1px solid #27272a; }
            QListWidget::item:hover { background-color: #1f1f22; border-bottom: 1px solid #3f3f46; }
            QListWidget::item:selected { background-color: #1db954; color: #121212; font-weight: bold; border-bottom: none; }
        """)
        self.playlist_widget.itemDoubleClicked.connect(self.play_selected_track)
        lay.addWidget(self.playlist_widget, stretch=1)

        player_bar = QFrame()
        player_bar.setStyleSheet("background-color: #18181b; border-radius: 12px; border: 1px solid #27272a;")
        p_lay = QHBoxLayout(player_bar)
        p_lay.setContentsMargins(16, 12, 16, 12)
        
        info_lay = QHBoxLayout()
        info_lay.setSpacing(12)
        
        self.lbl_cover = QLabel("🎵")
        self.lbl_cover.setFixedSize(48, 48)
        self.lbl_cover.setAlignment(Qt.AlignCenter)
        self.lbl_cover.setStyleSheet("background-color: #27272a; color: #a1a1aa; font-size: 24px; border-radius: 8px;")
        
        text_info_lay = QVBoxLayout()
        text_info_lay.setAlignment(Qt.AlignVCenter)
        self.lbl_track_name = QLabel("Şu an çalan parça yok")
        self.lbl_track_name.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 14px;")
        self.lbl_track_artist = QLabel("Yerel Müzik Çalar")
        self.lbl_track_artist.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        
        text_info_lay.addWidget(self.lbl_track_name)
        text_info_lay.addWidget(self.lbl_track_artist)
        info_lay.addWidget(self.lbl_cover)
        info_lay.addLayout(text_info_lay)
        p_lay.addLayout(info_lay, stretch=2)
        
        mid_lay = QVBoxLayout()
        mid_lay.setAlignment(Qt.AlignCenter)
        
        ctrl_btn_lay = QHBoxLayout()
        ctrl_btn_lay.setSpacing(16)
        
        btn_style_sec = """
            QPushButton { background: transparent; border: none; border-radius: 12px; } 
            QPushButton:hover { background-color: #27272a; }
        """
        icon_size = QSize(22, 22)

        self.btn_shuffle = QPushButton()
        self.btn_shuffle.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_shuffle.setStyleSheet(btn_style_sec)
        self.btn_shuffle.setIcon(self.get_tinted_icon(os.path.join("resources", "icons", "shuffle.ico"), "#ffffff"))
        self.btn_shuffle.setIconSize(icon_size)
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        
        self.btn_prev = QPushButton()
        self.btn_prev.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_prev.setStyleSheet(btn_style_sec)
        self.btn_prev.setIcon(self.get_tinted_icon(os.path.join("resources", "icons", "prev.ico"), "#ffffff"))
        self.btn_prev.setIconSize(icon_size)
        self.btn_prev.clicked.connect(self.play_previous)
        
        self.btn_play = QPushButton()
        self.btn_play.setFixedSize(48, 48)
        self.btn_play.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_play.setStyleSheet("""
            QPushButton { background-color: #ffffff; border-radius: 24px; border: none; }
            QPushButton:hover { background-color: #e4e4e7; transform: scale(1.05); }
        """)
        self.btn_play.setIcon(self.get_tinted_icon(os.path.join("resources", "icons", "play.ico"), "#0c0a09"))
        self.btn_play.setIconSize(QSize(24, 24))
        self.btn_play.clicked.connect(self.toggle_play_music)
        
        self.btn_next = QPushButton()
        self.btn_next.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_next.setStyleSheet(btn_style_sec)
        self.btn_next.setIcon(self.get_tinted_icon(os.path.join("resources", "icons", "next.ico"), "#ffffff"))
        self.btn_next.setIconSize(icon_size)
        self.btn_next.clicked.connect(self.play_next)
        
        self.btn_repeat = QPushButton()
        self.btn_repeat.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_repeat.setStyleSheet(btn_style_sec)
        self.btn_repeat.setIcon(self.get_tinted_icon(os.path.join("resources", "icons", "repeat.ico"), "#ffffff"))
        self.btn_repeat.setIconSize(icon_size)
        self.btn_repeat.clicked.connect(self.toggle_repeat)
        
        ctrl_btn_lay.addStretch()
        ctrl_btn_lay.addWidget(self.btn_shuffle)
        ctrl_btn_lay.addWidget(self.btn_prev)
        ctrl_btn_lay.addWidget(self.btn_play)
        ctrl_btn_lay.addWidget(self.btn_next)
        ctrl_btn_lay.addWidget(self.btn_repeat)
        ctrl_btn_lay.addStretch()
        mid_lay.addLayout(ctrl_btn_lay)
        
        slider_lay = QHBoxLayout()
        self.lbl_time_cur = QLabel("0:00")
        self.lbl_time_cur.setStyleSheet("color: #a1a1aa; font-size: 11px; min-width: 30px;")
        
        self.slider_progress = QSlider(Qt.Horizontal)
        self.slider_progress.setCursor(QCursor(Qt.PointingHandCursor))
        self.slider_progress.setStyleSheet("""
            QSlider { height: 16px; background: transparent; }
            QSlider::groove:horizontal { background: #3f3f46; height: 4px; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #ffffff; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #ffffff; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::handle:horizontal:hover { background: #1db954; }
        """)
        self.slider_progress.sliderPressed.connect(self.slider_pressed)
        self.slider_progress.sliderReleased.connect(self.slider_released)
        self.slider_progress.sliderMoved.connect(self.slider_moved)
        
        self.lbl_time_tot = QLabel("0:00")
        self.lbl_time_tot.setStyleSheet("color: #a1a1aa; font-size: 11px; min-width: 30px;")
        
        slider_lay.addWidget(self.lbl_time_cur)
        slider_lay.addWidget(self.slider_progress)
        slider_lay.addWidget(self.lbl_time_tot)
        mid_lay.addLayout(slider_lay)
        
        p_lay.addLayout(mid_lay, stretch=5)
        
        right_lay = QVBoxLayout()
        right_lay.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        vol_frame = QFrame()
        vol_lay = QHBoxLayout(vol_frame)
        vol_lay.setContentsMargins(0, 0, 0, 0)
        vol_lay.setSpacing(8)
        
        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_mute.setStyleSheet("font-size: 14px; background: transparent; border: none; color: #a1a1aa;")
        self.btn_mute.clicked.connect(self.toggle_mute)
        
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(50)
        self.slider_volume.setFixedWidth(100)
        self.slider_volume.setStyleSheet("""
            QSlider { height: 16px; background: transparent; }
            QSlider::groove:horizontal { background: #3f3f46; height: 4px; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #1db954; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #ffffff; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::handle:horizontal:hover { background: #1db954; }
        """)
        self.slider_volume.valueChanged.connect(self.change_volume)
        
        vol_lay.addWidget(self.btn_mute)
        vol_lay.addWidget(self.slider_volume)
        right_lay.addWidget(vol_frame, alignment=Qt.AlignRight)

        btn_add_music = QPushButton("🎵 Listeye Şarkı Ekle")
        btn_add_music.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_music.setStyleSheet("background-color: transparent; border: 1px solid #1db954; color: #1db954; border-radius: 6px; padding: 4px 12px; font-weight: bold; font-size: 11px;")
        btn_add_music.clicked.connect(self.add_local_music)
        
        right_lay.addWidget(btn_add_music, alignment=Qt.AlignRight)
        p_lay.addLayout(right_lay, stretch=2)
        lay.addWidget(player_bar)
        
        return tab

    def load_playlists(self):
        self.playlists_view.clear()
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, cover_path FROM playlists")
            rows = cur.fetchall()
            if not rows:
                cur.execute("INSERT INTO playlists (name, cover_path) VALUES ('Ana Liste', '')")
                conn.commit()
                cur.execute("SELECT id, name, cover_path FROM playlists")
                rows = cur.fetchall()
            for row in rows:
                item = QListWidgetItem(row["name"])
                item.setData(Qt.UserRole, row["id"])
                cover = row["cover_path"]
                if cover and os.path.exists(cover):
                    item.setIcon(QIcon(cover))
                else:
                    item.setIcon(self.get_default_cover())
                self.playlists_view.addItem(item)
        if self.playlists_view.count() > 0:
            self.playlists_view.setCurrentRow(0)
            self.on_playlist_clicked(self.playlists_view.item(0))

    def on_playlist_clicked(self, item=None):
        if not item: item = self.playlists_view.currentItem()
        if not item: return
        playlist_id = item.data(Qt.UserRole)
        self.active_playlist_id = playlist_id
        self.playlist_widget.clear()
        self.current_playlist_tracks.clear()
        self.shuffle_played_tracks.clear()
        self.shuffle_recent_tracks.clear()
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT file_path FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
            for track in cur.fetchall():
                path = track["file_path"]
                if os.path.exists(path):
                    self.add_track_to_ui(path)
                else:
                    cur.execute("DELETE FROM playlist_tracks WHERE playlist_id = ? AND file_path = ?", (playlist_id, path))
            conn.commit()

    def show_context_menu(self, pos):
        item = self.playlist_widget.itemAt(pos)
        if not item: return
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #18181b; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 6px; padding: 4px; font-size: 13px; }
            QMenu::item { padding: 6px 24px; border-radius: 4px; }
            QMenu::item:selected { background-color: #27272a; }
        """)
        move_menu = menu.addMenu("➡️ Başka Listeye Taşı")
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM playlists WHERE id != ?", (self.active_playlist_id,))
            for row in cur.fetchall():
                action = QAction(row["name"], self)
                action.triggered.connect(lambda checked, pid=row["id"], itm=item: self.move_song(itm, pid))
                move_menu.addAction(action)
        remove_action = QAction("➖ Bu Listeden Çıkar", self)
        remove_action.triggered.connect(lambda: self.remove_from_playlist(item))
        delete_action = QAction("🗑️ Bilgisayardan Tamamen Sil", self)
        delete_action.triggered.connect(lambda: self.delete_from_disk(item))
        menu.addAction(remove_action)
        menu.addAction(delete_action)
        menu.exec(self.playlist_widget.mapToGlobal(pos))

    def move_song(self, item, target_playlist_id):
        file_path = item.data(Qt.UserRole)
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND file_path = ?", (target_playlist_id, file_path))
            if not cur.fetchone():
                cur.execute("UPDATE playlist_tracks SET playlist_id = ? WHERE playlist_id = ? AND file_path = ?", 
                            (target_playlist_id, self.active_playlist_id, file_path))
            else:
                cur.execute("DELETE FROM playlist_tracks WHERE playlist_id = ? AND file_path = ?", (self.active_playlist_id, file_path))
            conn.commit()
        row = self.playlist_widget.row(item)
        self.playlist_widget.takeItem(row)
        if file_path in self.current_playlist_tracks:
            self.current_playlist_tracks.remove(file_path)

    def create_new_playlist(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Yeni Playlist", "Çalma Listesi Adı:")
        if not ok or not name.strip(): return
        cover_path, _ = QFileDialog.getOpenFileName(self, "Kapak Fotoğrafı Seç (İsteğe Bağlı)", "", "Resimler (*.png *.jpg *.jpeg)")
        dest_cover = ""
        if cover_path:
            file_size_mb = os.path.getsize(cover_path) / (1024 * 1024)
            if file_size_mb > 5:
                QMessageBox.warning(self, "Boyut Uyarısı", "Seçtiğiniz kapak fotoğrafı 5MB'tan büyük. Uygulamanın hızlı çalışması için daha küçük boyutlu bir görsel seçmeniz önerilir.")
            filename = os.path.basename(cover_path)
            dest_cover = os.path.join(self.cover_dir, f"cover_{random.randint(1000, 9999)}_{filename}")
            try: shutil.copy2(cover_path, dest_cover)
            except: dest_cover = ""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO playlists (name, cover_path) VALUES (?, ?)", (name.strip(), dest_cover))
            conn.commit()
        self.load_playlists()

    def delete_playlist(self):
        item = self.playlists_view.currentItem()
        if not item: return
        playlist_id = item.data(Qt.UserRole)
        if self.playlists_view.count() <= 1:
            QMessageBox.warning(self, "Uyarı", "Son kalan listeyi silemezsiniz.")
            return
        reply = QMessageBox.question(self, "Listeyi Sil", f"'{item.text()}' listesini silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT cover_path FROM playlists WHERE id = ?", (playlist_id,))
                cover = cur.fetchone()["cover_path"]
                if cover and os.path.exists(cover):
                    try: os.remove(cover)
                    except: pass
                cur.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
                conn.commit()
            self.load_playlists()

    def remove_from_playlist(self, item):
        file_path = item.data(Qt.UserRole)
        row = self.playlist_widget.row(item)
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM playlist_tracks WHERE playlist_id = ? AND file_path = ?", (self.active_playlist_id, file_path))
            conn.commit()
        self.playlist_widget.takeItem(row)
        if file_path in self.current_playlist_tracks:
            self.current_playlist_tracks.remove(file_path)
        if self.player.source().toLocalFile() == file_path:
            self.player.stop()
            self.lbl_track_name.setText("Şu an çalan parça yok")
            self.slider_progress.setValue(0)
            self.btn_play.setIcon(self.get_tinted_icon(os.path.join("resources", "icons", "play.ico"), "#0c0a09"))

    def delete_from_disk(self, item):
        file_path = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "Kalıcı Silme", "Bu müziği bilgisayarınızdan tamamen silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.remove_from_playlist(item)
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass

    def toggle_shuffle(self):
        self.is_shuffle = not self.is_shuffle
        if self.is_shuffle:
            self.shuffle_played_tracks.clear()
            self.shuffle_recent_tracks.clear()
            current_item = self.playlist_widget.currentItem()
            if current_item:
                self.record_shuffle_track(current_item.data(Qt.UserRole))
        color = "#1db954" if self.is_shuffle else "#ffffff"
        icon_path = os.path.join("resources", "icons", "shuffle.ico")
        self.btn_shuffle.setIcon(self.get_tinted_icon(icon_path, color))

    def toggle_repeat(self):
        self.is_repeat = not self.is_repeat
        color = "#1db954" if self.is_repeat else "#ffffff"
        icon_path = os.path.join("resources", "icons", "repeat.ico")
        self.btn_repeat.setIcon(self.get_tinted_icon(icon_path, color))

    def handle_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            duration = self.player.duration()
            if duration > 0:
                self.update_slider_duration(duration)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_auto_next()

    def play_auto_next(self):
        if self.playlist_widget.count() == 0: return
        if self.is_repeat:
            self.player.setPosition(0)
            self.player.play()
        elif self.is_shuffle:
            file_path = self.select_shuffle_track()
            item = next((self.playlist_widget.item(i) for i in range(self.playlist_widget.count())
                         if self.playlist_widget.item(i).data(Qt.UserRole) == file_path), None)
            if not item: return
            self.current_track_index = self.playlist_widget.row(item)
            self.playlist_widget.setCurrentItem(item)
            self.load_and_play(file_path)
        else:
            self.play_next()

    def record_shuffle_track(self, file_path):
        if not file_path: return
        self.shuffle_played_tracks.add(file_path)
        if file_path in self.shuffle_recent_tracks:
            self.shuffle_recent_tracks.remove(file_path)
        self.shuffle_recent_tracks.append(file_path)
        del self.shuffle_recent_tracks[:-5]

    def select_shuffle_track(self):
        tracks = [self.playlist_widget.item(i).data(Qt.UserRole) for i in range(self.playlist_widget.count())]
        if not tracks: return None
        candidates = [path for path in tracks if path not in self.shuffle_played_tracks]
        if not candidates:
            self.shuffle_played_tracks.clear()
            candidates = [path for path in tracks if path not in self.shuffle_recent_tracks]
        current_item = self.playlist_widget.currentItem()
        current_path = current_item.data(Qt.UserRole) if current_item else None
        if len(candidates) > 1 and current_path in candidates:
            candidates.remove(current_path)
        return random.choice(candidates or tracks)

    def add_track_to_ui(self, file_path):
        for i in range(self.playlist_widget.count()):
            if self.playlist_widget.item(i).data(Qt.UserRole) == file_path: return 
        name = os.path.basename(file_path)
        item = QListWidgetItem(f"   {name}")
        item.setData(Qt.UserRole, file_path) 
        self.playlist_widget.addItem(item)
        self.current_playlist_tracks.append(file_path)

    def add_local_music(self):
        if not self.active_playlist_id:
            QMessageBox.warning(self, "Hata", "Lütfen önce bir çalma listesi seçin veya oluşturun.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Müzik Dosyalarını Seç", "", "Ses Dosyaları (*.mp3 *.wav *.ogg *.m4a)")
        is_first_song_check_needed = True
        for file_path in files:
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.music_dir, filename)
            if os.path.abspath(file_path) != os.path.abspath(dest_path):
                try: shutil.copy2(file_path, dest_path)
                except Exception: continue
            if dest_path not in self.current_playlist_tracks:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO playlist_tracks (playlist_id, file_path) VALUES (?, ?)", (self.active_playlist_id, dest_path))
                    if is_first_song_check_needed and dest_path.lower().endswith('.mp3'):
                        cur.execute("SELECT cover_path FROM playlists WHERE id = ?", (self.active_playlist_id,))
                        res = cur.fetchone()
                        if res and not res["cover_path"]:
                            new_cover_path = os.path.join(self.cover_dir, f"auto_cover_{self.active_playlist_id}.jpg")
                            if self.extract_cover_from_mp3(dest_path, new_cover_path):
                                cur.execute("UPDATE playlists SET cover_path = ? WHERE id = ?", (new_cover_path, self.active_playlist_id))
                                is_first_song_check_needed = False
                    conn.commit()
                self.add_track_to_ui(dest_path)
        self.load_playlists()

    def play_selected_track(self, item):
        self.current_track_index = self.playlist_widget.row(item)
        file_path = item.data(Qt.UserRole)
        self.load_and_play(file_path)

    def load_and_play(self, file_path):
        if self.is_shuffle:
            self.record_shuffle_track(file_path)
        name = os.path.basename(file_path)
        self.lbl_track_name.setText(name)
        cover = ""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT cover_path FROM playlists WHERE id = ?", (self.active_playlist_id,))
            res = cur.fetchone()
            if res: cover = res["cover_path"]
        if cover and os.path.exists(cover):
            self.lbl_cover.setPixmap(QPixmap(cover).scaled(48, 48, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else:
            self.lbl_cover.setText("💿") 
            self.lbl_cover.setStyleSheet("background-color: #1db954; color: #121212; font-size: 24px; border-radius: 8px;")
        
        self.slider_progress.setRange(0, 0)
        self.slider_progress.setValue(0)
        self.lbl_time_cur.setText("0:00")
        self.lbl_time_tot.setText("0:00")
        
        self.player.setSource(QUrl.fromLocalFile(file_path))
        calculated_duration = 0
        if file_path.lower().endswith('.wav'):
            try:
                with contextlib.closing(wave.open(file_path, 'r')) as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    calculated_duration = int((frames / float(rate)) * 1000)
            except Exception: pass
        if calculated_duration > 0:
            self.update_slider_duration(calculated_duration)
        else:
            self.duration_timer.start()

        self.player.play()
        self.btn_play.setText("") 
        pause_icon = os.path.join("resources", "icons", "pause.ico")
        self.btn_play.setIcon(self.get_tinted_icon(pause_icon, "#0c0a09"))

    def check_media_duration(self):
        duration = self.player.duration()
        if duration > 0:
            self.update_slider_duration(duration)
            self.duration_timer.stop()

    def toggle_play_music(self):
        if self.playlist_widget.count() == 0: return
        play_icon = os.path.join("resources", "icons", "play.ico")
        pause_icon = os.path.join("resources", "icons", "pause.ico")
        self.btn_play.setText("") 
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.btn_play.setIcon(self.get_tinted_icon(play_icon, "#0c0a09"))
        else:
            if self.current_track_index == -1:
                self.play_next()
            else:
                self.player.play()
                self.btn_play.setIcon(self.get_tinted_icon(pause_icon, "#0c0a09"))

    def play_next(self):
        count = self.playlist_widget.count()
        if count == 0: return
        self.current_track_index = (self.current_track_index + 1) % count
        item = self.playlist_widget.item(self.current_track_index)
        self.playlist_widget.setCurrentItem(item)
        self.load_and_play(item.data(Qt.UserRole))

    def play_previous(self):
        count = self.playlist_widget.count()
        if count == 0: return
        self.current_track_index = (self.current_track_index - 1) % count
        item = self.playlist_widget.item(self.current_track_index)
        self.playlist_widget.setCurrentItem(item)
        self.load_and_play(item.data(Qt.UserRole))

    def update_slider_position(self, pos):
        if not self.is_slider_pressed and self.slider_progress.maximum() > 0:
            self.slider_progress.setValue(pos)
            self.lbl_time_cur.setText(self.format_time(pos))

    def update_slider_duration(self, duration):
        if duration > 0:
            self.slider_progress.setRange(0, duration)
            self.lbl_time_tot.setText(self.format_time(duration))

    def slider_pressed(self):
        self.is_slider_pressed = True

    def slider_released(self):
        self.is_slider_pressed = False
        self.player.setPosition(self.slider_progress.value())

    def slider_moved(self, pos):
        self.lbl_time_cur.setText(self.format_time(pos))

    def change_volume(self, val):
        vol_float = val / 100.0
        self.audio_output.setVolume(vol_float)
        if val == 0: self.btn_mute.setText("🔇")
        elif val < 50: self.btn_mute.setText("🔉")
        else: self.btn_mute.setText("🔊")

    def toggle_mute(self):
        if self.slider_volume.value() == 0:
            self.slider_volume.setValue(50)
            self.audio_output.setVolume(0.5)
            self.btn_mute.setText("🔉")
        else:
            self.slider_volume.setValue(0)
            self.audio_output.setVolume(0.0)
            self.btn_mute.setText("🔇")

    def format_time(self, ms):
        secs = ms // 1000
        m, s = divmod(secs, 60)
        return f"{m}:{s:02d}"

    def create_youtube_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(10)

        self.yt_stack = QStackedWidget()

        offline_widget = QWidget()
        off_lay = QVBoxLayout(offline_widget)
        off_lay.setAlignment(Qt.AlignCenter)
        lbl_off = QLabel("🔌 Çevrimdışısınız")
        lbl_off.setStyleSheet("font-size: 24px; font-weight: bold; color: #ef4444;")
        lbl_desc = QLabel("YouTube Music kullanabilmek için aktif bir internet bağlantısı gereklidir.\nLütfen yerel müzik çaları (1. Sekme) kullanın.")
        lbl_desc.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        lbl_desc.setAlignment(Qt.AlignCenter)
        off_lay.addWidget(lbl_off, alignment=Qt.AlignCenter)
        off_lay.addWidget(lbl_desc, alignment=Qt.AlignCenter)
        self.yt_stack.addWidget(offline_widget)

        online_widget = QWidget()
        on_lay = QVBoxLayout(online_widget)
        on_lay.setContentsMargins(0, 0, 0, 0)
        
        link_row = QHBoxLayout()
        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("YouTube Music playlist linki yapıştırın (İsteğe bağlı)...")
        self.link_input.setFixedHeight(34)
        self.link_input.setStyleSheet("background-color: #27272a; border-radius: 6px; padding: 0 10px; color: white;")
        
        btn_load = QPushButton("Git")
        btn_load.setObjectName("AccentButton")
        btn_load.setCursor(QCursor(Qt.PointingHandCursor))
        btn_load.setFixedHeight(34)
        btn_load.clicked.connect(self.load_music_link)
        
        link_row.addWidget(self.link_input)
        link_row.addWidget(btn_load)
        on_lay.addLayout(link_row)

        self.yt_layout = QVBoxLayout()
        on_lay.addLayout(self.yt_layout)
        self.yt_stack.addWidget(online_widget)

        lay.addWidget(self.yt_stack)
        return tab

    def load_music_link(self):
        raw_url = self.link_input.text().strip()
        if not raw_url: return
        if self.main_window and hasattr(self.main_window, 'yt_webview'):
            self.main_window.yt_webview.setUrl(QUrl(raw_url))

    def on_tab_changed(self, index):
        if index == 1:
            try:
                from core.network import check_internet_connection
                if not check_internet_connection():
                    self.yt_stack.setCurrentIndex(0) 
                else:
                    self.yt_stack.setCurrentIndex(1) 
            except Exception:
                self.yt_stack.setCurrentIndex(1)

    # =========================================================================
    # YENİ TASARIM: POMODORO ODAK SAYACI (SES GERİ BİLDİRİMLİ & MANUEL KAYITLI)
    # =========================================================================
    def create_focus_tab(self):
        tab = QWidget()
        lay = QHBoxLayout(tab)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(30)

        # ---------------- SOL PANEL: AYARLAR ----------------
        left_panel = QFrame()
        left_panel.setFixedWidth(320)
        left_panel.setStyleSheet("""
            QFrame { background-color: #171412; border: 1px solid #292524; border-radius: 12px; }
        """)
        l_lay = QVBoxLayout(left_panel)
        l_lay.setContentsMargins(24, 24, 24, 24)
        l_lay.setSpacing(20)

        title_lbl = QLabel("AYARLAR")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 900; color: #ffffff; letter-spacing: 2px; border: none; background: transparent;")
        l_lay.addWidget(title_lbl)
        
        def create_setting_row(label_text, min_val, max_val, current_val, suffix="dk"):
            row = QVBoxLayout()
            row.setSpacing(6)
            
            top_h = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 13px; color: #a1a1aa; font-weight: bold; border: none; background: transparent;")
            val_lbl = QLabel(f"{current_val} {suffix}")
            val_lbl.setStyleSheet("font-size: 13px; color: #ffffff; font-weight: bold; border: none; background: transparent;")
            top_h.addWidget(lbl)
            top_h.addStretch()
            top_h.addWidget(val_lbl)
            row.addLayout(top_h)
            
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(current_val)
            slider.setCursor(QCursor(Qt.PointingHandCursor))
            slider.setStyleSheet("""
                QSlider { height: 20px; background: transparent; border: none; }
                QSlider::groove:horizontal { background: #3f3f46; height: 6px; border-radius: 3px; }
                QSlider::sub-page:horizontal { background: #38bdf8; height: 6px; border-radius: 3px; }
                QSlider::handle:horizontal { background: #ffffff; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
                QSlider::handle:horizontal:hover { transform: scale(1.1); }
            """)
            
            slider.valueChanged.connect(lambda v: val_lbl.setText(f"{v} {suffix}"))
            row.addWidget(slider)
            l_lay.addLayout(row)
            return slider

        self.slider_work = create_setting_row("Çalışma Süresi", 1, 60, 25, "dk")
        self.slider_short = create_setting_row("Kısa Mola", 1, 15, 5, "dk")
        self.slider_long = create_setting_row("Uzun Mola", 5, 30, 15, "dk")
        self.slider_rounds = create_setting_row("Oturum Sayısı", 1, 10, 4, "oturum")

        l_lay.addStretch()
        
        btn_restore = QPushButton("Varsayılanlara Dön")
        btn_restore.setCursor(QCursor(Qt.PointingHandCursor))
        btn_restore.setStyleSheet("""
            QPushButton { background-color: transparent; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 6px; padding: 10px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background-color: #27272a; color: #ffffff; }
        """)
        btn_restore.clicked.connect(self.restore_timer_defaults)
        l_lay.addWidget(btn_restore)

        btn_apply = QPushButton("Kaydet ve Yenile")
        btn_apply.setCursor(QCursor(Qt.PointingHandCursor))
        btn_apply.setStyleSheet("""
            QPushButton { background-color: #38bdf8; color: #0c0a09; border-radius: 6px; padding: 10px; font-weight: bold; font-size: 12px; border: none; }
            QPushButton:hover { background-color: #0284c7; color: #ffffff; }
        """)
        btn_apply.clicked.connect(self._on_apply_clicked)
        l_lay.addWidget(btn_apply)

        # ---------------- SAĞ PANEL: SAYAÇ VE KONTROLLER ----------------
        right_panel = QFrame()
        right_panel.setStyleSheet("background: transparent; border: none;")
        r_lay = QVBoxLayout(right_panel)
        r_lay.setAlignment(Qt.AlignCenter)
        r_lay.setSpacing(20)

        r_lay.addStretch(1)

        self.circular_timer = SmoothCircularTimer()
        self.glow_effect = QGraphicsDropShadowEffect()
        self.glow_effect.setBlurRadius(50)
        self.glow_effect.setColor(QColor("#38bdf8"))
        self.glow_effect.setOffset(0, 0)
        self.circular_timer.setGraphicsEffect(self.glow_effect)
        r_lay.addWidget(self.circular_timer, alignment=Qt.AlignCenter)

        r_lay.addStretch(1)

        ctrl_lay = QHBoxLayout()
        ctrl_lay.setContentsMargins(0, 0, 0, 0)

        self.lbl_session = QLabel(f"1/{self.total_rounds}\nOTURUM")
        self.lbl_session.setFixedWidth(80)
        self.lbl_session.setStyleSheet("color: #a1a1aa; font-weight: bold; font-size: 12px; letter-spacing: 2px; border: none;")
        self.lbl_session.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        ctrl_lay.addWidget(self.lbl_session)
        
        ctrl_lay.addStretch()

        mid_btns = QHBoxLayout()
        mid_btns.setSpacing(35)
        mid_btns.setAlignment(Qt.AlignCenter)

        icon_play = os.path.join("resources", "icons", "play.ico")
        icon_skip = os.path.join("resources", "icons", "next.ico")

        self.btn_timer_reset = QPushButton("↻")
        self.btn_timer_reset.setFixedSize(40, 40)
        self.btn_timer_reset.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_timer_reset.setStyleSheet("background: transparent; color: #a1a1aa; font-size: 26px; font-weight: bold; border: none;")
        self.btn_timer_reset.clicked.connect(self.reset_timer_phase)
        mid_btns.addWidget(self.btn_timer_reset)

        self.btn_timer_play = QPushButton()
        self.btn_timer_play.setFixedSize(64, 64)
        self.btn_timer_play.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_timer_play.setIcon(self.get_tinted_icon(icon_play, "#ffffff"))
        self.btn_timer_play.setIconSize(QSize(28, 28))
        self.btn_timer_play.setStyleSheet("""
            QPushButton { background-color: #1e293b; border-radius: 32px; border: none; }
            QPushButton:hover { background-color: #334155; transform: scale(1.05); }
        """)
        self.btn_timer_play.clicked.connect(self.toggle_pomodoro)
        mid_btns.addWidget(self.btn_timer_play)

        self.btn_timer_skip = QPushButton()
        self.btn_timer_skip.setFixedSize(40, 40)
        self.btn_timer_skip.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_timer_skip.setIcon(self.get_tinted_icon(icon_skip, "#a1a1aa"))
        self.btn_timer_skip.setIconSize(QSize(20, 20))
        self.btn_timer_skip.setStyleSheet("background: transparent; border: none;")
        self.btn_timer_skip.clicked.connect(self.skip_timer_phase)
        mid_btns.addWidget(self.btn_timer_skip)

        ctrl_lay.addLayout(mid_btns)
        ctrl_lay.addStretch()
        
        spacer = QLabel()
        spacer.setFixedWidth(80)
        spacer.setStyleSheet("background: transparent; border: none;")
        ctrl_lay.addWidget(spacer)

        r_lay.addLayout(ctrl_lay)
        r_lay.addSpacing(10)

        # --- YENİ MANUEL KAYIT BÖLÜMÜ ---
        save_container = QFrame()
        save_container.setStyleSheet("background-color: rgba(245, 158, 11, 0.05); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px;")
        save_lay = QHBoxLayout(save_container)
        save_lay.setContentsMargins(16, 12, 16, 12)
        
        self.lbl_unsaved = QLabel("Kaydedilmeyen Çalışma: 00:00")
        self.lbl_unsaved.setStyleSheet("color: #fcd34d; font-weight: bold; font-size: 13px; border: none; background: transparent;")
        
        self.btn_save_time = QPushButton("💾 Süreyi Kaydet")
        self.btn_save_time.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_save_time.setStyleSheet("""
            QPushButton { background-color: #f59e0b; color: #0c0a09; border-radius: 6px; padding: 6px 14px; font-weight: bold; border: none; font-size: 12px; }
            QPushButton:hover { background-color: #fbbf24; }
        """)
        self.btn_save_time.clicked.connect(self.save_accumulated_time)
        
        save_lay.addWidget(self.lbl_unsaved)
        save_lay.addStretch()
        save_lay.addWidget(self.btn_save_time)
        
        r_lay.addWidget(save_container)
        r_lay.addStretch(1)

        lay.addWidget(left_panel)
        lay.addWidget(right_panel, stretch=1)
        
        self.apply_timer_settings()

        return tab

    # =========================================================================
    # POMODORO MOTOR MANTIĞI VE MANUEL KAYIT
    # =========================================================================
    def restore_timer_defaults(self):
        try: play_action_sound("click")
        except: pass
        self.slider_work.setValue(25)
        self.slider_short.setValue(5)
        self.slider_long.setValue(15)
        self.slider_rounds.setValue(4)
        self.apply_timer_settings()

    def _on_apply_clicked(self):
        try: play_action_sound("save")
        except: pass
        self.apply_timer_settings()

    def apply_timer_settings(self):
        self.work_time = self.slider_work.value() * 60
        self.short_break_time = self.slider_short.value() * 60
        self.long_break_time = self.slider_long.value() * 60
        self.total_rounds = self.slider_rounds.value()
        
        self.timer.stop()
        self.is_timer_running = False
        
        icon_play = os.path.join("resources", "icons", "play.ico")
        self.btn_timer_play.setIcon(self.get_tinted_icon(icon_play, "#ffffff"))
        
        self.pomodoro_state = "WORK"
        self.current_round = 1
        self._update_timer_ui_from_state()

    def _update_timer_ui_from_state(self):
        self.lbl_session.setText(f"{self.current_round}/{self.total_rounds}\nOTURUM")
        
        if self.pomodoro_state == "WORK":
            self.current_total_time = self.work_time
            self.current_time_left = self.work_time
            color = "#38bdf8" 
            text = "ÇALIŞMA"
        elif self.pomodoro_state == "SHORT_BREAK":
            self.current_total_time = self.short_break_time
            self.current_time_left = self.short_break_time
            color = "#10b981" 
            text = "KISA MOLA"
        else:
            self.current_total_time = self.long_break_time
            self.current_time_left = self.long_break_time
            color = "#14b8a6" 
            text = "UZUN MOLA"

        self.glow_effect.setColor(QColor(color))
        self.circular_timer.update_state(self.current_time_left, self.current_total_time, color, text)

    def toggle_pomodoro(self):
        try: play_action_sound("click")
        except: pass
        
        if self.current_time_left <= 0: return

        icon_play = os.path.join("resources", "icons", "play.ico")
        icon_pause = os.path.join("resources", "icons", "pause.ico")

        if self.is_timer_running:
            self.timer.stop()
            self.is_timer_running = False
            self.btn_timer_play.setIcon(self.get_tinted_icon(icon_play, "#ffffff"))
        else:
            self.timer.start(1000)
            self.is_timer_running = True
            self.btn_timer_play.setIcon(self.get_tinted_icon(icon_pause, "#ffffff"))

    def reset_timer_phase(self):
        try: play_action_sound("click")
        except: pass
        
        self.timer.stop()
        self.is_timer_running = False
        
        icon_play = os.path.join("resources", "icons", "play.ico")
        self.btn_timer_play.setIcon(self.get_tinted_icon(icon_play, "#ffffff"))
        
        self._update_timer_ui_from_state()

    def skip_timer_phase(self):
        try: play_action_sound("click")
        except: pass
        self.advance_pomodoro_state()

    def advance_pomodoro_state(self):
        self.timer.stop()
        self.is_timer_running = False
        
        icon_play = os.path.join("resources", "icons", "play.ico")
        self.btn_timer_play.setIcon(self.get_tinted_icon(icon_play, "#ffffff"))

        if self.pomodoro_state == "WORK":
            if self.current_round >= self.total_rounds:
                self.pomodoro_state = "LONG_BREAK"
            else:
                self.pomodoro_state = "SHORT_BREAK"
        elif self.pomodoro_state == "SHORT_BREAK":
            self.current_round += 1
            self.pomodoro_state = "WORK"
        elif self.pomodoro_state == "LONG_BREAK":
            self.current_round = 1
            self.pomodoro_state = "WORK"

        self._update_timer_ui_from_state()

    def timer_tick(self):
        if self.current_time_left > 0:
            self.current_time_left -= 1
            self.circular_timer.update_state(self.current_time_left, self.current_total_time, None, self.circular_timer.mode_text)
            
            # Sadece çalışma modunda süreyi arka planda biriktirir (OTOMATİK KAYDETMEZ)
            if self.pomodoro_state == "WORK":
                self.unsaved_study_seconds += 1
                self.update_unsaved_label()
        else:
            self.timer.stop()
            self.is_timer_running = False
            
            title = "Çalışma Bitti!" if self.pomodoro_state == "WORK" else "Mola Bitti!"
            msg = "Mola zamanı geldi, dinlen." if self.pomodoro_state == "WORK" else "Tekrar odaklanma vakti, hadi başlayalım."
            color = "#10b981" if self.pomodoro_state == "WORK" else "#38bdf8"
            
            if self.main_window and hasattr(self.main_window, 'send_tray_notification'):
                self.main_window.send_tray_notification(title, msg, color=color, sound_key="sound_pomodoro")
            
            self.advance_pomodoro_state()

    def update_unsaved_label(self):
        m, s = divmod(self.unsaved_study_seconds, 60)
        self.lbl_unsaved.setText(f"Kaydedilmeyen Çalışma: {m:02d}:{s:02d}")

    def save_accumulated_time(self):
        if self.unsaved_study_seconds <= 0:
            return
            
        try: play_action_sound("save")
        except: pass
        
        if not self.main_window or not hasattr(self.main_window, "db"): return
        
        try:
            with self.main_window.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO study_time_logs (log_date, seconds, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(log_date) DO UPDATE SET
                        seconds = seconds + ?,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (date.today().isoformat(), self.unsaved_study_seconds, self.unsaved_study_seconds),
                )
                conn.commit()
                
            saved_mins = self.unsaved_study_seconds // 60
            self.unsaved_study_seconds = 0
            self.update_unsaved_label()
            
            # Dashboard'u tetikler
            bus.study_time_changed.emit()
            
            if hasattr(self.main_window, 'send_tray_notification'):
                self.main_window.send_tray_notification(
                    "Süre Kaydedildi! 💾", 
                    f"Tebrikler, {saved_mins} dakikalık çalışma süresi Dashboard'a eklendi.", 
                    color="#f59e0b", 
                    sound_key="sound_success"
                )
        except Exception:
            pass