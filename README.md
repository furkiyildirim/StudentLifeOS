# Student Life OS

Student Life OS, universite ogrencilerinin ders programini, gorevlerini, projelerini, notlarini, spor planini ve gunluk yasamini tek bir masaustu uygulamasinda yonetmesini saglayan Python ve PySide6 tabanli bir productivity uygulamasidir.

## Ozellikler

- Dersler, haftalik ders programi, sinavlar ve akademik takvim
- To-do listesi, projeler ve gunluk planlama
- HTML destekli notlar ve materyal arsivi
- DOCX, PPTX, XLSX ve CSV dosyalariyla calisma
- Spor ve antrenman takibi
- YouTube Music, yerel muzik ve Pomodoro odak sayaci
- Sistem tepsisi, bildirim sesleri ve zamanlanmis uyarilar
- Gemini, OpenAI, Anthropic veya yerel GGUF model kullanan AI asistani
- SQLite tabanli yerel veritabani

## Uygulama Goruntuleri

Ekran goruntulerini `images/` klasorune ekleyin. Asagidaki dosya adlarini kullanirsaniz gorseller README icinde otomatik olarak gorunur:

![Dashboard](images/dashboard.png)

![Ders Programi](images/timetable.png)

![Takvim](images/calendar.png)

![AI Asistani](images/ai-assistant.png)

![Gorevler](images/tasks.png)

Yeni bir ekran goruntusu eklemek icin dosyayi `images/` klasorune koyup README'ye su formatta bir satir ekleyin:

```markdown
![Gorsel aciklamasi](images/dosya-adi.png)
```

## Gereksinimler

- Windows 10 veya daha yeni bir Windows surumu
- Python 3.11 veya 3.12 onerilir
- Python 3.14 ile temel paketler calisabilir; `llama-cpp-python` icin CPU wheel kullanilmalidir
- Yerel model kullanilacaksa `resources/models/local_model.gguf` dosyasi

## Kurulum

PowerShell ile proje klasorunde su komutlari calistirin:

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

## AI API Anahtarlari

API anahtarlari uygulama icindeki AI asistani ayarlarindan girilebilir. Kullanilan saglayiciya gore Gemini, OpenAI veya Anthropic anahtari gerekir. Yerel model secenegi icin API anahtari gerekmez; GGUF dosyasi `resources/models/local_model.gguf` konumunda bulunmalidir.

API anahtarlarini kaynak koduna veya `requirements.txt` dosyasina yazmayin.

## Yerel Modeli Indirme

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
python -m PyInstaller --noconfirm --clean --windowed --name StudentLifeOS --icon resources/icons/icon.ico --add-data "resources;resources" --add-data "schema.sql;." --collect-all llama_cpp app.py
```

Olusan uygulama `dist/StudentLifeOS/StudentLifeOS.exe` konumunda bulunur. Bu yontem `--onedir` paketidir ve Qt WebEngine ile yerel model dosyalari icin onerilir.

### EXE'yi calistirma

```powershell
dist\StudentLifeOS\StudentLifeOS.exe
```

### Dagitim notlari

- `resources/` klasoru paketleme sirasinda `--add-data` ile dahil edilir; ikon, sesler, stiller ve model dosyalari bu klasorden okunur.
- `local_model.gguf` buyuk oldugu icin EXE'nin icine gomulmek yerine dagitim klasorunde tutulmasi tercih edilebilir. Bu durumda `dist/StudentLifeOS/resources/models/local_model.gguf` yoluna kopyalayin.
- EXE, yerel model olmadan da acilabilir; ancak `Yerel` AI secenegi icin model dosyasini `dist/StudentLifeOS/resources/models/local_model.gguf` konumuna ayri olarak kopyalamaniz gerekir.
- Uygulama calisirken olusan `student_life.db` ve `vault_storage/` kullanici verileridir; yedeklemek icin bu iki yolu kopyalayin.
- Tek dosyali paket gerekiyorsa `--onedir` yerine `--onefile` kullanilabilir. Ancak baslangic daha yavas olur ve buyuk model dosyasini paketlemek pratik olmayabilir.

## Sorun Giderme

### `llama-cpp-python` kurulamiyor

CPU wheel kaynagi `requirements.txt` icinde tanimlidir. Elle kurmak icin:

```powershell
python -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

### EXE acilmiyor

Once konsol ciktilarini gorebilmek icin uygulamayi `--console` ile yeniden paketleyin:

```powershell
python -m PyInstaller --noconfirm --clean --console --name StudentLifeOS --add-data "resources;resources" --add-data "schema.sql;." --collect-all llama_cpp app.py
```

Ardindan `dist/StudentLifeOS/StudentLifeOS.exe` komutunu PowerShell'den calistirip hata mesajini inceleyin.

## Lisans

Bu proje MIT lisansi altinda gelistirilmistir. Ayrintilar icin [LICENSE](LICENSE) dosyasina bakin.