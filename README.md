# Essenza Lab — analisis aroma satu senyawa untuk B2B

Essenza membantu UMKM/peracik parfum mengeksplorasi **label aroma satu molekul**. Aplikasi Android menyediakan katalog **6.686 senyawa penelitian** dengan pilihan tambahan dari luar dataset, pencarian nama/rumus dengan konfirmasi struktur, dan input SMILES lanjutan. **RDKit dan 109 model LightGBM D asli berjalan pada komputer lokal**; HP mengirim struktur dan menerima skor melalui API lokal lewat USB.

```text
Android: pilih satu struktur
  -> USB / adb reverse
  -> PC: FastAPI -> validasi RDKit -> 2.056 fitur -> LightGBM asli
  -> Android: 109 skor -> label dengan skor >= 0,5 -> Riwayat otomatis
```

**Full local** berarti preprocessing dan inferensi berlangsung pada PC milik pengguna, tanpa hosting/cloud dan tanpa konversi ONNX. Komputer, API, dan sambungan USB tetap diperlukan untuk **prediksi baru**. Setelah dependency dan model tersedia, prediksi katalog/SMILES tidak memerlukan internet. PubChem hanya opsi tambahan untuk pencarian nama di luar katalog; mati secara default.

## Jalankan dari awal

Panduan lengkap: [LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md).

| Kebutuhan | Pengaturan |
| --- | --- |
| Node.js | >=22.11; dependency dipasang dengan `npm ci` |
| Python | **3.12**, environment `.venv-feature-api` |
| Android | JDK 17/21, Android SDK/ADB, USB debugging pada HP |
| Model | Salinan **109 `.joblib` asli** dari frozen run final v7; tidak termasuk Git |
| Alamat default | **`http://127.0.0.1:8000`** pada seluruh build |

Di terminal pertama:

```powershell
Set-Location -LiteralPath 'C:\Users\ACER\Documents\Marvel\Skripsi\Project Skripsi\Essenza_Frontend'
npm ci
.\scripts\start-local-api.ps1
```

Script API menyiapkan dependency, menyalin model jika belum tersedia, memverifikasi checksum, lalu menjalankan **`feature_api.app:app`**. Sumber model dideteksi dari repo penelitian di folder sebelah; gunakan `-SourceRun 'C:\path\ke\runs\perfume-five-grouped-v7-m2048-d8'` bila lokasinya berbeda. `-SetupOnly` menyiapkan dependency dan model tanpa menyalakan API. Setelah paket lokal lengkap, startup memakai paket tersebut tanpa perlu mengakses repo penelitian.

Di terminal kedua, setelah HP mengizinkan USB debugging:

```powershell
Set-Location -LiteralPath 'C:\Users\ACER\Documents\Marvel\Skripsi\Project Skripsi\Essenza_Frontend'
.\scripts\run-local-android.ps1
```

Script memeriksa kontrak `/health`, memasang aturan reverse, membangun dan memasang APK `local`, lalu membuka aplikasi. APK membawa bundle JavaScript sehingga **tidak membutuhkan Metro** saat digunakan. Lokasi APK: `android/app/build/outputs/apk/local/app-local.apk`. Windows memakai drive pendek `X:` untuk native build dan path fisik untuk bundling.

Di HP, **Panduan → Pengaturan koneksi → Gunakan koneksi USB → Simpan & tes koneksi**. URL lokal disimpan di namespace tersendiri; alamat cloud dari build lama tidak dipakai. Untuk `-ApiUrl` khusus/LAN, script hanya memeriksa alamat tersebut pada PC; **atur URL yang sama secara manual pada HP**, karena opsi ini tidak menyuntikkan URL ke APK.

## Model dan kontrak aplikasi

| Komponen | Implementasi aktif |
| --- | --- |
| Model penelitian | **v7 LightGBM D**, 109 klasifikator biner asli |
| Representasi | Morgan **2.048 bit**, radius **2**, tanpa chirality, ditambah **8 deskriptor RDKit** |
| Input model | **2.056 fitur float32**, urutan sesuai manifest |
| Pemuatan/inferensi | `joblib.load` sekali saat startup API; `predict_proba` kelas positif **1** |
| Ambang label | **0,5**, tetap mengikuti model final |
| Paket lokal | `feature_api/models/v7/label_000.joblib` s.d. `label_108.joblib` |
| Manifest | `src/assets/metadata/v7_model_manifest.json` |

`scripts/prepare-local-models.py` menyalin artefak secara identik dan memeriksa checksum terhadap sumber beku. Script tidak melakukan training atau menyimpan ulang objek model. Total berkas model asli sekitar **250,2 MB** (**250.210.606 byte**); model disimpan pada PC, bukan dalam APK. Runtime Python dipin sesuai lingkungan artefak asli, termasuk LightGBM, scikit-learn, joblib, NumPy, pandas, dan RDKit.

API aplikasi menyediakan:

| Endpoint | Kegunaan |
| --- | --- |
| `GET /health` | Status model siap, runtime, identitas bundle/skema, dimensi, dan kemampuan layanan |
| `POST /resolve` | Kandidat struktur dari nama/rumus; pengguna harus memilih satu |
| `POST /predict` | Validasi struktur, preprocessing, dan inferensi lokal; mengembalikan seluruh 109 skor |
| `POST /fingerprint` | Diagnostik/checksum fitur; tidak digunakan frontend untuk inferensi |

Frontend memeriksa runtime, identitas model/bundle/skema, dimensi, threshold, urutan label, dan skor sebelum membentuk hasil. Tidak ada vektor fitur atau proses inferensi model pada HP. [Alur teknis](docs/B2B_LAB.md) menjelaskan pemisahan tanggung jawab dan batasnya.

## Fitur dan batas penggunaan

- Setiap prediksi berhasil otomatis dicatat di **Riwayat** (maksimal 100 hasil lokal). Bila penyimpanan gagal, hasil tetap terlihat dan dapat dicoba simpan lagi.
- **Koleksi** bersifat manual (maksimal 200 senyawa), dengan nama panggilan/catatan, edit, hapus, dan analisis ulang. Data lama dipertahankan saat memperbarui APK dengan identitas/tanda tangan yang cocok.
- Tutorial lima langkah dapat diulang dari Panduan. Identitas B2B tetap **`com.essenza.lab`**; penyimpanan terpisah dari B2C. Tidak ada login atau database server.
- Skor ditampilkan dalam persen, tetapi **belum merupakan probabilitas terkalibrasi**, serta bukan intensitas, kadar, komposisi, atau keamanan bahan. Skor tidak harus berjumlah 100%.
- Katalog bukan batas domain model. Guard satu fragmen/karbon hanya pemeriksaan dasar. Air, CO₂, campuran, dan input tidak valid ditolak; struktur lain yang diterima tetap dapat berada di luar domain pelatihan.
- Aplikasi tidak menyusun resep atau memprediksi campuran, ketahanan, maupun keamanan parfum. iOS dan kesiapan produksi tidak diklaim.

## Pemeriksaan dan dokumentasi

```powershell
npm run lint
npm run test:ci
.\.venv-feature-api\Scripts\python.exe -B -m unittest discover -s feature_api -p 'test_*.py' -v
.\.venv-feature-api\Scripts\python.exe -B scripts\prepare-local-models.py --verify-only
```

Perintah di atas adalah prosedur pemeriksaan, bukan pernyataan hasil tes. Daftar perubahan serta **bukti aktual migrasi** dicatat pada [MIGRATION_FULL_LOCAL_20261107.md](docs/MIGRATION_FULL_LOCAL_20261107.md). [VERIFICATION.md](docs/VERIFICATION.md) dan [QA_20261106.md](docs/QA_20261106.md) adalah arsip sebelum migrasi, sehingga hasil pengujiannya tidak otomatis berlaku pada implementasi baru.

[PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md) memuat cakupan B2B aktif. Dataset, proses training, model final, dan metrik penelitian tetap berasal dari repo `Perfume-MultiLabel-Classifier`; API penelitian lama di root repo tersebut bukan layanan aplikasi ini.
