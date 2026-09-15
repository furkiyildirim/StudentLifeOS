# Student Life OS

> Ogrenci hayatinin ders, gorev, proje, materyal, spor ve odak calismalarini tek bir Windows masaustu uygulamasinda birlestiren productivity platformu.

[![Platform](https://img.shields.io/badge/platform-Windows-0078D4)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-PySide6-41CD52)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Student Life OS, universite ogrencilerinin akademik ve gunluk planlarini yerel veritabaniyla yonetmesini saglayan Python ve PySide6 tabanli bir masaustu uygulamasidir. Veriler varsayilan olarak bilgisayarda tutulur; bulut hesabina bagimli bir kullanim gerektirmez.

## Icerik

- [Neler Sunar?](#neler-sunar)
- [Gereksinimler](#gereksinimler)
- [Kurulum](#kurulum)
- [Yapilandirma](#yapilandirma)
- [Yerel AI Modeli](#yerel-ai-modeli)
- [Gelismis Kullanim](#gelismis-kullanim)
- [Veri ve Gizlilik](#veri-ve-gizlilik)
- [Sorun Giderme](#sorun-giderme)
- [Lisans](#lisans)

## Neler Sunar?

### Akademik planlama

- Dersler, haftalik ders programi, sinavlar ve akademik takvim
- To-do listesi, projeler ve gunluk planlama
- Sistem tepsisi bildirimleri ve zamanlanmis hatirlaticilar

### Kisisel takip

- Spor, antrenman ve aliskanlik takibi
- YouTube Music, yerel muzik ve Pomodoro odak sayaci
- Hava durumu ve gunluk kontrol paneli

### Materyal ve AI

- HTML destekli notlar ve materyal arsivi
- DOCX, PPTX, XLSX ve CSV dosyalariyla calisma
- Gemini, OpenAI, Anthropic veya yerel GGUF model kullanan AI asistani
- SQLite tabanli yerel veri saklama

## Uygulama Goruntuleri

Uygulamanin ekran goruntuleri `images/` klasorunden:

![Kontrol Paneli](images/dashboard.png)

![Kontrol Paneli Detayi](images/dashboard2.png)

![Yapilacaklar](images/tasks.png)

![Akilli Takvim](images/calendar.png)

![Dersler ve Notlar](images/timetable.png)

![Ders Programi Detayi](images/timetable2.png)

![Materyal Kasasi](images/vault.png)

![Materyal Kasasi Detayi](images/vault2.png)

![Materyal Kasasi Notlar](images/vault3.png)

![Materyal Kasasi Dosyalar](images/vault4.png)

![Spor ve Aliskanlik](images/fitness.png)

![Muzik ve Odak](images/music.png)

![Muzik Detayi](images/music2.png)

![Muzik Ek Detayi](images/music3.png)

![Universite](images/uni.png)

![Universite Detayi](images/uni2.png)

![Projeler](images/procject.png)

![Ayarlar](images/settings.png)

![Ayarlar Detayi](images/settings2.png)

![AI Asistani](images/ai-assistant.png)


```

## Gereksinimler

- Windows 10 veya daha yeni bir Windows surumu
- Python 3.11 veya 3.12 onerilir
- Python 3.14 ile temel paketler calisabilir; `llama-cpp-python` icin CPU wheel kullanilmalidir
- Internet baglantisi: AI API'leri, YouTube Music ve guncel hava durumu icin gereklidir
- Yerel model kullanilacaksa `resources/models/local_model.gguf` dosyasi

## Kurulum

### 1. Depoyu klonlayin

```powershell
git clone https://github.com/furkiyildirim/StudentLifeOS.git
Set-Location StudentLifeOS
```

### 2. Sanal ortami olusturun

PowerShell ile proje klasorunda su komutlari calistirin:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PowerShell script calistirma politikasi aktivasyonu engellerse, mevcut oturum icin su komutu calistirin ve kurulumu tekrarlayin:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Uygulamayi baslatmak icin:

```powershell
python app.py
```

Uygulama ilk calistirmada proje klasorunde `student_life.db` dosyasini olusturur. Kullanici dosyalari ve profil verileri `vault_storage/` altinda tutulur.

## Yapilandirma

Uygulama icindeki `Ayarlar` ekranindan su tercihleri yonetilebilir:

- AI saglayici ve API anahtarlari
- Bildirimler, bildirim zamanlari ve sesler
- Hava durumu gorunumu ve konum

API anahtarlarini kaynak koduna, `README.md` dosyasina veya `requirements.txt` dosyasina yazmayin. Anahtarlar yerel SQLite ayarlar tablosunda tutulur.

## AI API Anahtarlari

API anahtarlari uygulama icindeki AI asistani ayarlarindan girilebilir. Kullanilan saglayiciya gore Gemini, OpenAI veya Anthropic anahtari gerekir. Yerel model secenegi icin API anahtari gerekmez; GGUF dosyasi `resources/models/local_model.gguf` konumunda bulunmalidir.

## Yerel AI Modeli

Yerel AI asistani icin Qwen2.5 Coder 3B Instruct modelinin GGUF formatindaki `Q4_K_M` quantization dosyasi kullanilir. Model dosyasi yaklasik 1.8 GB oldugu icin GitHub deposuna dahil edilmez.

### PowerShell ile indirme

Proje klasorunde PowerShell acip su komutlari calistirin:

```powershell
New-Item -ItemType Directory -Force resources\models | Out-Null
Invoke-WebRequest `
	-Uri "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf?download=true" `
	-OutFile "resources\models\local_model.gguf"
```

Indirme tamamlandiktan sonra dosyanin dogru konumda ve yeterli boyutta oldugunu kontrol edin:

```powershell
Get-Item resources\models\local_model.gguf | Select-Object FullName,Length
```

Dosya adi tam olarak `local_model.gguf` olmalidir. Windows dosya uzantilarini gizliyorsa dosyanin yanlislikla `local_model.gguf.gguf` olarak kaydedilmedigini kontrol edin.

### Tarayici ile indirme

1. [Qwen2.5-Coder-3B-Instruct-GGUF model sayfasini](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF) acin.
2. `qwen2.5-coder-3b-instruct-q4_k_m.gguf` dosyasini indirin.
3. Dosyayi proje icindeki `resources/models/` klasorune tasiyin.
4. Dosyanin adini `local_model.gguf` olarak degistirin.

Uygulamayi yeniden baslattiktan sonra AI asistani icinden `Yerel` model secenegini kullanabilirsiniz. Model bulunamazsa uygulama `resources/models/local_model.gguf` yolunu kontrol eder.

## Windows EXE Olusturma

PyInstaller, uygulamayi ve Python kodunu Windows icin calistirilabilir dosyaya paketler. Proje klasorunde sanal ortam aktifken:

```powershell
.\build_exe.ps1
```

Betik, `StudentLifeOS.spec` dosyasini kullanarak uygulamayi klasor halinde olusturur. Eski derleme ciktilari temizlenir ve sonuc proje klasorundeki `Student Os/Student Life OS/` dizinine yazilir.

Olusan klasor yapisi:

```text
Student Os/
└── Student Life OS/
	├── StudentLifeOS.exe
	├── resources/
	└── _internal/
		├── *.dll
		└── diger PyInstaller bagimliliklari
```

`resources/` klasoru EXE ile ayni seviyede tutulur; ikonlar, sesler, stiller ve yerel model bu klasorden okunur. `_internal/` klasoru PyInstaller tarafindan uretilen DLL ve diger bagimliliklari icerir. Dagitim yaparken `Student Life OS/` klasorunun tamamini birlikte tasiyin.

### EXE'yi calistirma

```powershell
Set-Location "Student Os\Student Life OS"
.\StudentLifeOS.exe
```

### Dagitim notlari

- `resources/` klasoru EXE ile ayni seviyede olmalidir. EXE'yi tek basina baska bir klasore tasimayin.
- `_internal/` klasorundeki DLL dosyalari ve diger bagimliliklar calisma icin gereklidir.
- `local_model.gguf` yaklasik 1.8 GB oldugu icin kaynak `resources/models/` klasorune elle eklenmelidir; dosya GitHub reposuna dahil edilmez.
- Uygulama calisirken olusan `student_life.db` ve `vault_storage/` kullanici verileridir; yedeklemek icin bu iki yolu kopyalayin.

## Gelismis Kullanim

### Proje yapisi

```text
app.py                 Ana PySide6 uygulamasi
core/                  Veritabani, AI, ag, ses ve olay modulleri
views/                 Uygulama ekranlari
widgets/               Ortak arayuz bilesenleri
resources/             Tema, ikon, ses ve model dosyalari
schema.sql             Veritabani semasi
```

### Gelistirme kontrolu

Degisikliklerden sonra en azindan Python syntax kontrolunu calistirin:

```powershell
python -m py_compile app.py
```

## Veri ve Gizlilik

- Uygulama verileri yerel `student_life.db` SQLite dosyasinda tutulur.
- Web profilleri, muzik oturumlari ve uygulama onbellekleri `vault_storage/` altinda tutulur.
- API anahtarlari Git'e eklenmemelidir.
- Yedek almak icin `student_life.db` ve `vault_storage/` klasorlerini birlikte kopyalayin.
- `resources/models/local_model.gguf` buyuk oldugu icin GitHub reposuna dahil edilmez.

## Sorun Giderme

### `llama-cpp-python` kurulamiyor

CPU wheel kaynagi `requirements.txt` icinde tanimlidir. Elle kurmak icin:

```powershell
python -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

### EXE acilmiyor

Once konsol ciktilarini gorebilmek icin uygulamayi `--console` ile yeniden paketleyin:

```powershell
python -m PyInstaller --noconfirm --clean --console --distpath "Student Os" --workpath "Student Os\build" StudentLifeOS.spec
```

Ardindan `Student Os\Student Life OS\StudentLifeOS.exe` dosyasini PowerShell'den calistirip hata mesajini inceleyin. PyInstaller'in guncel yapisini kullanmak icin mumkunse hata ayiklamada da `StudentLifeOS.spec` dosyasini temel alin.

## Lisans

Bu proje MIT lisansi altinda gelistirilmistir. Ayrintilar icin [LICENSE](LICENSE) dosyasina bakin.
