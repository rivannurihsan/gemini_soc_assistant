Berikut adalah versi final dan lengkap dari `README.md` yang merangkum seluruh arsitektur, *use case* SOC, dan konfigurasi *zero-dependency* yang telah kita buat. Anda bisa langsung menyalin seluruh isi kotak di bawah ini:

```markdown
# Gemini SOC Assistant

**Gemini SOC Assistant** adalah aplikasi kustom untuk Splunk Enterprise yang mengintegrasikan kemampuan analitik dari Google Gemini dan Gemma AI secara langsung ke dalam alur kerja Security Operations Center (SOC). 

Aplikasi ini dirancang dengan pendekatan *zero-dependency* (memanfaatkan *library* bawaan Splunk secara penuh menggunakan `urllib`) sehingga sangat ringan, aman, dan tidak memerlukan instalasi *library* Python pihak ketiga di *server* Splunk Anda.

## 🌟 Fitur Utama
* **Custom Search Command (SPL)**: Analisis log, ekstraksi *Indicator of Compromise* (IOC), dan pembuatan draf laporan keamanan menggunakan *command* `| geminianalyze`.
* **Dukungan Multi-Model**: Mendukung berbagai model Google AI, termasuk jajaran **Gemini 1.5** (Pro/Flash) dan **Gemma** (seperti `gemma-4-31b-it` atau `gemma-2-27b-it`).
* **Keamanan Terjamin**: API Key disimpan secara terenkripsi di dalam Splunk Credential Store, bukan sebagai *plaintext*.
* **Konfigurasi via UI**: Halaman *Setup Dashboard* yang ramah pengguna untuk mengatur kredensial dan memilih model *default*.

## 📋 Prasyarat
* **Splunk Enterprise** (Akses Administrator untuk instalasi dan konfigurasi awal).
* **Google AI API Key**. Dapatkan secara gratis melalui [Google AI Studio](https://aistudio.google.com/).

## 📂 Struktur Direktori
```text
gemini_soc_assistant/
├── appserver/static/setup_page.js             # Logika JavaScript untuk halaman UI Setup
├── bin/
│   ├── gemini_analyze.py                      # Script utama Custom Search Command
│   └── setup_handler.py                       # REST Handler untuk Splunk Credential Store
├── default/
│   ├── app.conf                               # Metadata dan status aplikasi
│   ├── commands.conf                          # Registrasi command SPL
│   ├── gemini_settings.conf                   # Konfigurasi model default
│   ├── restmap.conf                           # Registrasi endpoint REST
│   ├── web.conf                               # Eksposur endpoint ke Splunk Web
│   └── data/ui/views/setup_page_dashboard.xml # Layout UI halaman Setup
├── metadata/
│   └── default.meta                           # Pengaturan izin akses peran Splunk
├── README/
│   └── gemini_settings.conf.spec              # Spesifikasi file konfigurasi kustom
├── README.md
└── LICENSE
```

## 🚀 Tahapan Instalasi

1. **Download Repositori**
   Clone repositori ini atau unduh dalam format `.zip`:
   ```bash
   git clone [https://github.com/rivannurihsan/gemini_soc_assistant.git](https://github.com/rivannurihsan/gemini_soc_assistant.git)
   ```

2. **Pindahkan ke Direktori Apps Splunk**
   Salin seluruh direktori `gemini_soc_assistant` ke dalam folder aplikasi Splunk Anda:
   * **Linux:** `/opt/splunk/etc/apps/`
   * **Windows:** `C:\Program Files\Splunk\etc\apps\`

3. **Restart Splunk**
   Jalankan ulang layanan Splunk agar sistem mengenali *Custom Search Command* dan *endpoint* REST yang baru ditambahkan:
   ```bash
   /opt/splunk/bin/splunk restart
   ```

## ⚙️ Konfigurasi (Setup API Key & Model)

Setelah instalasi selesai, Anda wajib melakukan konfigurasi kredensial melalui antarmuka web Splunk:
1. Login ke **Splunk Web** menggunakan akun berhak akses Administrator.
2. Pada menu navigasi **Apps** (kiri atas), klik **Gemini SOC Assistant**.
3. Anda akan secara otomatis diarahkan ke halaman **Gemini & Gemma API Configuration**.
4. Masukkan **Google AI API Key** Anda pada kolom yang disediakan.
5. Pilih model *default* pada *dropdown* (misalnya: `gemma-4-31b-it` untuk analisis SOC). Jika model yang diinginkan tidak ada di daftar, pilih opsi *Custom* dan ketikkan nama model secara manual.
6. Klik **Simpan Konfigurasi**. Tunggu hingga pesan sukses muncul di layar.

## 🔍 Panduan Penggunaan SPL

Gunakan *command* `| geminianalyze` di kolom pencarian (*Search & Reporting*) Splunk.

**Sintaks Dasar:**
```splunk
| geminianalyze prompt="<Instruksi atau Pertanyaan Anda>" field=<Nama Field Log> model="<Opsional: Nama Model>"
```
* `prompt` (Wajib): Instruksi analisis untuk AI.
* `field` (Opsional): Nama kolom yang berisi data log. *Default* bernilai `_raw`.
* `model` (Opsional): Parameter ini memungkinkan Anda meng- *override* model *default* khusus untuk satu pencarian tersebut.

### Contoh Kasus Penggunaan SOC

**1. Analisis dan Ekstraksi IOC dari Alert EDR (Misal: SentinelOne):**
```splunk
index=edr sourcetype="sentinelone:alerts" threat_status="unmitigated"
| head 5
| geminianalyze prompt="Ekstrak indikator kompromi (IOC) dari peringatan EDR ini dalam format *bullet points*, dan berikan rekomendasi langkah karantina:" field=_raw
| table _time, endpoint_name, threat_name, gemini_analysis
```

**2. Deteksi Anomali Jaringan pada Log Firewall untuk Draf Scorecard OJK:**
```splunk
index=firewall action=blocked
| head 10
| geminianalyze prompt="Analisis apakah alamat IP sumber dalam log ini menunjukkan pola serangan *brute-force* atau *probing*, lalu buatkan ringkasan singkat dan formal untuk draf laporan keamanan." field=_raw
| table _time, src_ip, dest_port, gemini_analysis
```

**3. Mengganti Model Secara Langsung di Query (On-the-fly Override):**
Jika Anda membutuhkan model analitik yang lebih besar seperti Gemini 1.5 Pro khusus untuk membedah *payload* yang rumit:
```splunk
index=proxy
| head 1
| geminianalyze prompt="Analisis payload HTTP ini secara mendalam untuk menemukan teknik obfuscation atau SQL Injection bypass." field=_raw model="gemini-1.5-pro"
| table _time, url, gemini_analysis
```

## 📄 Lisensi
Proyek ini didistribusikan di bawah lisensi **MIT License**. Lihat file `LICENSE` untuk informasi lebih lanjut mengenai hak penggunaan dan modifikasi.
```