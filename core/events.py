from PySide6.QtCore import QObject, Signal

class AppEventBus(QObject):
    """Tüm sayfaların birbirini anında tetiklemesini sağlayan merkezi sinyal yöneticisi."""
    # Veri değişim sinyalleri
    habits_changed = Signal()      
    workouts_changed = Signal()    
    courses_changed = Signal()     
    assessments_changed = Signal() 
    notes_changed = Signal()       
    calendar_changed = Signal()    
    study_time_changed = Signal()

    # --- YENİ: Kayıt ve Silme Bildirim Sinyalleri ---
    item_saved = Signal(str)       # Örn: "Yeni plan kaydedildi."
    item_deleted = Signal(str)     # Örn: "Öğe silindi."

# Uygulama genelinde tek bir örnek (Singleton)
bus = AppEventBus()