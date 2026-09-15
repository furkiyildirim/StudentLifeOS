import os
import html
import json
import multiprocessing
import google.generativeai as genai
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QTextEdit, QComboBox,
    QLineEdit, QPushButton, QLabel, QFrame, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QCursor, QColor, QTextCursor

from core.events import bus

class AIWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)
    system_ready = Signal()

    def __init__(self, db, model_choice, conversation_history=None):
        super().__init__()
        self.db = db
        self.model_choice = model_choice
        self.api_key = None
        self.message_queue = []
        self.is_running = True
        self.chat_session = None
        self.chat_history = [] 
        self.conversation_history = conversation_history or []
        self.local_llm = None

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
                    if not self.is_running:
                        return
                    self.local_llm = Llama(
                        model_path=model_path, 
                        n_ctx=4096, 
                        n_threads=optimal_threads, 
                        n_gpu_layers=0, 
                        verbose=False
                    )

                if not self.is_running:
                    self.local_llm = None
                    return

                self.chat_history = [{"role": "system", "content": system_prompt}]
                self.chat_history.extend(self.conversation_history)
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
                if not self.is_running:
                    break
                try:
                    if "Gemini" in self.model_choice:
                        context = self.conversation_history[-8:]
                        if context:
                            context_text = "\n".join(
                                f"{item['role']}: {item['content']}" for item in context
                            )
                            msg = f"Önceki sohbet bağlamı:\n{context_text}\n\nYeni mesajım:\n{msg}"
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
        self.message_queue.clear()
        self.local_llm = None

class AIChatWindow(QFrame):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.main_window = parent
        self.db = db
        self.worker = None
        self.stopping_workers = []
        self.generation_cancelled = False
        self.conversation_history = []
        
        self.setFixedSize(450, 600)
        self.setObjectName("ChatSidebar")
        self.setStyleSheet("#ChatSidebar { background-color: #12100e; border: 1px solid #292524; border-radius: 12px; }")
        
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.hide()
        self.init_ui()
        self._load_conversation_history()
        bus.ai_settings_changed.connect(self.refresh_credentials)
        if QApplication.instance():
            QApplication.instance().aboutToQuit.connect(self.clear_conversation_history)
            QApplication.instance().aboutToQuit.connect(self.shutdown_workers)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_lay = QHBoxLayout()
        lbl_title = QLabel("🧠  Student Life AI")
        lbl_title.setStyleSheet("color: #7dd3fc; font-size: 16px; font-weight: bold; border: none;")
        
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
        layout.addWidget(self.chat_display)

        self.lbl_typing = QLabel("")
        self.lbl_typing.setStyleSheet("color: #3b82f6; font-size: 12px; font-style: italic; border: none;")
        self.lbl_typing.hide()
        self.lbl_typing.setParent(self.chat_display.viewport())
        self.lbl_typing.setStyleSheet("""
            QLabel {
                background-color: #27272a;
                color: #7dd3fc;
                border: 1px solid #3f3f46;
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 12px;
                font-style: italic;
            }
        """)
        
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

        self.btn_stop = QPushButton("■")
        self.btn_stop.setFixedSize(44, 44)
        self.btn_stop.setToolTip("Yanıt üretimini durdur")
        self.btn_stop.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_stop.setStyleSheet("""
            QPushButton { background-color: #9f1239; color: white; font-weight: bold; border-radius: 22px; font-size: 14px; border: none; }
            QPushButton:hover { background-color: #be123c; }
        """)
        self.btn_stop.clicked.connect(self.stop_generation)
        self.btn_stop.hide()
        
        input_lay.addWidget(self.input_field)
        input_lay.addWidget(self.btn_send)
        input_lay.addWidget(self.btn_stop)
        layout.addLayout(input_lay)

    def _history_key(self, model_name=None):
        model_name = model_name or self.model_combo.currentText()
        safe_name = "".join(char if char.isalnum() else "_" for char in model_name.lower())
        return f"ai_chat_history_{safe_name}"

    def _load_conversation_history(self):
        try:
            with self.db.get_connection() as conn:
                row = conn.execute(
                    "SELECT setting_value FROM app_settings WHERE setting_key = ?",
                    (self._history_key(),),
                ).fetchone()
            history = json.loads(row[0]) if row and row[0] else []
            self.conversation_history = [
                item for item in history
                if item.get("role") in ("user", "assistant") and item.get("content")
            ]
        except (ValueError, TypeError, json.JSONDecodeError):
            self.conversation_history = []
        except Exception:
            self.conversation_history = []
        self.render_conversation()

    def _save_conversation_history(self):
        try:
            value = json.dumps(self.conversation_history[-40:], ensure_ascii=False)
            with self.db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?) "
                    "ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
                    (self._history_key(), value),
                )
                conn.commit()
        except Exception:
            pass

    def clear_conversation_history(self):
        """Uygulama tamamen kapanırken kalıcı sohbet geçmişini temizle."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM app_settings WHERE setting_key LIKE 'ai_chat_history_%'")
                conn.commit()
        except Exception:
            pass
        self.conversation_history.clear()

    def render_conversation(self):
        self.chat_display.clear()
        if not self.conversation_history:
            self.chat_display.append(
                "<p style='color:#94a3b8;'><b>🧠 Student Life AI</b><br>"
                "Hazırım. Derslerini, planlarını ve projelerini birlikte yönetebiliriz.</p>"
            )
            return
        for item in self.conversation_history:
            content = html.escape(str(item["content"])).replace("\n", "<br>")
            if item["role"] == "user":
                self.chat_display.append(
                    f"<p><b style='color:#f8fafc;'>👤 Sen</b><br>{content}</p>"
                )
            else:
                self.chat_display.append(
                    f"<p><b style='color:#10b981;'>🧠 Student Life AI</b><br>{content}</p>"
                )
        self.scroll_to_bottom()

    def resizeEvent(self, event):
        super().resizeEvent(event)
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
        self.typing_timer.stop()
        self.lbl_typing.hide()
        self.input_field.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.btn_stop.hide()
        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)

    def closeEvent(self, event):
        self.hide()
        event.accept()

    def shutdown_workers(self):
        workers = list(self.stopping_workers)
        if self.worker:
            workers.append(self.worker)
            self.worker = None

        for worker in workers:
            self.stop_worker(worker)

        for worker in list(self.stopping_workers):
            if worker.isRunning():
                worker.wait()
            self.finish_stopping_worker(worker)

    def stop_worker(self, worker):
        try:
            worker.response_ready.disconnect()
            worker.error_occurred.disconnect()
            worker.system_ready.disconnect()
        except (RuntimeError, TypeError):
            pass

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
        if self.isVisible() and self.generation_cancelled and not self.stopping_workers:
            self.generation_cancelled = False
            self.input_field.setEnabled(True)
            self.btn_send.setEnabled(True)
            self.chat_display.append("<br><span style='color:#a1a1aa;'>Sistem: Yanıt üretimi durduruldu.</span>")
            self.scroll_to_bottom()

    def update_typing(self):
        self.typing_dots = (self.typing_dots + 1) % 4
        self.lbl_typing.setText(f"🧠 Student Life AI yazıyor{'.' * self.typing_dots}")
        self.lbl_typing.adjustSize()
        viewport = self.chat_display.viewport()
        self.lbl_typing.move(14, viewport.height() - self.lbl_typing.height() - 12)

    def show_local_model_missing(self):
        self.chat_display.clear()
        self.chat_display.append(
            "<span style='color:#f87171; font-size:14px;'><b>AI model yüklü değil.</b></span><br>"
            "<span style='color:#a1a1aa;'>Yerel asistanı kullanmak için "
            "README.md dosyasındaki adımları izleyin:</span><br><br>"
            "<span style='color:#e4e4e7;'><b>PowerShell ile:</b></span><br>"
            "<pre style='color:#a1a1aa;'>"
            "New-Item -ItemType Directory -Force resources\\models | Out-Null\n"
            "Invoke-WebRequest `\n"
            "  -Uri \"https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf?download=true\" `\n"
            "  -OutFile \"resources\\models\\local_model.gguf\"</pre>"
            "<span style='color:#a1a1aa;'>Dosya adı tam olarak "
            "<b>local_model.gguf</b> olmalı ve şu konumda bulunmalı:</span><br>"
            "<span style='color:#38bdf8;'>resources/models/local_model.gguf</span><br><br>"
            "<span style='color:#e4e4e7;'><b>Kontrol etmek için:</b></span><br>"
            "<pre style='color:#a1a1aa;'>Get-Item resources\\models\\local_model.gguf | Select-Object FullName,Length</pre>"
            "<span style='color:#a1a1aa;'>Alternatif olarak Qwen2.5-Coder-3B-Instruct-GGUF modelini tarayıcıdan indirip "
            "resources/models/ klasörüne <b>local_model.gguf</b> adı ile koyabilirsiniz. "
            "Ardından uygulamayı yeniden başlatın.</span>"
        )
        self.input_field.setEnabled(False)
        self.btn_send.setEnabled(False)

    def reset_ai(self, val=None):
        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)
            
        self.typing_timer.stop()
        self.lbl_typing.hide()
        self._load_conversation_history()
            
        selected_model = self.model_combo.currentText()
        self.chat_display.append(f"<br><span style='color:#f59e0b;'>Sistem: {selected_model} modeline geçiliyor...</span>")
        
        if "Yerel" in selected_model and isinstance(val, str):
            model_path = os.path.join("resources", "models", "local_model.gguf")
            if not os.path.exists(model_path):
                self.show_local_model_missing()
                return

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
            model_path = os.path.join("resources", "models", "local_model.gguf")
            if not os.path.exists(model_path):
                self.show_local_model_missing()
                return False

            self.worker = AIWorker(self.db, selected_model, self.conversation_history)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.response_ready.connect(self.on_response)
            self.worker.error_occurred.connect(self.on_error)
            self.worker.system_ready.connect(self.on_ready)
            self.worker.start()
            return True

        from core.network import check_internet_connection
        if not check_internet_connection():
            self.chat_display.clear()
            self.chat_display.append(
                "<span style='color:#ef4444;'>Sistem: 🔴 Offline. "
                "İnternet bağlantısı yok. Yalnızca Yerel Model kullanılabilir.</span>"
            )
            self.input_field.setEnabled(False)
            self.btn_send.setEnabled(False)
            return False
                    
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
            
        self.worker = AIWorker(self.db, selected_model, self.conversation_history)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.set_api_key(api_key)
        self.worker.response_ready.connect(self.on_response)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.system_ready.connect(self.on_ready)
        self.worker.start()
        return True

    def on_ready(self):
        if not self.conversation_history:
            self.chat_display.append(f"<p style='color:#7dd3fc;'><b>🧠 Student Life AI</b><br>{self.model_combo.currentText()} aktif. Size nasıl yardımcı olabilirim?</p>")
        else:
            self.render_conversation()
        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.btn_stop.hide()

    def stop_generation(self):
        self.generation_cancelled = True
        self.typing_timer.stop()
        self.lbl_typing.hide()
        self.btn_stop.hide()

        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)

        self.input_field.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.chat_display.append("<br><span style='color:#f59e0b;'><b>Sistem:</b> Yanıt üretimi durduruluyor...</span>")
        self.scroll_to_bottom()

    def send_message(self):
        text = self.input_field.text().strip()
        if not text: return

        self.generation_cancelled = False

        if "Yerel" not in self.model_combo.currentText():
            from core.network import check_internet_connection
            if not check_internet_connection():
                self.chat_display.append(
                    "<br><span style='color:#ef4444;'><b>Sistem:</b> "
                    "🔴 Offline. Yalnızca Yerel Model kullanılabilir.</span>"
                )
                self.scroll_to_bottom()
                return
        
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
        self.lbl_typing.setText(f"{self.model_combo.currentText().split(' ')[0]} yazıyor")
        self.lbl_typing.show()
        self.typing_timer.start(400)
        
        self.worker.queue_message(text)

    def on_response(self, reply_text):
        if self.generation_cancelled:
            return

        self.typing_timer.stop()
        self.lbl_typing.hide()
        self.btn_stop.hide()
        
        model_name = self.model_combo.currentText().split(' ')[0]
        self.conversation_history.append({"role": "assistant", "content": str(reply_text or "").strip()})
        self._save_conversation_history()
        self.render_conversation()
        
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
            bus.assessments_changed.emit()
            bus.notes_changed.emit()
        except Exception: pass
        
        self.input_field.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.input_field.setFocus()
        self.scroll_to_bottom()

    def refresh_credentials(self):
        if "Yerel" in self.model_combo.currentText():
            return
        if self.worker:
            worker = self.worker
            self.worker = None
            self.stop_worker(worker)
        self.typing_timer.stop()
        self.lbl_typing.hide()
        self.input_field.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.chat_display.append("<p style='color:#f59e0b;'>🔐 API anahtarı kaydedildi. Chat bağlantısı yenileniyor...</p>")
        if self.isVisible():
            QTimer.singleShot(150, self.setup_ai)

    def on_error(self, error_msg):
        if self.generation_cancelled:
            return

        self.typing_timer.stop()
        self.lbl_typing.hide()
        self.btn_stop.hide()

        provider = self.model_combo.currentText().split(" ")[0]
        raw_error = str(error_msg or "")
        lowered_error = raw_error.lower()
        rate_limit_error = any(token in lowered_error for token in (
            "429", "rate limit", "rate_limit", "quota", "resource exhausted",
            "too many requests", "token limit", "token quota", "usage limit"
        ))
        key_error = any(token in lowered_error for token in (
            "api key", "api_key", "api anaht", "unauthenticated", "authentication",
            "permission denied", "401", "403", "invalid argument"
        ))

        if rate_limit_error:
            message = (
                f"⏳ <b>{provider} kullanım/token hakkı dolmuş olabilir.</b><br>"
                "İstek limiti (429) aşıldı. Kota yenilenene kadar bekleyin veya "
                "sağlayıcının kullanım ve faturalandırma panelini kontrol edin."
            )
            self.input_field.setEnabled(True)
            self.btn_send.setEnabled(True)
        elif key_error:
            message = (
                f"🔐 <b>{provider} API anahtarı kabul edilmedi.</b><br>"
                "Anahtar yanlış, süresi dolmuş veya bu model için yetkisiz olabilir.<br>"
                "Ayarlar bölümünden anahtarı kontrol edip tekrar kaydedin."
            )
            self.input_field.setEnabled(False)
            self.btn_send.setEnabled(False)
        elif "offline" in lowered_error or "connection" in lowered_error or "timeout" in lowered_error:
            message = (
                "🌐 <b>AI servisine bağlanılamadı.</b><br>"
                "İnternet bağlantınızı kontrol edip biraz sonra tekrar deneyin."
            )
            self.input_field.setEnabled(True)
            self.btn_send.setEnabled(True)
        else:
            message = (
                f"⚠️ <b>{provider} yanıt veremedi.</b><br>"
                "İstek tamamlanamadı. Ayarları veya bağlantınızı kontrol edip tekrar deneyin."
            )
            self.input_field.setEnabled(True)
            self.btn_send.setEnabled(True)

        self.chat_display.append(
            f"<p style='color:#fca5a5;'><b>🧠 Student Life AI</b><br>{message}</p>"
        )
        self.scroll_to_bottom()
        
    def scroll_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())