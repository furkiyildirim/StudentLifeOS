import os
import shutil
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QLineEdit, QComboBox,
    QMessageBox, QFrame, QFileDialog, QCheckBox, QDateEdit, QSpinBox
)
from PySide6.QtCore import Qt, QSize, QDate
from PySide6.QtGui import QCursor, QPixmap, QColor

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from core.events import bus
from core.sound import play_action_sound

COVERS_DIR = os.path.join("resources", "covers")
VAULT_DIR = "vault_storage"

class BookCard(QFrame):
    def __init__(self, data, parent_view):
        super().__init__()
        self.data = data
        self.parent_view = parent_view
        self.setObjectName("Card")
        # Kartın ekranın tamamını (%100) kaplamasını sağlayan, ferah CSS tasarımı
        self.setStyleSheet("""
            QFrame#Card {
                background-color: #171412;
                border: 1px solid #292524;
                border-radius: 12px;
            }
            QFrame#Card:hover {
                border-color: #3f3f46;
                background-color: #1c1917;
            }
        """)
        self.init_ui()

    def init_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(20)

        # 1. Kapak Görseli (Boyutu ve netliği artırıldı)
        self.lbl_cover = QLabel()
        self.lbl_cover.setFixedSize(85, 125)
        self.lbl_cover.setStyleSheet("background-color: #27272a; border-radius: 6px; border: 1px solid #3f3f46;")
        self.lbl_cover.setAlignment(Qt.AlignCenter)
        
        cover_path = self.data.get("cover_path")
        if cover_path and os.path.exists(cover_path):
            pixmap = QPixmap(cover_path)
            self.lbl_cover.setPixmap(pixmap.scaled(85, 125, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else:
            self.lbl_cover.setText("📖")
            self.lbl_cover.setStyleSheet("background-color: #27272a; font-size: 32px; border-radius: 6px; border: 1px solid #3f3f46;")
        
        lay.addWidget(self.lbl_cover)

        # 2. Orta Bilgi Alanı (Başlık, Yazar, Sayfa, Rozetler)
        info_lay = QVBoxLayout()
        info_lay.setSpacing(6)
        
        lbl_title = QLabel(self.data["title"])
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        lbl_title.setWordWrap(True)
        
        lbl_author = QLabel(self.data.get("author") or "Bilinmeyen Yazar")
        lbl_author.setStyleSheet("font-size: 14px; color: #a1a1aa; font-weight: 500;")
        
        lbl_pages = QLabel(f"{self.data.get('page_count', 0)} Sayfa")
        lbl_pages.setStyleSheet("font-size: 12px; color: #71717a;")
        
        info_lay.addWidget(lbl_title)
        info_lay.addWidget(lbl_author)
        info_lay.addWidget(lbl_pages)
        info_lay.addStretch()

        # --- ROZETLER ---
        badges_lay = QHBoxLayout()
        badges_lay.setSpacing(10)
        
        genre = self.data.get("genre") or "Diğer"
        lbl_genre = QLabel(genre)
        lbl_genre.setStyleSheet("background-color: #3b1d68; color: #d8b4fe; font-size: 11px; font-weight: bold; padding: 5px 12px; border-radius: 6px;")
        badges_lay.addWidget(lbl_genre)
        
        status = self.data.get("status") or "Okunacak"
        status_colors = {
            "Okunacak": ("rgba(245, 158, 11, 0.15)", "#f59e0b", "#f59e0b"),   
            "Okunuyor": ("rgba(56, 189, 248, 0.15)", "#38bdf8", "#38bdf8"),   
            "Okundu":   ("rgba(16, 185, 129, 0.15)", "#10b981", "#10b981")    
        }
        bg_col, fg_col, border_col = status_colors.get(status, ("#27272a", "#ffffff", "#3f3f46"))
        
        lbl_status = QLabel(status)
        lbl_status.setStyleSheet(f"background-color: {bg_col}; color: {fg_col}; font-size: 11px; font-weight: bold; padding: 5px 12px; border-radius: 6px; border: 1px solid {border_col};")
        badges_lay.addWidget(lbl_status)
        
        active_return_event = self.has_active_return_event(self.data.get('title'))
        
        if self.data.get("is_borrowed"):
            if active_return_event:
                return_dt_str = self.data.get('return_date', '')
                try:
                    dt_obj = QDate.fromString(return_dt_str, "yyyy-MM-dd")
                    formatted_date = dt_obj.toString("dd.MM.yyyy")
                except:
                    formatted_date = return_dt_str
                    
                lbl_borrow = QLabel(f"⏳ İade: {formatted_date}")
                lbl_borrow.setStyleSheet("background-color: rgba(244, 63, 94, 0.15); color: #f43f5e; font-size: 11px; font-weight: bold; padding: 5px 12px; border-radius: 6px; border: 1px solid #f43f5e;")
                badges_lay.addWidget(lbl_borrow)
            else:
                lbl_borrow = QLabel("✅ İade Edildi / Teslim")
                lbl_borrow.setStyleSheet("background-color: rgba(16, 185, 129, 0.15); color: #10b981; font-size: 11px; font-weight: bold; padding: 5px 12px; border-radius: 6px; border: 1px solid #10b981;")
                badges_lay.addWidget(lbl_borrow)

        badges_lay.addStretch()
        info_lay.addLayout(badges_lay)
        
        # stretch=1 diyerek orta alanın kart sağa doğru uzadıkça esnemesini (butonların en sağa itilmesini) sağlıyoruz.
        lay.addLayout(info_lay, stretch=1)

        # 3. Sağ Taraf İşlem Butonları (Tamamen hizalandı, sıkışıklık önlendi)
        right_panel_lay = QVBoxLayout()
        right_panel_lay.setSpacing(8)
        right_panel_lay.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        btn_style_primary = "font-weight: bold; border-radius: 6px; padding: 8px 16px; font-size: 13px; min-width: 140px;"
        btn_style_secondary = "font-weight: bold; border-radius: 6px; padding: 6px 12px; font-size: 12px;"

        if status == "Okunacak":
            btn_start_read = QPushButton("📖 Okumaya Başla")
            btn_start_read.setCursor(QCursor(Qt.PointingHandCursor))
            btn_start_read.setStyleSheet(f"background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #0284c7; {btn_style_primary}")
            btn_start_read.clicked.connect(lambda: self.parent_view.change_book_status(self.data["id"], self.data["title"], "Okunuyor"))
            right_panel_lay.addWidget(btn_start_read)
            
        elif status == "Okunuyor":
            btn_mark_read = QPushButton("✅ Okundu Yap")
            btn_mark_read.setCursor(QCursor(Qt.PointingHandCursor))
            btn_mark_read.setStyleSheet(f"background-color: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #10b981; {btn_style_primary}")
            btn_mark_read.clicked.connect(lambda: self.parent_view.change_book_status(self.data["id"], self.data["title"], "Okundu"))
            right_panel_lay.addWidget(btn_mark_read)
        
        if self.data.get("is_borrowed") and active_return_event:
            btn_return = QPushButton("📥 İade Et")
            btn_return.setCursor(QCursor(Qt.PointingHandCursor))
            btn_return.setStyleSheet(f"background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #0284c7; {btn_style_primary}")
            btn_return.clicked.connect(lambda: self.parent_view.return_borrowed_book(self.data["id"], self.data["title"]))
            right_panel_lay.addWidget(btn_return)
            
        pdf_path = self.data.get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            btn_pdf = QPushButton("📕 PDF'i Aç")
            btn_pdf.setCursor(QCursor(Qt.PointingHandCursor))
            btn_pdf.setStyleSheet(f"background-color: #e11d48; color: white; {btn_style_primary}")
            btn_pdf.clicked.connect(lambda: self.parent_view.open_pdf_in_vault(pdf_path))
            right_panel_lay.addWidget(btn_pdf)
            
        right_panel_lay.addStretch()

        action_lay = QHBoxLayout()
        action_lay.setSpacing(8)
        
        btn_edit = QPushButton("✏️ Düzenle")
        btn_edit.setCursor(QCursor(Qt.PointingHandCursor))
        btn_edit.setStyleSheet(f"background-color: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; {btn_style_secondary}")
        btn_edit.clicked.connect(lambda: self.parent_view.dialog_add_edit_book(self.data))
        
        btn_delete = QPushButton("🗑 Sil")
        btn_delete.setCursor(QCursor(Qt.PointingHandCursor))
        btn_delete.setStyleSheet(f"background-color: transparent; color: #f87171; border: 1px solid transparent; {btn_style_secondary}")
        btn_delete.clicked.connect(lambda: self.parent_view.delete_book(self.data["id"]))
        
        action_lay.addWidget(btn_edit)
        action_lay.addWidget(btn_delete)
        
        right_panel_lay.addLayout(action_lay)
        lay.addLayout(right_panel_lay)

    def has_active_return_event(self, title):
        with self.parent_view.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM calendar_events WHERE title LIKE ? AND category = 'Kitap İade' AND is_completed = 0", 
                (f"Kitap İadesi: {title}%",)
            )
            row = cur.fetchone()
            return row is not None


class LibraryView(QWidget):
    def __init__(self, db, main_window):
        super().__init__()
        self.db = db
        self.main_window = main_window
        
        if not os.path.exists(COVERS_DIR):
            os.makedirs(COVERS_DIR)
        if not os.path.exists(VAULT_DIR):
            os.makedirs(VAULT_DIR)
            
        self.setup_tables()
        self.init_ui()
        
        bus.calendar_changed.connect(self.load_books)

    def setup_tables(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT,
                    genre TEXT,
                    status TEXT,
                    cover_path TEXT,
                    pdf_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try: cur.execute("ALTER TABLE books ADD COLUMN is_borrowed INTEGER DEFAULT 0")
            except: pass
            try: cur.execute("ALTER TABLE books ADD COLUMN return_location TEXT")
            except: pass
            try: cur.execute("ALTER TABLE books ADD COLUMN return_date TEXT")
            except: pass
            try: cur.execute("ALTER TABLE books ADD COLUMN page_count INTEGER DEFAULT 0")
            except: pass
            
            conn.commit()

    def init_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(24, 24, 24, 24)
        main_lay.setSpacing(16)

        header_lay = QHBoxLayout()
        
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("📚 Kitaplığım")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        lbl_desc = QLabel("Okuduğunuz veya okuyacağınız kitapları, e-kitap (PDF) arşivinizi buradan yönetin.")
        lbl_desc.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_desc)
        header_lay.addLayout(title_box)
        header_lay.addStretch()

        btn_add = QPushButton("➕ Yeni Kitap Ekle")
        btn_add.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add.setStyleSheet("""
            QPushButton { background-color: #0ea5e9; color: #f0f9ff; border-radius: 8px; padding: 10px 16px; font-size: 13px; font-weight: 800; border: none; }
            QPushButton:hover { background-color: #38bdf8; }
        """)
        btn_add.clicked.connect(lambda: self.dialog_add_edit_book())
        header_lay.addWidget(btn_add)
        
        main_lay.addLayout(header_lay)

        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)
        
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("🔍 Kitap veya yazar ara...")
        self.search_in.setFixedHeight(36)
        self.search_in.setStyleSheet("background-color: #171412; border: 1px solid #3f3f46; border-radius: 6px; padding: 0 10px; color: white;")
        self.search_in.textChanged.connect(self.load_books)
        
        self.filter_status = QComboBox()
        self.filter_status.addItems(["Tüm Durumlar", "Okunacak", "Okunuyor", "Okundu"])
        self.filter_status.setFixedHeight(36)
        self.filter_status.setStyleSheet("background-color: #171412; border: 1px solid #3f3f46; border-radius: 6px; padding: 0 10px; color: white; font-weight: bold;")
        self.filter_status.currentTextChanged.connect(self.load_books)

        self.filter_genre = QComboBox()
        self.genres = ["Tüm Türler", "Roman", "Bilim Kurgu / Fantastik", "Tarih", "Kişisel Gelişim", "Biyografi", "Felsefe", "Psikoloji", "Akademik", "Şiir", "Diğer"]
        self.filter_genre.addItems(self.genres)
        self.filter_genre.setFixedHeight(36)
        self.filter_genre.setStyleSheet("background-color: #171412; border: 1px solid #3f3f46; border-radius: 6px; padding: 0 10px; color: white; font-weight: bold;")
        self.filter_genre.currentTextChanged.connect(self.load_books)

        filter_bar.addWidget(self.search_in, stretch=2)
        filter_bar.addWidget(self.filter_status, stretch=1)
        filter_bar.addWidget(self.filter_genre, stretch=1)
        main_lay.addLayout(filter_bar)

        # --- YENİ LİSTE YAPISI: Yüzde Yüz Ekranı Kaplayan Dikey Liste ---
        self.books_list = QListWidget()
        self.books_list.setSpacing(14)
        self.books_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { background: transparent; outline: none; border: none; }
            QListWidget::item:selected { background: transparent; border: none; outline: none; }
            QScrollBar:vertical { background: #171412; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #3f3f46; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #38bdf8; }
        """)
        main_lay.addWidget(self.books_list)

        self.load_books()

    def load_books(self):
        self.books_list.clear()

        search_q = self.search_in.text().strip()
        f_status = self.filter_status.currentText()
        f_genre = self.filter_genre.currentText()

        query = "SELECT * FROM books WHERE 1=1"
        params = []

        if search_q:
            query += " AND (title LIKE ? OR author LIKE ?)"
            params.extend([f"%{search_q}%", f"%{search_q}%"])
        if f_status != "Tüm Durumlar":
            query += " AND status = ?"
            params.append(f_status)
        if f_genre != "Tüm Türler":
            query += " AND genre = ?"
            params.append(f_genre)
            
        # Önceliklendirme: Önce okunanlar, sonra okunacaklar, en son okunanlar
        query += " ORDER BY CASE status WHEN 'Okunuyor' THEN 1 WHEN 'Okunacak' THEN 2 WHEN 'Okundu' THEN 3 ELSE 4 END, id DESC"

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            books = cur.fetchall()

        for b in books:
            card = BookCard(dict(b), self)
            
            item = QListWidgetItem()
            # Genişliği 0 bırakarak %100 yatay esnemesini, Yüksekliğini ise 180px sabit olmasını sağlıyoruz
            item.setSizeHint(QSize(0, 180)) 
            
            self.books_list.addItem(item)
            self.books_list.setItemWidget(item, card)

        if not books:
            empty = QListWidgetItem("Aradığınız kriterlere uygun kitap bulunamadı.")
            empty.setForeground(QColor("#71717a"))
            empty.setTextAlignment(Qt.AlignCenter)
            self.books_list.addItem(empty)

    def change_book_status(self, b_id: int, title: str, new_status: str):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE books SET status = ? WHERE id = ?", (new_status, b_id))
            conn.commit()
            
        try: play_action_sound("complete")
        except: pass
        
        if new_status == "Okundu":
            bus.item_saved.emit(f"Tebrikler! '{title}' kitabını bitirdiniz.")
        elif new_status == "Okunuyor":
            bus.item_saved.emit(f"'{title}' kitabını okumaya başladınız. İyi okumalar!")
            
        self.load_books()
        
        if hasattr(self.main_window, "dashboard_view"):
            self.main_window.dashboard_view.refresh()

    def return_borrowed_book(self, b_id: int, title: str):
        confirm = QMessageBox.question(
            self, "İade Onayı", 
            f"'{title}' adlı kitabı iade ettiniz mi?\nTakvimdeki hatırlatıcı görev kalıcı olarak silinecektir.", 
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                event_title = f"Kitap İadesi: {title}%"
                cur.execute("DELETE FROM calendar_events WHERE title LIKE ?", (event_title,))
                conn.commit()
            
            try:
                play_action_sound("complete")
            except: pass
            
            bus.calendar_changed.emit()
            try:
                bus.item_deleted.emit(f"'{title}' kitabının iade görevi başarıyla tamamlandı ve silindi.")
            except: pass
            
            self.load_books()
            
            if hasattr(self.main_window, "dashboard_view"):
                self.main_window.dashboard_view.refresh()

    def dialog_add_edit_book(self, book_data=None):
        is_edit = book_data is not None
        dlg = QDialog(self)
        dlg.setWindowTitle("Kitabı Düzenle" if is_edit else "Yeni Kitap Ekle")
        dlg.resize(400, 590)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)

        title_in = QLineEdit(book_data["title"] if is_edit else "")
        title_in.setPlaceholderText("Kitap Adı")
        
        author_in = QLineEdit(book_data["author"] if is_edit and book_data["author"] else "")
        author_in.setPlaceholderText("Yazar Adı")

        genre_cb = QComboBox()
        genre_cb.addItems(self.genres[1:]) 
        if is_edit and book_data.get("genre"):
            genre_cb.setCurrentText(book_data["genre"])

        status_cb = QComboBox()
        status_cb.addItems(["Okunacak", "Okunuyor", "Okundu"])
        if is_edit and book_data.get("status"):
            status_cb.setCurrentText(book_data["status"])
            
        page_count_in = QSpinBox()
        page_count_in.setRange(0, 10000)
        page_count_in.setSuffix(" Sayfa")
        page_count_in.setStyleSheet("background-color: #171412; border: 1px solid #3f3f46; color: white; padding: 4px; border-radius: 4px;")
        if is_edit and book_data.get("page_count"):
            page_count_in.setValue(int(book_data["page_count"]))

        self.chk_borrowed = QCheckBox("Bu kitabı ödünç aldım (İade edilecek)")
        self.chk_borrowed.setStyleSheet("color: #f43f5e; font-weight: bold;")
        if is_edit and book_data.get("is_borrowed"):
            self.chk_borrowed.setChecked(True)
            
        self.return_loc_in = QLineEdit(book_data.get("return_location") if is_edit and book_data.get("return_location") else "")
        self.return_loc_in.setPlaceholderText("Kime / Nereye teslim edilecek?")
        
        self.return_date_in = QDateEdit()
        self.return_date_in.setCalendarPopup(True)
        self.return_date_in.setDisplayFormat("dd.MM.yyyy")
        if is_edit and book_data.get("return_date"):
            try:
                self.return_date_in.setDate(QDate.fromString(book_data["return_date"], "yyyy-MM-dd"))
            except:
                self.return_date_in.setDate(QDate.currentDate().addDays(14))
        else:
            self.return_date_in.setDate(QDate.currentDate().addDays(14))

        self.borrow_widget = QWidget()
        b_lay = QVBoxLayout(self.borrow_widget)
        b_lay.setContentsMargins(0, 0, 0, 0)
        b_lay.setSpacing(6)
        b_lay.addWidget(QLabel("Teslim Edilecek Yer/Kişi:"))
        b_lay.addWidget(self.return_loc_in)
        b_lay.addWidget(QLabel("Teslim Tarihi:"))
        b_lay.addWidget(self.return_date_in)
        
        self.borrow_widget.setVisible(self.chk_borrowed.isChecked())
        self.chk_borrowed.toggled.connect(self.borrow_widget.setVisible)

        cover_lay = QHBoxLayout()
        cover_path_in = QLineEdit(book_data.get("cover_path") if is_edit else "")
        cover_path_in.setReadOnly(True)
        cover_path_in.setPlaceholderText("Kapak görseli (Opsiyonel)")
        btn_cover = QPushButton("Gözat")
        cover_lay.addWidget(cover_path_in)
        cover_lay.addWidget(btn_cover)

        pdf_lay = QHBoxLayout()
        pdf_path_in = QLineEdit(book_data.get("pdf_path") if is_edit else "")
        pdf_path_in.setReadOnly(True)
        pdf_path_in.setPlaceholderText("PDF e-kitap (Opsiyonel)")
        btn_pdf = QPushButton("Gözat")
        pdf_lay.addWidget(pdf_path_in)
        pdf_lay.addWidget(btn_pdf)

        def browse_cover():
            path, _ = QFileDialog.getOpenFileName(dlg, "Kapak Seç", "", "Görseller (*.png *.jpg *.jpeg)")
            if path: cover_path_in.setText(path)

        def browse_pdf():
            path, _ = QFileDialog.getOpenFileName(dlg, "PDF Seç", "", "PDF Dosyaları (*.pdf)")
            if path: pdf_path_in.setText(path)

        btn_cover.clicked.connect(browse_cover)
        btn_pdf.clicked.connect(browse_pdf)

        lay.addWidget(QLabel("Kitap Adı:"))
        lay.addWidget(title_in)
        
        row_lay1 = QHBoxLayout()
        row_lay1.addWidget(QLabel("Yazar:"))
        row_lay1.addWidget(author_in)
        lay.addLayout(row_lay1)
        
        row_lay2 = QHBoxLayout()
        row_lay2.addWidget(QLabel("Sayfa:"))
        row_lay2.addWidget(page_count_in)
        row_lay2.addWidget(QLabel("Tür:"))
        row_lay2.addWidget(genre_cb)
        lay.addLayout(row_lay2)
        
        lay.addWidget(QLabel("Durum:"))
        lay.addWidget(status_cb)
        
        lay.addWidget(self.chk_borrowed)
        lay.addWidget(self.borrow_widget)
        
        lay.addWidget(QLabel("Kapak Fotoğrafı:"))
        lay.addLayout(cover_lay)
        lay.addWidget(QLabel("E-Kitap (PDF):"))
        lay.addLayout(pdf_lay)
        lay.addStretch()

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("AccentButton")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        lay.addWidget(btn_save)

        def save():
            if not title_in.text().strip():
                QMessageBox.warning(dlg, "Uyarı", "Kitap adı boş bırakılamaz.")
                return

            c_path = cover_path_in.text()
            p_path = pdf_path_in.text()
            p_count = page_count_in.value()

            if p_path and p_path.lower().endswith(".pdf") and not c_path:
                if PYMUPDF_AVAILABLE:
                    try:
                        doc = fitz.open(p_path)
                        page = doc.load_page(0)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        cover_filename = f"pdf_cover_{random.randint(1000, 9999)}.png"
                        dest_cover = os.path.join(COVERS_DIR, cover_filename)
                        pix.save(dest_cover)
                        c_path = dest_cover
                    except Exception: pass

            if c_path and not c_path.startswith(COVERS_DIR):
                filename = f"book_{random.randint(1000, 9999)}_{os.path.basename(c_path)}"
                dest = os.path.join(COVERS_DIR, filename)
                try: shutil.copy2(c_path, dest); c_path = dest
                except: pass
                
            if p_path and not p_path.startswith(VAULT_DIR):
                filename = f"book_{random.randint(1000, 9999)}_{os.path.basename(p_path)}"
                dest = os.path.join(VAULT_DIR, filename)
                try: 
                    shutil.copy2(p_path, dest)
                    p_path = dest
                    with self.db.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO materials (course_id, file_name, file_path, file_type) VALUES (?, ?, ?, ?)",
                                    (None, f"{title_in.text().strip()} (E-Kitap)", p_path, "pdf"))
                        conn.commit()
                    if hasattr(self.main_window, "vault_view"):
                        self.main_window.vault_view.load_materials()
                except: pass

            is_borrow = 1 if self.chk_borrowed.isChecked() else 0
            r_loc = self.return_loc_in.text().strip() if is_borrow else ""
            r_date_iso = self.return_date_in.date().toString("yyyy-MM-dd") if is_borrow else ""

            with self.db.get_connection() as conn:
                cur = conn.cursor()
                if is_edit:
                    cur.execute("""
                        UPDATE books 
                        SET title=?, author=?, genre=?, status=?, cover_path=?, pdf_path=?, is_borrowed=?, return_location=?, return_date=?, page_count=?
                        WHERE id=?
                    """, (title_in.text().strip(), author_in.text().strip(), genre_cb.currentText(), 
                          status_cb.currentText(), c_path, p_path, is_borrow, r_loc, r_date_iso, p_count, book_data["id"]))
                else:
                    cur.execute("""
                        INSERT INTO books (title, author, genre, status, cover_path, pdf_path, is_borrowed, return_location, return_date, page_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (title_in.text().strip(), author_in.text().strip(), genre_cb.currentText(), 
                          status_cb.currentText(), c_path, p_path, is_borrow, r_loc, r_date_iso, p_count))
                conn.commit()

            if is_borrow and r_date_iso:
                event_title = f"Kitap İadesi: {title_in.text().strip()} ({r_loc})"
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM calendar_events WHERE title = ?", (event_title,))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO calendar_events (title, event_date, start_time, end_time, category, is_completed)
                            VALUES (?, ?, '09:00', '10:00', 'Kitap İade', 0)
                        """, (event_title, r_date_iso))
                        conn.commit()
                        bus.calendar_changed.emit()

            try:
                play_action_sound("save")
            except: pass
            dlg.accept()
            self.load_books()
            
            if hasattr(self.main_window, "dashboard_view"):
                self.main_window.dashboard_view.refresh()

        btn_save.clicked.connect(save)
        dlg.exec()

    def delete_book(self, b_id: int):
        confirm = QMessageBox.question(self, "Silme Onayı", "Bu kitabı kitaplığınızdan silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                row = cur.execute("SELECT title, return_location, cover_path, pdf_path FROM books WHERE id = ?", (b_id,)).fetchone()
                if row:
                    if row["cover_path"] and os.path.exists(row["cover_path"]):
                        try: os.remove(row["cover_path"])
                        except: pass
                    if row["pdf_path"] and os.path.exists(row["pdf_path"]):
                        try: os.remove(row["pdf_path"])
                        except: pass
                    
                    event_title = f"Kitap İadesi: {row['title']}%"
                    cur.execute("DELETE FROM calendar_events WHERE title LIKE ?", (event_title,))
                        
                cur.execute("DELETE FROM books WHERE id = ?", (b_id,))
                conn.commit()
                
            bus.calendar_changed.emit()
            try:
                play_action_sound("delete")
            except: pass
            self.load_books()
            
            if hasattr(self.main_window, "dashboard_view"):
                self.main_window.dashboard_view.refresh()

    def open_pdf_in_vault(self, pdf_path):
        if not hasattr(self.main_window, "vault_view"): return
        self.main_window.navigate_to(4)
        vault = self.main_window.vault_view
        vault.course_filter_cb.blockSignals(True)
        vault.course_filter_cb.setCurrentIndex(0) 
        vault.course_filter_cb.blockSignals(False)
        vault.load_materials()
        materials_list = vault.materials_list
        for i in range(materials_list.count()):
            item = materials_list.item(i)
            data = item.data(Qt.UserRole)
            if data and data.get("file_path") == pdf_path:
                materials_list.setCurrentItem(item)
                vault.preview_material(item)
                break