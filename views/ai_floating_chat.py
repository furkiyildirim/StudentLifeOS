import os
import multiprocessing
import google.generativeai as genai
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTextEdit, QComboBox,
    QLineEdit, QPushButton, QLabel, QFrame, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QCursor, QColor

from core.events import bus

class AIWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)
    system_ready = Signal()

    def __init__(self, db, model_choice):
        super().__init__()
        self.db = db
        self.model_choice = model_choice
        self.api_key = None
        self.message_queue = []
        self.is_running = True
        self.chat_session = None
        self.chat_history = [] 

    def set_api_key(self, key):
        self.api_key = key

    def run(self):
        if "Yerel" not in self.model_choice and not self.api_key:
            self.is_running = False
            self.error_occurred.emit("API Anahtarı eksik!")
            return

        system_prompt = "Sen Student Life OS asistanısın. Yanıtlarını kısa ve öz tut."
        try:
            from core.ai_agent import get_system_prompt
            system_prompt = get_system_prompt(self.db)
        except: pass
        
        tools = []
        try:
            from core.ai_agent import get_database_tools
            tools = get_database_tools(self.db)
        except: pass

        if "Yerel" in self.model_choice:
            try:
                from llama_cpp import Llama
                model_path = os.path.join("resources", "models", "local_model.gguf")
                if not os.path.exists(model_path):
                    self.error_occurred.emit("Model dosyası bulunamadı! Lütfen 'resources/models/local_model.gguf' konumuna ekleyin.")
                    self.is_running = False
                    return

                optimal_threads = max(1, multiprocessing.cpu_count() - 1)

                try:
                    self.local_llm = Llama(
                        model_path=model_path, 
                        n_ctx=4096, 
                        n_threads=optimal_threads, 
                        n_gpu_layers=-1, 
                        verbose=False
                    )
                except Exception:
                    self.local_llm = Llama(
                        model_path=model_path, 
                        n_ctx=4096, 
                        n_threads=optimal_threads, 
                        n_gpu_layers=0, 
                        verbose=False
                    )

                self.chat_history = [{"role": "system", "content": system_prompt}]
                self.system_ready.emit()
            except Exception as e:
                self.is_running = False
                self.error_occurred.emit(f"Yerel Model Hatası: {str(e)}")
                return
            
        elif "Gemini" in self.model_choice:
            try:
                genai.configure(api_key=self.api_key)
                model_name = "gemini-3.5-flash"
                model = genai.GenerativeModel(model_name=model_name, tools=tools, system_instruction=system_prompt)
                self.chat_session = model.start_chat(enable_automatic_function_calling=True)
                self.system_ready.emit()
            except Exception as e:
                self.is_running = False
                self.error_occurred.emit(f"Başlatma Hatası: {str(e)}")
                return
        else:
            self.system_ready.emit()

        while self.is_running:
            if self.message_queue:
                msg = self.message_queue.pop(0)
                try:
                    if "Gemini" in self.model_choice:
                        response = self.chat_session.send_message(msg)
                        try:
                            reply = response.text
                        except ValueError:
                            reply = "İşlemi veritabanında başarıyla uyguladım."
                        self.response_ready.emit(reply)
                    
                    elif "ChatGPT" in self.model_choice:
                        import openai
                        client = openai.OpenAI(api_key=self.api_key)
                        resp = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": msg}
                            ]
                        )
                        self.response_ready.emit(resp.choices[0].message.content)
                        
                    elif "Claude" in self.model_choice:
                        import anthropic
                        client = anthropic.Anthropic(api_key=self.api_key)
                        resp = client.messages.create(
                            model="claude-3-5-sonnet-20240620",
                            max_tokens=1000,
                            system=system_prompt,
                            messages=[{"role": "user", "content": msg}]
                        )
                        self.response_ready.emit(resp.content[0].text)
                        
                    elif "Yerel" in self.model_choice:
                        # Veritabanı araç entegrasyonu tamamen devre dışı bırakıldı, sadece sohbet edecek
                        self.chat_history.append({"role": "user", "content": msg})
                        
                        response = self.local_llm.create_chat_completion(
                            messages=self.chat_history,
                            max_tokens=300,
                            temperature=0.6
                        )
                        
                        message = response["choices"][0]["message"]
                        reply = message.get("content", "")
                        
                        if not reply:
                            reply = "Sizi anladım."
                            
                        self.chat_history.append({"role": "assistant", "content": reply})
                        self.response_ready.emit(reply)

                except Exception as e:
                    self.error_occurred.emit(str(e))
            
            self.msleep(150)

    def queue_message(self, text):
        self.message_queue.append(text)

    def stop(self):
        self.is_running = False

class AIChatWindow(QFrame):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.main_window = parent
        self.db = db
        self.worker = None
        
        self.setFixedSize(450, 600)
        self.setObjectName("ChatSidebar")
        self.setStyleSheet("#ChatSidebar { background-color: #12100e; border: 1px solid #292524; border-radius: 12px; }")
        
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.hide()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_lay = QHBoxLayout()
        lbl_title = QLabel("✨ Asistan")
        lbl_title.setStyleSheet("color: #3b82f6; font-size: 16px; font-weight: bold; border: none;") 
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "Gemini 3.5 Flash", 
            "ChatGPT (GPT-4o-mini)", 
            "Claude 3.5 Sonnet",
            "Yerel Model (Çevrimdışı)"
        ])
        self.model_combo.setStyleSheet("""
            QComboBox { background-color: #1c1917; color: white; border-radius: 6px; padding: 4px; border: 1px solid #292524; font-size: 12px; }
            QComboBox::drop-down { border: none; }
        """)
        self.model_combo.currentTextChanged.connect(self.reset_ai)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        btn_close.setStyleSheet("background: transparent; color: #a1a1aa; font-weight: bold; font-size: 14px; border: none;")
        btn_close.clicked.connect(self.hide)
        
        header_lay.addWidget(lbl_title)
        header_lay.addWidget(self.model_combo)
        header_lay.addStretch()
        header_lay.addWidget(btn_close)
        layout.addLayout(header_lay)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("QTextEdit { background-color: #171412; color: #f4f4f5; border-radius: 12px; padding: 12px; font-size: 13px; line-height: 1.5; border: 1px solid #292524; }")
        self.chat_display.append("<span style='color:#a1a1aa;'>Sistem: Model seçimi bekleniyor...</span>")
        layout.addWidget(self.chat_display)

        self.lbl_typing = QLabel("")
        self.lbl_typing.setStyleSheet("color: #3b82f6; font-size: 12px; font-style: italic; border: none;") 
        self.lbl_typing.hide()
        layout.addWidget(self.lbl_typing) 
        
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.update_typing)
        self.typing_dots = 0

        input_lay = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Asistana yaz...")
        self.input_field.setFixedHeight(44)
        self.input_field.setStyleSheet("""
            QLineEdit { background-color: #1c1917; color: white; border-radius: 22px; padding: 0 16px; font-size: 13px; border: 1px solid #292524; }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        
        self.btn_send = QPushButton("➤")
        self.btn_send.setFixedSize(44, 44)
        self.btn_send.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_send.setStyleSheet("""
            QPushButton { background-color: #3b82f6; color: white; font-weight: bold; border-radius: 22px; font-size: 16px; border: none; }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btn_send.clicked.connect(self.send_message)
        
        input_lay.addWidget(self.input_field)
        input_lay.addWidget(self.btn_send)
        layout.addLayout(input_lay)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.worker:
            self.setup_ai()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)
            self.chat_display.append("<br><span style='color:#a1a1aa;'>Sistem: Asistan uyku moduna geçti (RAM temizlendi).</span>")

    def closeEvent(self, event):
        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)
        event.accept()

    def stop_worker(self, worker):
        try:
            worker.response_ready.disconnect()
            worker.error_occurred.disconnect()
            worker.system_ready.disconnect()
        except (RuntimeError, TypeError):
            pass

        worker.stop()
        if worker.isRunning():
            worker.wait(3000)

        if worker.isRunning():
            worker.finished.connect(worker.deleteLater)
        else:
            worker.deleteLater()

    def update_typing(self):
        self.typing_dots = (self.typing_dots + 1) % 4
        self.lbl_typing.setText(f"{self.model_combo.currentText().split(' ')[0]} yazıyor{'.' * self.typing_dots}")

    def reset_ai(self, val=None):
        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)
            
        self.typing_timer.stop()
        self.lbl_typing.hide()
            
        selected_model = self.model_combo.currentText()
        self.chat_display.append(f"<br><span style='color:#f59e0b;'>Sistem: {selected_model} modeline geçiliyor...</span>")
        
        if "Yerel" in selected_model and isinstance(val, str):
            QMessageBox.warning(
                self, 
                "Otomatik Donanım Algılama ⚙️", 
                "Yerel Yapay Zeka modeli başlatılırken sisteminizin işlemci (CPU) ve grafik (GPU) performansı analiz edilecek ve yük en uygun şekilde paylaştırılacaktır."
            )

        self.input_field.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.setup_ai()

    def setup_ai(self):
        selected_model = self.model_combo.currentText()
        key_name = "gemini_api_key"
        
        if "Yerel" in selected_model:
            self.worker = AIWorker(self.db, selected_model)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.response_ready.connect(self.on_response)
            self.worker.error_occurred.connect(self.on_error)
            self.worker.system_ready.connect(self.on_ready)
            self.worker.start()
            return True
                    
        if "ChatGPT" in selected_model: key_name = "openai_api_key"
        elif "Claude" in selected_model: key_name = "anthropic_api_key"

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key_name,))
            row = cur.fetchone()
            api_key = row["setting_value"] if row else ""
        
        if not api_key or api_key == "1":
            self.chat_display.clear()
            self.chat_display.append(
                f"<span style='color:#ef4444;'>Sistem: {selected_model} API anahtarı bulunamadı. "
                "Lütfen sol menüdeki 'Ayarlar' sekmesinden anahtarınızı kaydedin.</span>"
            )
            if hasattr(self, 'input_field'): self.input_field.setEnabled(False)
            if hasattr(self, 'btn_send'): self.btn_send.setEnabled(False)
            return False
            
        self.worker = AIWorker(self.db, selected_model)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.set_api_key(api_key)
        self.worker.response_ready.connect(self.on_response)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.system_ready.connect(self.on_ready)
        self.worker.start()
        return True

    def on_ready(self):
        self.chat_display.clear()
        self.chat_display.append(f"<span style='color:#3b82f6;'>Sistem: {self.model_combo.currentText()} aktif. Size nasıl yardımcı olabilirim?</span><br>")
        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text: return
        
        if not self.worker or not self.worker.is_running:
            if not self.setup_ai(): return

        self.chat_display.append(f"<br><span style='color:#f4f4f5;'><b>Sen:</b></span> {text}<br>")
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.btn_send.setEnabled(False)
        
        self.typing_dots = 0
        self.lbl_typing.setText(f"{self.model_combo.currentText().split(' ')[0]} yazıyor")
        self.lbl_typing.show()
        self.typing_timer.start(400)
        
        self.worker.queue_message(text)

    def on_response(self, reply_text):
        self.typing_timer.stop()
        self.lbl_typing.hide()
        
        formatted = str(reply_text or "").replace('\n', '<br>')
        model_name = self.model_combo.currentText().split(' ')[0]
        self.chat_display.append(f"<b style='color:#10b981;'>{model_name}:</b> {formatted}<br><br>")
        
        try:
            if self.main_window:
                if hasattr(self.main_window, 'todo_view'): 
                    self.main_window.todo_view.load_tasks()
                if hasattr(self.main_window, 'dashboard_view'):
                    if hasattr(self.main_window.dashboard_view, 'refresh'):
                        self.main_window.dashboard_view.refresh()
                if hasattr(self.main_window, 'project_view'): 
                    self.main_window.project_view.load_projects()
                if hasattr(self.main_window, 'vault_view'): 
                    self.main_window.vault_view.load_notes()
                if hasattr(self.main_window, 'calendar_view'): 
                    self.main_window.calendar_view.refresh_calendar()
                if hasattr(self.main_window, 'timetable_view'): 
                    self.main_window.timetable_view.load_schedule()
            
            bus.habits_changed.emit()
            bus.workouts_changed.emit()
            bus.courses_changed.emit()
        except Exception: pass
        
        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.input_field.setFocus()
        self.scroll_to_bottom()

    def on_error(self, error_msg):
        self.typing_timer.stop()
        self.lbl_typing.hide()
        
        self.chat_display.append(f"<br><span style='color:#ef4444;'><b>Hata:</b> {error_msg}</span>")
        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.scroll_to_bottom()
        
    def scroll_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())