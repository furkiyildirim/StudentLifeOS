import os
import html
import json
import google.generativeai as genai
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QLineEdit, QPushButton, QLabel, QFrame, QMessageBox, QGraphicsDropShadowEffect, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QCursor, QColor

from core.events import bus

class AIWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)
    system_ready = Signal()

    def __init__(self, db, model_version="Gemini 3.5 Flash", conversation_history=None):
        super().__init__()
        self.db = db
        self.api_key = None
        self.message_queue = []
        self.is_running = True
        self.chat_session = None
        self.model_version = model_version
        self.conversation_history = conversation_history or []

    def set_api_key(self, key):
        self.api_key = key

    def run(self):
        if not self.api_key:
            self.is_running = False
            self.error_occurred.emit("API Anahtarı eksik!")
            return

        system_prompt = "Sen Student Life OS asistanısın. Yanıtlarını kısa ve öz tut."
        tools = []
        try:
            from core.ai_agent import get_system_prompt, get_database_tools
            system_prompt = get_system_prompt(self.db)
            tools = get_database_tools(self.db)
        except: pass

        try:
            genai.configure(api_key=self.api_key)
            
            model_map = {
                "Gemini 3.2 Flash": "gemini-3.2-flash",
                "Gemini 3.5 Flash": "gemini-3.5-flash",
                "Gemini 3.7 Pro": "gemini-3.7-pro",
                "Gemini 3.8 Flash": "gemini-3.8-flash"
            }
            selected_model = model_map.get(self.model_version, "gemini-3.5-flash")
            
            model = genai.GenerativeModel(model_name=selected_model, tools=tools, system_instruction=system_prompt)
            self.chat_session = model.start_chat(enable_automatic_function_calling=True)
            self.system_ready.emit()
        except Exception as e:
            self.is_running = False
            self.error_occurred.emit(f"Başlatma Hatası: {str(e)}")
            return

        while self.is_running:
            if self.message_queue:
                msg = self.message_queue.pop(0)
                if not self.is_running:
                    break
                try:
                    context = self.conversation_history[-8:]
                    if context:
                        context_text = "\n".join(f"{item['role']}: {item['content']}" for item in context)
                        msg = f"Önceki sohbet bağlamı:\n{context_text}\n\nYeni mesajım:\n{msg}"
                    
                    response = self.chat_session.send_message(msg)
                    try:
                        reply = response.text
                    except ValueError:
                        reply = "İşlemi veritabanında başarıyla uyguladım."
                    self.response_ready.emit(reply)
                except Exception as e:
                    self.error_occurred.emit(str(e))
            self.msleep(150)

    def queue_message(self, text):
        self.message_queue.append(text)

    def stop(self):
        self.is_running = False
        self.message_queue.clear()

class AIChatWindow(QFrame):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.main_window = parent
        self.db = db
        self.worker = None
        self.stopping_workers = []
        self.generation_cancelled = False
        self.conversation_history = []
        
        self.setFixedSize(380, 520)
        self.setObjectName("ChatWindow")
        
        self.setStyleSheet("""
            #ChatWindow { background-color: #171412; border: 1px solid #292524; border-radius: 16px; }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 10)
        self.setGraphicsEffect(shadow)
        
        self.init_ui()
        self._load_conversation_history()
        
        self.hide()
        
        bus.ai_settings_changed.connect(self.refresh_credentials)
        if QApplication.instance():
            QApplication.instance().aboutToQuit.connect(self.shutdown_workers)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header_lay = QHBoxLayout()
        lbl_title = QLabel("✦")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #38bdf8;")
        header_lay.addWidget(lbl_title)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Gemini 3.2 Flash", "Gemini 3.5 Flash", "Gemini 3.7 Pro", "Gemini 3.8 Flash"])
        self.model_combo.setCurrentText("Gemini 3.5 Flash")
        
        self.model_combo.setCursor(QCursor(Qt.PointingHandCursor))
        self.model_combo.setStyleSheet("""
            QComboBox { background-color: #1c1917; color: #e4e4e7; border-radius: 6px; padding: 4px 10px; border: 1px solid #3f3f46; font-size: 13px; font-weight: bold; }
            QComboBox::drop-down { border: none; }
        """)
        self.model_combo.currentTextChanged.connect(self.reset_ai)
        header_lay.addWidget(self.model_combo)
        
        header_lay.addStretch()
        
        # YENİ EKLENEN: Sohbet Geçmişi Temizleme Butonu
        btn_clear = QPushButton("🗑")
        btn_clear.setCursor(QCursor(Qt.PointingHandCursor))
        btn_clear.setFixedSize(24, 24)
        btn_clear.setToolTip("Sohbet Geçmişini Temizle")
        btn_clear.setStyleSheet("background: transparent; color: #f43f5e; font-weight: bold; font-size: 15px; border: none;")
        btn_clear.clicked.connect(self.clear_chat)
        header_lay.addWidget(btn_clear)
        
        btn_close = QPushButton("✖")
        btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet("background: transparent; color: #a1a1aa; font-weight: bold; font-size: 14px; border: none;")
        btn_close.clicked.connect(self.hide)
        header_lay.addWidget(btn_close)
        
        layout.addLayout(header_lay)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit { background-color: #12100e; border: 1px solid #292524; border-radius: 8px; padding: 10px; font-size: 13px; line-height: 1.6; color: #f4f4f5; }
        """)
        layout.addWidget(self.chat_display)

        self.lbl_typing = QLabel("")
        self.lbl_typing.hide()
        self.lbl_typing.setParent(self.chat_display.viewport())
        self.lbl_typing.setStyleSheet("""
            QLabel { background-color: #1c1917; color: #38bdf8; border: 1px solid #3f3f46; border-radius: 10px; padding: 6px 10px; font-size: 12px; font-style: italic; }
        """)
        
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.update_typing)
        self.typing_dots = 0

        input_lay = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Asistana yaz...")
        self.input_field.setFixedHeight(44)
        self.input_field.setStyleSheet("""
            QLineEdit { background-color: #1c1917; color: #f4f4f5; border-radius: 22px; padding: 0 16px; font-size: 13px; border: 1px solid #3f3f46; }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        
        self.btn_send = QPushButton("➤")
        self.btn_send.setFixedSize(44, 44)
        self.btn_send.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_send.setStyleSheet("""
            QPushButton { background-color: #38bdf8; color: #0c0a09; font-weight: bold; border-radius: 22px; font-size: 16px; border: none; }
            QPushButton:hover { background-color: #0284c7; }
            QPushButton:disabled { background-color: #292524; color: #52525b; }
        """)
        self.btn_send.clicked.connect(self.send_message)

        self.btn_stop = QPushButton("■")
        self.btn_stop.setFixedSize(44, 44)
        self.btn_stop.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_stop.setStyleSheet("""
            QPushButton { background-color: #e11d48; color: white; font-weight: bold; border-radius: 22px; font-size: 14px; border: none; }
            QPushButton:hover { background-color: #be123c; }
        """)
        self.btn_stop.clicked.connect(self.stop_generation)
        self.btn_stop.hide()
        
        input_lay.addWidget(self.input_field)
        input_lay.addWidget(self.btn_send)
        input_lay.addWidget(self.btn_stop)
        layout.addLayout(input_lay)

    def _history_key(self):
        return "ai_chat_history_gemini"

    def _load_conversation_history(self):
        try:
            with self.db.get_connection() as conn:
                row = conn.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (self._history_key(),)).fetchone()
            history = json.loads(row[0]) if row and row[0] else []
            self.conversation_history = [item for item in history if item.get("role") in ("user", "assistant") and item.get("content")]
        except Exception:
            self.conversation_history = []
        self.render_conversation()

    def _save_conversation_history(self):
        try:
            value = json.dumps(self.conversation_history[-40:], ensure_ascii=False)
            with self.db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
                    (self._history_key(), value),
                )
                conn.commit()
        except Exception: pass

    # YENİ EKLENEN: Geçmişi kalıcı olarak temizler ve modeli sıfırlar
    def clear_chat(self):
        if not self.conversation_history:
            return
            
        confirm = QMessageBox.question(
            self, "Sohbeti Temizle", 
            "Tüm sohbet geçmişi silinecek ve yapay zekanın hafızası sıfırlanacak. Emin misiniz?", 
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.conversation_history.clear()
            self._save_conversation_history()
            self.render_conversation()
            self.reset_ai() # Modeli baştan başlatarak Gemini'nin önceki mesajları hatırlamasını (context) engeller.

    def render_conversation(self):
        self.chat_display.clear()
        if not self.conversation_history:
            self.chat_display.append("<p style='color:#a1a1aa;'><b>✦ Gemini Asistan</b><br>Hazırım. Derslerini, planlarını ve projelerini birlikte yönetebiliriz.</p>")
            return
        for item in self.conversation_history:
            content = html.escape(str(item["content"])).replace("\n", "<br>")
            if item["role"] == "user":
                self.chat_display.append(f"<p><b style='color:#38bdf8;'>Sen</b><br>{content}</p>")
            else:
                self.chat_display.append(f"<p><b style='color:#10b981;'>Gemini</b><br>{content}</p>")
        self.scroll_to_bottom()

    def reset_ai(self):
        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)
        self.typing_timer.stop()
        if hasattr(self, 'lbl_typing') and self.lbl_typing:
            self.lbl_typing.hide()
        self.setup_ai()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'lbl_typing') and self.lbl_typing:
            self.lbl_typing.adjustSize()
            viewport = self.chat_display.viewport()
            self.lbl_typing.move(14, viewport.height() - self.lbl_typing.height() - 12)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.worker:
            self.setup_ai()
        self.render_conversation()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, 'typing_timer') and self.typing_timer:
            self.typing_timer.stop()
        if hasattr(self, 'lbl_typing') and self.lbl_typing:
            self.lbl_typing.hide()
        if hasattr(self, 'btn_stop') and self.btn_stop:
            self.btn_stop.hide()

    def shutdown_workers(self):
        workers = list(self.stopping_workers)
        if self.worker:
            workers.append(self.worker)
            self.worker = None
        for worker in workers:
            self.stop_worker(worker)
        for worker in list(self.stopping_workers):
            if worker.isRunning(): worker.wait()
            self.finish_stopping_worker(worker)

    def stop_worker(self, worker):
        try:
            worker.response_ready.disconnect()
            worker.error_occurred.disconnect()
            worker.system_ready.disconnect()
        except Exception: pass
        worker.stop()
        if worker.isRunning():
            if worker not in self.stopping_workers:
                self.stopping_workers.append(worker)
                worker.finished.connect(lambda: self.finish_stopping_worker(worker))
            return
        worker.deleteLater()

    def finish_stopping_worker(self, worker):
        if worker in self.stopping_workers:
            self.stopping_workers.remove(worker)
        worker.deleteLater()

    def update_typing(self):
        self.typing_dots = (self.typing_dots + 1) % 4
        self.lbl_typing.setText(f"Gemini yazıyor{'.' * self.typing_dots}")
        self.lbl_typing.adjustSize()
        viewport = self.chat_display.viewport()
        self.lbl_typing.move(14, viewport.height() - self.lbl_typing.height() - 12)

    def setup_ai(self):
        from core.network import check_internet_connection
        if not check_internet_connection():
            self.chat_display.clear()
            self.chat_display.append("<span style='color:#ef4444;'>Sistem: 🔴 Offline. İnternet bağlantısı yok.</span>")
            self.input_field.setEnabled(False)
            self.btn_send.setEnabled(False)
            return False

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'gemini_api_key'")
            row = cur.fetchone()
            api_key = row["setting_value"] if row else ""
        
        if not api_key or api_key == "1":
            self.chat_display.clear()
            self.chat_display.append("<span style='color:#ef4444;'>Hata: API Anahtarı eksik! Ayarlar menüsünden anahtarınızı kaydedin.</span>")
            if hasattr(self, 'input_field'): self.input_field.setEnabled(False)
            if hasattr(self, 'btn_send'): self.btn_send.setEnabled(False)
            return False
            
        selected_model = self.model_combo.currentText()
        self.worker = AIWorker(self.db, selected_model, self.conversation_history)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.set_api_key(api_key)
        self.worker.response_ready.connect(self.on_response)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.system_ready.connect(self.on_ready)
        self.worker.start()
        return True

    def on_ready(self):
        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.btn_stop.hide()

    def stop_generation(self):
        self.generation_cancelled = True
        self.typing_timer.stop()
        if hasattr(self, 'lbl_typing') and self.lbl_typing:
            self.lbl_typing.hide()
        if hasattr(self, 'btn_stop') and self.btn_stop:
            self.btn_stop.hide()

        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)

        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.chat_display.append("<br><span style='color:#f59e0b;'><b>Sistem:</b> Yanıt üretimi durduruldu.</span>")
        self.scroll_to_bottom()

    def send_message(self):
        text = self.input_field.text().strip()
        if not text: return

        self.generation_cancelled = False
        
        if not self.worker or not self.worker.is_running:
            if not self.setup_ai(): return

        self.conversation_history.append({"role": "user", "content": text})
        self._save_conversation_history()
        self.render_conversation()
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.btn_stop.show()
        
        self.typing_dots = 0
        self.lbl_typing.setText("Gemini yazıyor")
        self.lbl_typing.show()
        self.typing_timer.start(400)
        
        self.worker.queue_message(text)

    def on_response(self, reply_text):
        if self.generation_cancelled: return
        self.typing_timer.stop()
        self.lbl_typing.hide()
        self.btn_stop.hide()
        
        self.conversation_history.append({"role": "assistant", "content": str(reply_text or "").strip()})
        self._save_conversation_history()
        self.render_conversation()
        
        try:
            if self.main_window:
                if hasattr(self.main_window, 'todo_view'): self.main_window.todo_view.load_tasks()
                if hasattr(self.main_window, 'dashboard_view') and hasattr(self.main_window.dashboard_view, 'refresh'):
                    self.main_window.dashboard_view.refresh()
                if hasattr(self.main_window, 'project_view'): self.main_window.project_view.load_projects()
                if hasattr(self.main_window, 'vault_view'): self.main_window.vault_view.load_notes()
                if hasattr(self.main_window, 'calendar_view'): self.main_window.calendar_view.refresh_calendar()
                if hasattr(self.main_window, 'timetable_view'): self.main_window.timetable_view.load_schedule()
            bus.habits_changed.emit()
            bus.workouts_changed.emit()
            bus.courses_changed.emit()
            bus.assessments_changed.emit()
            bus.notes_changed.emit()
        except Exception: pass
        
        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.input_field.setFocus()
        self.scroll_to_bottom()

    def refresh_credentials(self):
        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)
        self.typing_timer.stop()
        if hasattr(self, 'lbl_typing') and self.lbl_typing:
            self.lbl_typing.hide()
        self.input_field.setEnabled(False)
        self.btn_send.setEnabled(False)
        if self.isVisible():
            QTimer.singleShot(150, self.setup_ai)

    def on_error(self, error_msg):
        if self.generation_cancelled: return
        self.typing_timer.stop()
        self.lbl_typing.hide()
        self.btn_stop.hide()

        self.chat_display.append(f"<p style='color:#fca5a5;'><b>Hata:</b> {error_msg}</p>")
        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.scroll_to_bottom()
        
    def scroll_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())