# Menjalankan Essenza B2B full local

Pembaruan arsitektur: **7 November 2026**. Repo aktif: `C:\Users\ACER\Documents\Marvel\Skripsi\Project Skripsi\Essenza_Frontend`.

**PC menjalankan RDKit dan model LightGBM asli; Android menjadi antarmuka dan penyimpanan lokal.** Full local tidak berarti prediksi mandiri di HP. Komputer, API, dan jalur HP–PC harus tersedia untuk prediksi baru. Sesudah dependency dan model tersedia, pilihan katalog, input SMILES, preprocessing, dan inferensi tidak membutuhkan internet.

## Alur dan komponen

```text
HP: pilih katalog / cari nama atau rumus / input SMILES
  -> konfirmasi satu struktur
  -> POST /predict melalui USB/ADB reverse
  -> PC: RDKit -> 2.048 bit Morgan + 8 deskriptor float32
  -> PC: 109 LightGBM asli -> skor per label
  -> HP: tampilkan hasil + simpan Riwayat otomatis
  -> Koleksi disimpan manual bila diperlukan
```

| Komponen | Pengaturan |
| --- | --- |
| Entrypoint API | **`feature_api.app:app`** dalam repo frontend |
| Alamat default PC dan semua build aplikasi | **`http://127.0.0.1:8000`** |
| Jalur USB | **`adb reverse tcp:8000 tcp:8000`** |
| Model pada PC | **`feature_api/models/v7/`**, 109 `.joblib` asli |
| Registry/kontrak | **`src/assets/metadata/v7_model_manifest.json`** |
| Environment Python | **`.venv-feature-api`**, Python **3.12** |
| Riwayat/Koleksi | Penyimpanan lokal aplikasi pada HP |
| PubChem | Opsional untuk pencarian tambahan, **mati secara default** |

`127.0.0.1` pada HP mencapai PC karena aturan **ADB reverse**. Tanpa aturan tersebut, alamat itu menunjuk HP sendiri. API penelitian lama pada root repo `Perfume-MultiLabel-Classifier` tidak digunakan oleh aplikasi.

## 1. Persiapan pertama

Siapkan Node.js **>=22.11**, Python **3.12**, JDK **17/21**, Android SDK/ADB, dan USB debugging. Terima dialog otorisasi USB pada HP. Script memakai `JAVA_HOME`/`ANDROID_HOME` jika sudah disetel; lokasi standar PC ini:

- JDK: `C:\Program Files\Android\Android Studio\jbr`.
- Android SDK: `C:\Users\ACER\AppData\Local\Android\Sdk`.

Siapkan juga **frozen run final v7** yang berisi `inference_bundle.json`, `completion_manifest.json`, dan direktori `lgbm_D` dengan 109 model asli. Script mencari run pada repo penelitian di folder sebelah, termasuk lokasi transfer beku yang dipakai proyek ini. Jika lokasi berbeda, gunakan `-SourceRun` pada langkah berikutnya.

```powershell
Set-Location -LiteralPath 'C:\Users\ACER\Documents\Marvel\Skripsi\Project Skripsi\Essenza_Frontend'
npm ci
.\scripts\start-local-api.ps1 -SetupOnly
```

`-SetupOnly` membuat/memakai `.venv-feature-api`, memasang dependency yang dipin, menyiapkan salinan model, dan memeriksa checksum tanpa menyalakan server. Setup awal memerlukan internet untuk paket npm/Python/Gradle/Android yang belum tersimpan di komputer. Sumber model harus sudah tersedia; script tidak mengunduh atau melatih model.

Untuk memilih run secara eksplisit:

```powershell
.\scripts\start-local-api.ps1 -SetupOnly -SourceRun 'C:\path\ke\runs\perfume-five-grouped-v7-m2048-d8'
```

Ganti path contoh dengan folder run **final v7 LightGBM D** yang benar. Semua model disalin identik ke `feature_api/models/v7/` dan diverifikasi; paket lengkap berukuran **250.210.606 byte** untuk berkas modelnya. Tidak ada ekspor, fitting, atau serialisasi ulang. Direktori model lokal diabaikan Git, sehingga checkout frontend baru saja belum cukup untuk menjalankan prediksi.

Setelah salinan lengkap tersedia, startup berikutnya memverifikasi paket lokal tanpa membaca repo penelitian. Direktori model dan manifest yang cocok dapat disiapkan bersama untuk komputer lain; jangan mencampur model dari run berbeda.

Jika paket hanya tersedia sebagian, jalankan setup dengan `-SourceRun` untuk menyalin berkas yang hilang. Berkas tujuan dengan checksum berbeda ditolak dan perlu diperiksa terlebih dahulu; script tidak menimpa model berbeda secara otomatis.

```powershell
.\.venv-feature-api\Scripts\python.exe -B scripts\prepare-local-models.py --verify-only
```

Untuk pemilihan interpreter saat environment belum dibuat:

```powershell
$python312 = (& py -3.12 -c 'import sys; print(sys.executable)').Trim()
.\scripts\start-local-api.ps1 -PythonExe $python312 -SetupOnly
```

Runtime dipin sesuai artefak: NumPy **1.26.4**, pandas **2.2.3**, scikit-learn **1.6.1**, LightGBM **4.6.0**, joblib **1.6.0**, dan RDKit **2026.3.4**. Runtime memeriksa versi saat memuat model. Jangan mengganti versi atau identitas manifest hanya untuk melewati error kompatibilitas.

Jika shim `npm` menunjuk lokasi yang salah, gunakan Node yang sebenarnya:

```powershell
& 'C:\Program Files\nodejs\node.exe' 'C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js' ci
```

## 2. Nyalakan API pada PC

Jalankan di terminal pertama dan biarkan terbuka:

```powershell
.\scripts\start-local-api.ps1
```

Pada startup, API memverifikasi manifest, checksum **109 model**, versi paket, jumlah fitur, dan kelas `[0, 1]`, lalu memuat model sekali melalui `joblib.load`. Prediksi berikutnya memakai objek tersebut melalui `predict_proba`, bukan memuat model dari disk untuk setiap input. Server baru siap setelah pemuatan selesai.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health'
```

Periksa **`status: ok`**, **`runtime: lightgbm`**, **`model_ready: true`**, **`capabilities.local_prediction: true`**, **109 label**, **2.056 dimensi**, dan **threshold 0,5**. Identitas `model_id`, `bundle_id`, serta `feature_schema_id` harus cocok dengan manifest yang dibawa aplikasi.

PubChem tidak dibutuhkan untuk prediksi katalog/SMILES. Bila memang ingin mencari nama di luar katalog melalui internet, hentikan API dengan `Ctrl+C`, lalu jalankan:

```powershell
.\scripts\start-local-api.ps1 -AllowPubChem
```

Fitur ini memerlukan internet pada PC dan tetap meminta pemilihan kandidat struktur. Rumus seperti `C2H6O` dapat menghasilkan lebih dari satu molekul. Nama yang tidak ditemukan ketika PubChem mati dapat diganti dengan pilihan katalog atau SMILES yang diketahui.

## 3. Bangun dan jalankan APK pada HP

Di terminal kedua, dari root repo frontend:

```powershell
.\scripts\run-local-android.ps1
```

Script memeriksa HP berstatus `device`, memasang reverse, memeriksa `/health`, membangun `:app:assembleLocal`, memasang dengan `adb install -r`, lalu membuka **`com.essenza.lab`**. APK berada di **`android/app/build/outputs/apk/local/app-local.apk`**.

Build Windows memakai drive pendek **`X:`** untuk native build dan path fisik untuk bundling Metro. APK `local` membawa JavaScript sehingga tidak membutuhkan proses Metro saat digunakan. Pemasangan ulang dengan identitas/tanda tangan cocok mempertahankan Riwayat/Koleksi; script tidak menghapus data secara paksa.

| Opsi | Kegunaan |
| --- | --- |
| `-Serial 'SERIAL_HP'` | Pilih perangkat jika lebih dari satu HP tersambung. |
| `-SkipBuild` | Pasang APK yang sudah ada; gunakan hanya jika kode dan manifest belum berubah. |
| `-DriveLetter Y` | Pilih drive pendek kosong jika `X:` dipakai project lain. |
| `-ApiUrl 'http://192.168.1.10:8000'` | Alamat yang diperiksa script pada PC. **Atur URL tersebut secara manual pada HP**; default APK tetap `http://127.0.0.1:8000`. |

Pada HP, buka **Panduan → Pengaturan koneksi → Gunakan koneksi USB → Simpan & tes koneksi**. Pengaturan menggunakan namespace lokal lama, sementara alamat cloud yang tersimpan pada build lama tidak dibaca. Jika pernah memakai LAN atau port lain, periksa kembali URL tersimpan sebelum berpindah ke USB.

## 4. Periksa prediksi dan penyimpanan

Contoh permintaan API langsung dari PC, setelah API siap:

```powershell
$manifest = Get-Content -LiteralPath 'src\assets\metadata\v7_model_manifest.json' -Raw | ConvertFrom-Json
$payload = @{
    smiles = 'COc1cc(C=O)ccc1O'
    feature_schema_id = $manifest.feature_schema_id
    bundle_id = $manifest.bundle_id
} | ConvertTo-Json
$result = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/predict' -Method Post -ContentType 'application/json' -Body $payload
$result.scores
```

`/predict` menjalankan validasi, fitur, dan model pada PC; respons memuat SMILES kanonis dan seluruh **109 objek `{label, score}`** sesuai urutan manifest. Vektor fitur tidak dikirim ke Android. Endpoint `/fingerprint` tetap tersedia untuk diagnostik/checksum, bukan jalur inferensi frontend.

Prosedur uji HP:

1. Pilih Vanillin dari katalog dan jalankan prediksi; cocokkan hasil dengan model asli melalui bukti kesetaraan.
2. Buka Riwayat, tutup/buka ulang aplikasi, lalu pastikan hasil bertahan.
3. Tambah Koleksi, ubah nama/catatan, analisis ulang, dan hapus entri uji tanpa menghapus Riwayat.
4. Cari `C2H6O`; pastikan harus memilih satu struktur sebelum prediksi.
5. Coba SMILES salah, multifragmen, air/CO₂, dan senyawa tanpa karbon; hasil invalid tidak boleh menjadi prediksi atau Riwayat baru.
6. Hentikan API sementara, periksa pesan koneksi dan data lokal, kemudian nyalakan ulang dan uji pemulihan.
7. Ulangi tutorial serta periksa sorotan dan keterbacaan pada font HP yang diuji.

Daftar ini merupakan **prosedur**, bukan klaim lulus. Rekam perangkat, konfigurasi, versi APK, langkah, hasil, dan bukti aktual. Skor tidak harus berjumlah 100%; angka bukan intensitas/kadar atau probabilitas persepsi manusia yang sudah terkalibrasi. Aplikasi tidak memprediksi resep campuran maupun keamanan bahan.

## Alternatif jaringan lokal atau port berbeda

Untuk LAN, PC dan HP harus berada pada jaringan yang dapat saling mengakses. Pada terminal API:

```powershell
.\scripts\start-local-api.ps1 -BindAddress '0.0.0.0'
```

Pada terminal Android:

```powershell
.\scripts\run-local-android.ps1 -ApiUrl 'http://192.168.1.10:8000'
```

Ganti IP contoh dengan IPv4 PC sebenarnya, lalu **isi alamat yang sama di Panduan pada HP**. `0.0.0.0` adalah alamat bind, bukan URL untuk HP. Aplikasi menerima localhost atau IPv4 private melalui HTTP/HTTPS; alamat publik/cloud tidak menjadi konfigurasi aktif. Jalur USB tetap pilihan utama.

Untuk port khusus, jalankan API dengan `-Port 8001` dan script Android dengan `-ApiUrl 'http://127.0.0.1:8001'`; script memasang reverse port tersebut. Ubah URL tersimpan pada HP secara manual. Untuk kembali ke default, nyalakan API port 8000, jalankan script Android tanpa `-ApiUrl`, lalu pilih **Gunakan koneksi USB** pada HP.

## Pemeriksaan dan pemecahan masalah

```powershell
npm run lint
npm run test:ci
.\.venv-feature-api\Scripts\python.exe -B -m unittest discover -s feature_api -p 'test_*.py' -v
.\.venv-feature-api\Scripts\python.exe -B scripts\prepare-local-models.py --verify-only
```

Audit kesetaraan numerik tambahan dapat memakai `scripts/verify-local-predictions.py`. Audit ini memerlukan frozen run beserta fitur/split/records dan referensi Python, bukan hanya paket runtime lokal. Dari PC yang memiliki seluruh artefak audit:

```powershell
.\.venv-feature-api\Scripts\python.exe -B scripts\verify-local-predictions.py --api-url 'http://127.0.0.1:8000' --output '.local-run\native-equivalence.json'
```

| Gejala | Tindakan |
| --- | --- |
| Model belum tersedia | Jalankan `start-local-api.ps1 -SetupOnly`; sediakan sumber beku atau isi `-SourceRun` yang benar. |
| Checksum/versi paket berbeda | Cocokkan sumber v7, manifest, salinan `.joblib`, dan requirements. Jangan menonaktifkan pemeriksaan atau menimpa model penelitian. |
| Python/dependency gagal | Gunakan Python 3.12 dan pin requirements proyek; interpreter lebih baru belum tentu cocok dengan NumPy yang digunakan. |
| HP tidak tampil | Periksa kabel data, USB debugging, otorisasi, dan `adb devices -l`. |
| Koneksi gagal di HP | Periksa API PC, URL HP, dan `adb reverse --list`; jalankan script Android setelah USB tersambung ulang. |
| URL khusus berbeda dari HP | `-ApiUrl` hanya memeriksa sisi PC; samakan URL secara manual melalui Panduan. |
| Build gagal karena path panjang | Gunakan drive pendek kosong lewat `-DriveLetter`; jangan menimpa pemetaan project lain. |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | Tanda tangan berbeda. Periksa pilihan migrasi data sebelum menghapus aplikasi; jangan uninstall otomatis. |
| Nama tidak ditemukan | Coba nama/alias yang dikenal, katalog, atau SMILES. PubChem opsional memerlukan `-AllowPubChem` dan internet. |

Hentikan API dengan `Ctrl+C`. Hasil tes, APK, checksum, file yang berubah, dan keterbatasan migrasi dicatat di [MIGRATION_FULL_LOCAL_20261107.md](MIGRATION_FULL_LOCAL_20261107.md). Catatan tes September dan 6 November merupakan arsip implementasi sebelum migrasi; unit test tidak menggantikan pemeriksaan HP atau validasi sensori.
