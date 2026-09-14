import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QSizePolicy, QComboBox, QLineEdit, QPushButton, QLabel,
    QStackedWidget, QFrame
)
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile, QWebEnginePage

VAULT_DIR = "vault_storage"

class CustomWebEngineView(QWebEngineView):
    def createWindow(self, _type):
        return self

class UniversityView(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        if not os.path.exists(VAULT_DIR):
            os.makedirs(VAULT_DIR)
            
        self.obs_list = {
            "Ankara Üniversitesi (OBS)": "https://obs.ankara.edu.tr/",
            "Orta Doğu Teknik Üniversitesi (ODTÜ)": "https://student.metu.edu.tr/",
            "İstanbul Teknik Üniversitesi (İTÜ)": "https://kepler-beta.itu.edu.tr/",
            "Boğaziçi Üniversitesi": "https://registration.boun.edu.tr/",
            "Hacettepe Üniversitesi (BİLSİS)": "https://bilsis.hacettepe.edu.tr/",
            "Gazi Üniversitesi": "https://obs.gazi.edu.tr/",
            "Yıldız Teknik Üniversitesi": "https://obs.yildiz.edu.tr/",
            "Ege Üniversitesi": "https://kimlik.ege.edu.tr/",
            "Farklı Bir Üniversite (URL Girin)": "https://"
        }

        self.mail_list = {
            "Microsoft Outlook (Üniversitelerin Çoğu)": "https://outlook.office365.com/mail/",
            "Google Workspace (Öğrenci Gmail)": "https://mail.google.com/",
            "Farklı Webmail (URL Girin)": "https://"
        }

        self.is_offline = False
        
        # Zorlu Dönem (Auto-Retry) Zamanlayıcısı
        self.retry_timer = QTimer(self)
        self.retry_timer.setInterval(5000) # Spam yememek için güvenli bekleme süresi (5 saniye)
        self.retry_timer.timeout.connect(self.check_and_reload_obs)
        self.is_retrying = False

        self.init_ui()

        self.net_timer = QTimer(self)
        self.net_timer.timeout.connect(self.check_network_status)
        self.net_timer.start(2000)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_obs_tab(), "🎓 OBS (Öğrenci Bilgi Sistemi)")
        self.tabs.addTab(self.create_mail_tab(), "📧 Öğrenci E-Posta")
        layout.addWidget(self.tabs)
        
        self.check_network_status()

    def check_network_status(self):
        try:
            main_win = self.window()
            if hasattr(main_win, 'is_online_state'):
                connected = main_win.is_online_state
            else:
                from core.network import check_internet_connection
                connected = check_internet_connection()
                
            new_status = not connected
            if self.is_offline != new_status:
                self.is_offline = new_status
                index = 1 if self.is_offline else 0
                
                if hasattr(self, 'obs_stack'):
                    self.obs_stack.setCurrentIndex(index)
                if hasattr(self, 'mail_stack'):
                    self.mail_stack.setCurrentIndex(index)
                    
                # Eğer internet giderse Zorlu Dönem modunu otomatik durdur
                if self.is_offline and self.is_retrying:
                    self.toggle_retry_mode()
        except Exception:
            pass

    def create_offline_widget(self):
        offline_widget = QFrame()
        offline_widget.setStyleSheet("QFrame { background-color: #0c0a09; border-radius: 8px; }")
        off_lay = QVBoxLayout(offline_widget)
        off_lay.setAlignment(Qt.AlignCenter)
        
        lbl_off_title = QHBoxLayout()
        lbl_off_title.setAlignment(Qt.AlignCenter)
        lbl_icon = QLabel("🔌")
        lbl_icon.setStyleSheet("font-size: 28px; background: transparent;")
        lbl_text = QLabel("Çevrimdışısınız")
        lbl_text.setStyleSheet("font-size: 28px; font-weight: bold; color: #ef4444; background: transparent;")
        lbl_off_title.addWidget(lbl_icon)
        lbl_off_title.addWidget(lbl_text)

        lbl_desc = QLabel("Üniversite sistemlerine (OBS ve E-Posta) bağlanabilmek için aktif\nbir internet bağlantısı gereklidir.\nLütfen internet bağlantınızı kontrol edip tekrar deneyin.")
        lbl_desc.setStyleSheet("color: #a1a1aa; font-size: 15px; line-height: 1.5; background: transparent;")
        lbl_desc.setAlignment(Qt.AlignCenter)
        
        off_lay.addStretch()
        off_lay.addLayout(lbl_off_title)
        off_lay.addSpacing(16)
        off_lay.addWidget(lbl_desc)
        off_lay.addStretch()
        return offline_widget

    def create_obs_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)

        top_bar = QHBoxLayout()
        
        lbl = QLabel("Üniversite Seç:")
        lbl.setStyleSheet("font-weight: bold; color: #a1a1aa;")
        top_bar.addWidget(lbl)

        self.obs_combo = QComboBox()
        self.obs_combo.addItems(self.obs_list.keys())
        self.obs_combo.setFixedHeight(34)
        self.obs_combo.setStyleSheet("background-color: #27272a; border-radius: 6px; padding-left: 8px; color: white; font-weight: bold;")
        self.obs_combo.currentIndexChanged.connect(self.update_obs_url)
        top_bar.addWidget(self.obs_combo, stretch=2)

        self.obs_url = QLineEdit()
        self.obs_url.setFixedHeight(34)
        self.obs_url.setStyleSheet("background-color: rgba(128,128,128,0.1); border: 1px solid #3f3f46; border-radius: 6px; padding-left: 10px;")
        top_bar.addWidget(self.obs_url, stretch=3)

        btn_go = QPushButton("Bağlan")
        btn_go.setFixedHeight(34)
        btn_go.setCursor(QCursor(Qt.PointingHandCursor))
        btn_go.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; border-radius: 6px; padding: 0 20px;")
        btn_go.clicked.connect(self.load_obs_url)
        top_bar.addWidget(btn_go)

        # ZORLU DÖNEM BUTONU
        self.btn_retry = QPushButton("🚀 Zorlu Dönem")
        self.btn_retry.setFixedHeight(34)
        self.btn_retry.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_retry.setStyleSheet("background-color: #f59e0b; color: #12100e; font-weight: bold; border-radius: 6px; padding: 0 15px;")
        self.btn_retry.setToolTip("Sistem çöktüğünde veya yoğunluktan açılmadığında otomatik bağlanmayı dener.")
        self.btn_retry.clicked.connect(self.toggle_retry_mode)
        top_bar.addWidget(self.btn_retry)

        lay.addLayout(top_bar)

        self.obs_stack = QStackedWidget()

        self.obs_webview = CustomWebEngineView()
        self.obs_webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        profile_path = os.path.join(os.getcwd(), VAULT_DIR, "uni_obs_profile")
        if not os.path.exists(profile_path):
            os.makedirs(profile_path)

        self.obs_profile = QWebEngineProfile("UniOBSProfile", self.obs_webview)
        self.obs_profile.setPersistentStoragePath(profile_path)
        self.obs_profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        
        settings = self.obs_profile.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

        self.obs_page = QWebEnginePage(self.obs_profile, self.obs_webview)
        self.obs_webview.setPage(self.obs_page)
        
        # Sayfa yüklenmesi bittiğinde başarılı olup olmadığını kontrol et
        self.obs_webview.loadFinished.connect(self.on_obs_load_finished)
        
        self.obs_stack.addWidget(self.obs_webview)
        self.obs_stack.addWidget(self.create_offline_widget())
        lay.addWidget(self.obs_stack)
        
        self.obs_combo.setCurrentText("Ankara Üniversitesi (OBS)")
        self.update_obs_url()
        self.load_obs_url()

        return tab

    # =========================================================================
    # ZORLU DÖNEM MANTIĞI (AUTO-RETRY)
    # =========================================================================
    def toggle_retry_mode(self):
        self.is_retrying = not self.is_retrying
        
        if self.is_retrying:
            if self.is_offline:
                self.is_retrying = False
                main_win = self.window()
                if hasattr(main_win, 'send_tray_notification'):
                    main_win.send_tray_notification("Hata ⚠️", "Çevrimdışıyken Zorlu Dönem modu başlatılamaz.", color="#ef4444")
                return
                
            self.btn_retry.setText("🛑 Durdur (Deneniyor...)")
            self.btn_retry.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; border-radius: 6px; padding: 0 15px;")
            self.retry_timer.start()
            self.obs_webview.reload()
            
            main_win = self.window()
            if hasattr(main_win, 'send_tray_notification'):
                main_win.send_tray_notification("Zorlu Dönem Aktif 🚀", "OBS sistemi çökükse bile 5 saniyede bir otomatik denenecek.", color="#f59e0b")
        else:
            self.btn_retry.setText("🚀 Zorlu Dönem")
            self.btn_retry.setStyleSheet("background-color: #f59e0b; color: #12100e; font-weight: bold; border-radius: 6px; padding: 0 15px;")
            self.retry_timer.stop()

    def check_and_reload_obs(self):
        # Eğer sayfa yüklenemiyorsa (veya beyaz/hata sayfasındaysa) otomatik yenilemeye devam et
        if self.main_stack.currentIndex() == 1 and self.is_retrying:
            self.obs_webview.reload()

    def on_obs_load_finished(self, success):
        if not self.is_retrying:
            return
            
        # Eğer sayfa HTTP hataları olmadan başarıyla yüklendiyse ve zorlu dönem modundaysak
        if success:
            # Sayfanın başlığını kontrol ederek gerçek bir giriş sayfası mı yoksa "502 Bad Gateway" veya çökme ekranı mı olduğunu kontrol et
            title = self.obs_webview.title().lower()
            if "error" not in title and "gateway" not in title and "timeout" not in title and "ulaşılamıyor" not in title:
                # Başarılı bir şekilde giriş sayfasına ulaştı
                self.toggle_retry_mode() # Yenilemeyi durdur
                main_win = self.window()
                if hasattr(main_win, 'send_tray_notification'):
                    main_win.send_tray_notification("Giriş Başarılı! ✅", "Zorlu dönem atlatıldı, OBS sistemine başarıyla ulaşıldı.", color="#10b981")


    # =========================================================================
    # DİĞER FONKSİYONLAR (DEĞİŞTİRİLMEDİ)
    # =========================================================================
    def update_obs_url(self):
        uni_name = self.obs_combo.currentText()
        url = self.obs_list.get(uni_name, "https://")
        self.obs_url.setText(url)

    def load_obs_url(self):
        self.check_network_status()
        url = self.obs_url.text().strip()
        if url:
            self.obs_webview.setUrl(QUrl(url))

    def create_mail_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)

        top_bar = QHBoxLayout()
        
        lbl = QLabel("Altyapı Seç:")
        lbl.setStyleSheet("font-weight: bold; color: #a1a1aa;")
        top_bar.addWidget(lbl)

        self.mail_combo = QComboBox()
        self.mail_combo.addItems(self.mail_list.keys())
        self.mail_combo.setFixedHeight(34)
        self.mail_combo.setStyleSheet("background-color: #27272a; border-radius: 6px; padding-left: 8px; color: white; font-weight: bold;")
        self.mail_combo.currentIndexChanged.connect(self.update_mail_url)
        top_bar.addWidget(self.mail_combo, stretch=2)

        self.mail_url = QLineEdit()
        self.mail_url.setFixedHeight(34)
        self.mail_url.setStyleSheet("background-color: rgba(128,128,128,0.1); border: 1px solid #3f3f46; border-radius: 6px; padding-left: 10px;")
        top_bar.addWidget(self.mail_url, stretch=3)

        btn_go = QPushButton("Giriş Yap")
        btn_go.setFixedHeight(34)
        btn_go.setCursor(QCursor(Qt.PointingHandCursor))
        btn_go.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; border-radius: 6px; padding: 0 20px;")
        btn_go.clicked.connect(self.load_mail_url)
        top_bar.addWidget(btn_go)

        lay.addLayout(top_bar)

        self.mail_stack = QStackedWidget()

        self.mail_webview = CustomWebEngineView()
        self.mail_webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        profile_path = os.path.join(os.getcwd(), VAULT_DIR, "uni_mail_profile")
        if not os.path.exists(profile_path):
            os.makedirs(profile_path)

        self.mail_profile = QWebEngineProfile("UniMailProfile", self.mail_webview)
        self.mail_profile.setPersistentStoragePath(profile_path)
        self.mail_profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        
        settings = self.mail_profile.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

        self.mail_page = QWebEnginePage(self.mail_profile, self.mail_webview)
        self.mail_webview.setPage(self.mail_page)

        self.mail_stack.addWidget(self.mail_webview)
        self.mail_stack.addWidget(self.create_offline_widget())
        lay.addWidget(self.mail_stack)

        self.mail_combo.setCurrentText("Microsoft Outlook (Üniversitelerin Çoğu)")
        self.update_mail_url()
        self.load_mail_url()

        return tab

    def update_mail_url(self):
        mail_name = self.mail_combo.currentText()
        url = self.mail_list.get(mail_name, "https://")
        self.mail_url.setText(url)

    def load_mail_url(self):
        self.check_network_status()
        url = self.mail_url.text().strip()
        if url:
            self.mail_webview.setUrl(QUrl(url))