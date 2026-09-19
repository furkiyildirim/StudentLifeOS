```markdown
# Student Life OS

> Öğrenci hayatının ders, görev, proje, materyal, kütüphane, spor ve odak çalışmalarını tek bir Windows masaüstü uygulamasında birleştiren productivity platformu.

[![Platform](https://img.shields.io/badge/platform-Windows-0078D4)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-PySide6-41CD52)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Student Life OS, üniversite öğrencilerinin akademik ve günlük planlarını yerel veritabanıyla yönetmesini sağlayan Python ve PySide6 tabanlı bir masaüstü uygulamasıdır[cite: 7]. Veriler varsayılan olarak bilgisayarda tutulur; bulut hesabına bağımlı bir kullanım gerektirmez[cite: 7].

## İçerik

- [Neler Sunar?](#neler-sunar)
- [Gereksinimler](#gereksinimler)
- [Kurulum](#kurulum)
- [Yapılandırma](#yapilandirma)
- [Yerel AI Modeli](#yerel-ai-modeli)
- [Gelişmiş Kullanım](#gelismis-kullanim)
- [Veri ve Gizlilik](#veri-ve-gizlilik)
- [Sorun Giderme](#sorun-giderme)
- [Lisans](#lisans)

## Neler Sunar?

### Akademik Planlama

- Dersler, haftalık ders programı, sınavlar ve akademik takvim[cite: 7].
- **Görüntü İşleme (OCR):** Ders programı fotoğraflarını yerel olarak tarayıp sisteme otomatik aktarma.
- Kredi bazlı Dönem Ortalaması (SPA) ve Genel Not Ortalaması (CGPA) hesaplamaları.
- To-do listesi, projeler ve günlük planlama[cite: 7].
- Sistem tepsisi bildirimleri, yaklaşan dönem sayaçları ve zamanlanmış hatırlatıcılar[cite: 7].

### Kişisel Takip

- **Kitaplığım:** E-kitap (PDF) ve fiziksel kitap arşivi, otomatik kapak çıkarma ve "Ödünç Alınan" kitapların (iade tarihi/konumu) bildirimli takibi.
- Spor, antrenman ve alışkanlık zinciri takibi[cite: 7].
- YouTube Music, yerel müzik çalar ve Pomodoro odak sayacı[cite: 7].
- Hava durumu, "Günün Sözü" motivasyonu ve dinamik ağ (Online/Offline) göstergesi içeren Kontrol Paneli.

### Materyal ve AI

- HTML destekli notlar, DOCX, PPTX, XLSX ve CSV dosyaları için entegre ön izleme ve kelime işlemci (Word) tarzı düzenleme[cite: 7].
- Gemini, OpenAI, Anthropic veya yerel GGUF model kullanan, veritabanını okuyup yönetebilen AI asistanı[cite: 7].
- İnternet kesintilerine karşı dinamik "Offline" koruma modülleri.
- SQLite tabanlı yerel veri saklama[cite: 7].

## Uygulama Görüntüleri

Uygulamanın ekran görüntüleri `images/` klasöründen[cite: 7]:

![Kontrol Paneli](images/dashboard.png)
![Yapılacaklar](images/tasks.png)
![Kitaplığım](images/library.png)
![Akıllı Takvim](images/calendar.png)
![Dersler ve Notlar](images/timetable.png)
![Materyal Kasası](images/vault.png)
![Spor ve Alışkanlık](images/fitness.png)
![Müzik ve Odak](images/music.png)
![Üniversite](images/uni.png)
![Kitaplik](images/lib.png)
![Projeler](images/procject.png)
![AI Asistanı](images/ai-assistant.png)

## Gereksinimler

- Windows 10 veya daha yeni bir Windows sürümü[cite: 7]
- Python 3.11 veya 3.12 önerilir[cite: 7]
- İnternet bağlantısı: AI API'leri, YouTube Music ve güncel hava durumu için gereklidir (Temel özellikler, Kitaplık ve Yerel Müzik Offline çalışır)[cite: 7].
- **Sistem Kütüphaneleri:** Arayüz için `PySide6`, Döküman/PDF işlemleri için `PyMuPDF`, `python-docx`, `python-pptx`, `pandas`, `openpyxl`, `xlrd`, Görüntü işleme (OCR) için `easyocr`[cite: 7].
- Yerel model kullanılacaksa `resources/models/local_model.gguf` dosyası[cite: 7]

## Kurulum

### 1. Depoyu klonlayın

```powershell
git clone [https://github.com/furkiyildirim/StudentLifeOS.git](https://github.com/furkiyildirim/StudentLifeOS.git)
Set-Location StudentLifeOS

```

### 2. Sanal ortamı oluşturun

PowerShell ile proje klasöründe şu komutları çalıştırın:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

```

PowerShell script çalıştırma politikası aktivasyonu engellerse, mevcut oturum için şu komutu çalıştırın ve kurulumu tekrarlayın:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

```

Uygulamayı başlatmak için:

```powershell
python app.py

```

Uygulama ilk çalıştırmada proje klasöründe `student_life.db` dosyasını oluşturur. Kullanıcı dosyaları `vault_storage/` ve kapak görselleri `resources/covers/` altında tutulur.

## Yapılandırma

Uygulama içindeki `Ayarlar` ekranından şu tercihler yönetilebilir:

* AI sağlayıcı (Gemini, ChatGPT, Claude) API anahtarları


* Bildirimler, ders hatırlatıcı zamanları ve sesler


* Hava durumu görünümü ve konum ayarları


* Dönem Başlangıç ve Bitiş tarihleri

API anahtarları güvenli bir şekilde yerel SQLite ayarlar tablosunda tutulur; asla kaynak koduna veya GitHub'a eklenmemelidir.

## Yerel AI Modeli

Yerel AI asistanı için Qwen2.5 Coder 3B Instruct modelinin GGUF formatındaki `Q4_K_M` dosyası kullanılır. Model dosyası yaklaşık 1.8 GB olduğu için GitHub deposuna dahil edilmez.

### PowerShell ile indirme

Proje klasöründe PowerShell açıp şu komutları çalıştırın:

```powershell
New-Item -ItemType Directory -Force resources\models | Out-Null
Invoke-WebRequest `
	-Uri "[https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf?download=true](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf?download=true)" `
	-OutFile "resources\models\local_model.gguf"

```

## Windows EXE Oluşturma

PyInstaller, uygulamayı ve Python kodunu Windows için çalıştırılabilir dosyaya paketler. Proje klasöründe sanal ortam aktifken:

```powershell
.\build_exe.ps1

```

Betik, `StudentLifeOS.spec` dosyasını kullanarak uygulamayı klasör halinde oluşturur.

### Dağıtım Notları

* `resources/` klasörü EXE ile aynı seviyede tutulmalıdır. EXE'yi tek başına başka bir klasöre taşımayın.


* `_internal/` klasöründeki DLL dosyaları çalışma için gereklidir.


* Uygulama çalışırken oluşan `student_life.db`, `vault_storage/` ve `resources/covers/` verilerinizdir; yedeklemek için bu yolları kopyalayın.



## Gelişmiş Kullanım

### Proje Yapısı

```text
app.py                 Ana PySide6 uygulaması
core/                  Veritabanı, AI (ai_agent), ağ, OCR, ses ve olay modülleri
views/                 Uygulama ekranları (Dashboard, Library, Vault, Timetable vb.)
widgets/               Ortak arayüz bileşenleri
resources/             Tema, ikon, kapaklar, ses ve model dosyaları
schema.sql             Veritabanı şeması

```

## Lisans

Bu proje MIT lisansı altında geliştirilmiştir. Ayrıntılar için [LICENSE](https://www.google.com/search?q=LICENSE&utm_source=gemini) dosyasına bakın.

```

```
