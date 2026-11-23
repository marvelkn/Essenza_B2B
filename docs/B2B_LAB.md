# Alur teknis Essenza B2B — model asli pada PC lokal

Arsitektur aktif per **7 November 2026**. Panduan operasional: [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md). Bukti perubahan dan pengujian: [MIGRATION_FULL_LOCAL_20261107.md](MIGRATION_FULL_LOCAL_20261107.md).

## Pembagian tanggung jawab

```text
Android / React Native
  pilih katalog atau konfirmasi kandidat nama/rumus atau input SMILES
  -> POST /predict, SMILES + feature_schema_id + bundle_id

PC / FastAPI
  validasi satu molekul dan kanonisasi RDKit
  -> Morgan 2.048 bit + 8 deskriptor -> float32[2056]
  -> 109 LGBMClassifier asli yang sudah dimuat
  -> predict_proba kelas positif 1 -> 109 skor berurutan

Android / React Native
  validasi kontrak dan skor
  -> label dengan skor >= 0,5 -> Riwayat otomatis -> layar hasil
```

**Preprocessing dan inferensi sama-sama berlangsung pada PC.** Android tidak membawa berkas model dan tidak menjalankan classifier. USB `adb reverse` menghubungkan `127.0.0.1:8000` pada HP ke API PC. Data Riwayat/Koleksi tetap pada HP; tidak ada database server atau autentikasi akun.

## Sumber model dan preprocessing

Model aktif adalah kandidat **v7 LightGBM D**, `perfume-five-grouped-v7-m2048-d8/lgbm_D`. Tetap ada **109 klasifikator biner independen**, satu per label. Pergantian lokasi inferensi tidak mengubah classifier, dataset, split, optimasi, proses fitting, hasil evaluasi, atau threshold penelitian.

| Bagian | Ketentuan aktif |
| --- | --- |
| Struktur | SMILES satu molekul terhubung; validasi dan kanonisasi RDKit |
| Fingerprint | Morgan **2.048 bit**, radius **2**, `includeChirality=false` |
| Deskriptor, berurutan | **MolWt, MolLogP, NumHDonors, NumHAcceptors, TPSA, NumRotatableBonds, HeavyAtomCount, RingCount** |
| Vektor | Fingerprint lebih dulu, lalu delapan deskriptor; **float32**, **2.056 nilai finite** |
| Artefak | `label_000.joblib` s.d. `label_108.joblib`, salinan identik dari `lgbm_D` final |
| Inferensi | `joblib.load` sekali saat startup; `LGBMClassifier.predict_proba(..., num_threads=1)[:, 1]` |
| Kelas/threshold | Kelas `[0, 1]` diverifikasi; positif apabila **skor >= 0,5** |

Tidak ada scaler atau preprocessing baru yang dipasang saat migrasi. Model lokal tetap memakai representasi yang sudah ditetapkan eksperimen final. API tidak memanggil `fit`, mengubah bobot model, atau menyimpan ulang artefak.

`scripts/prepare-local-models.py` membaca bundle serta completion manifest sumber, memeriksa SHA-256 model, lalu menyalin model ke `feature_api/models/v7/`. Paket runtime lokal dapat diperiksa dengan `--verify-only` tanpa repo penelitian. Pada startup, `NativePredictor` memeriksa manifest, checksum, versi paket, jenis classifier, jumlah fitur, dan kelas sebelum melayani prediksi. Satu model bermasalah menggagalkan kesiapan paket; tidak ada hasil prediksi parsial.

| Identitas | Nilai |
| --- | --- |
| `runtime` / `model_format` | **`lightgbm` / `joblib`** |
| `model_id` | `perfume-five-grouped-v7-m2048-d8/lgbm_D` |
| `bundle_id` paket asli lokal | `5970c19fffb56f3ff0a4d7f3fa1bcbb1f2b2c5743989c4cf5a5a6d28be68b344` |
| `feature_schema_id` | `dd5d2e2455f7fb3a8f127437d2654a1b74a13f88f9404fcf4b644726a2d907f7` |
| SHA-256 bundle sumber penelitian | `e29f8216b0b4ed0dcdbd0f28bac28a485ec0ceebbf81619f8609f5ee637898a9` |

Bundle ID berubah karena format paket runtime berubah. Skema fitur, model penelitian asal, dan threshold tetap. Manifest di aplikasi dan API harus diperbarui bersama; pemeriksaan ini mencegah aplikasi menerima layanan dengan paket lain.

## Input, API, dan hasil

1. Katalog lokal berisi **6.686 senyawa bernama** dari dataset final. Pencarian dalam modal hanya menyaring pilihan; pilihan menghasilkan SMILES yang dikirim ke API.
2. Mode nama/rumus memakai **`POST /resolve`**. Nama/alias dicocokkan ke katalog terlebih dahulu. PubChem hanya dipakai bila diaktifkan; rumus seperti `C2H6O` dapat menghasilkan beberapa isomer. Pengguna harus memilih satu struktur sebelum prediksi.
3. Mode SMILES menerima struktur langsung. Semua jalur prediksi berakhir pada validasi yang sama: struktur valid, satu fragmen, dan guard senyawa yang didukung. `Air`/`CO2` dapat dikenali oleh pencarian, tetapi tidak diprediksi.
4. **`POST /predict`** membutuhkan salah satu dari `smiles` atau `compound_name`, ditambah `feature_schema_id` dan `bundle_id`. Alur UI mengirim SMILES yang sudah dipilih agar identitas molekul jelas.
5. API mengembalikan `status`, `runtime`, identitas model/bundle/skema, `primary_threshold`, `label_count`, `input_dimensions`, SMILES kanonis, serta **109 objek `{label, score}`**. Urutan sesuai manifest dan skor berada pada 0–1. Vektor fitur dikeluarkan dari respons prediksi.
6. Frontend menolak identitas/dimensi/threshold yang berbeda, label hilang/berulang/tertukar, atau skor tidak valid. Seluruh skor disimpan; label positif diurutkan untuk tampilan setelah threshold tetap diterapkan. Skor tidak dinormalisasi agar totalnya 100%.

**`GET /health`** memeriksa status paket siap dan kontrak model. **`POST /fingerprint`** dipertahankan untuk diagnostik atau checksum fitur; frontend tidak menggunakannya untuk menjalankan model.

## Riwayat, Koleksi, dan kondisi gagal

Setiap inferensi berhasil membentuk hasil dengan input, SMILES kanonis, nama sampel, waktu, `modelId`, `bundleId`, label positif, serta semua skor. Hasil otomatis disimpan ke **Riwayat** sebelum layar hasil dibuka. Bila penyimpanan gagal, hasil tetap tersedia dengan aksi coba simpan lagi; inferensi tidak perlu diulang. Kegagalan API/model tidak membuat catatan hasil.

**Koleksi** hanya berisi senyawa yang disimpan manual. Pengguna dapat mengubah nama/catatan, menghapus, dan melakukan analisis ulang; analisis ulang memakai `/predict` dan menghasilkan Riwayat baru. Batas lokal tetap **100 hasil** dan **200 senyawa**. Identitas `com.essenza.lab` serta namespace penyimpanan tidak diubah. Riwayat lama tidak dikosongkan atau diklaim sebagai hasil runtime baru.

Antrean prediksi, timeout, AbortController, dan versi request menjaga hasil yang terlambat setelah pengguna berpindah layar. Server memakai model yang sudah dimuat dan membatasi eksekusi inferensi bersama melalui lock. Prediksi baru dari HP memerlukan jalur API yang tersedia, sementara data lokal yang sudah tersimpan tetap dapat dibaca ketika jalur tersebut terputus.

## Komponen utama

| Berkas | Tanggung jawab |
| --- | --- |
| `feature_api/app.py` | Resolve, validasi/fitur RDKit, endpoint prediksi dan health |
| `feature_api/native_model.py` | Validasi paket/runtime, pemuatan model, dan inferensi asli |
| `scripts/prepare-local-models.py` | Menyiapkan salinan artefak dan manifest terverifikasi |
| `scripts/verify-local-predictions.py` | Audit numerik terhadap artefak/vektor beku dan HTTP bila sumber audit tersedia |
| `src/services/v7Prediction.js` | REST, kontrak respons, pembatalan, antrean, serta metadata hasil |
| `src/services/featureApiConfig.js` | URL localhost/private; semua build default USB, pengaturan lokal tetap |
| `src/assets/catalog/compounds.json` | Pilihan nama/struktur lokal yang dapat direproduksi dari data beku |
| `src/screens/`, `src/storage/`, `src/tutorial/` | Alur pengguna, persistensi HP, dan panduan lima langkah |

## Batas kesimpulan

Katalog bukan jaminan domain atau kualitas prediksi semua molekul. Guard organik/satu fragmen hanya penyaringan dasar. Skor belum dikalibrasi sebagai probabilitas persepsi manusia; angka tidak menyatakan intensitas, kadar, komposisi, atau keamanan bahan. Aplikasi tidak memprediksi resep campuran, performa parfum, reaksi kimia, atau manfaat pengguna tanpa evaluasi tersendiri.

Prediksi baru tetap membutuhkan PC dan API lokal. PubChem memerlukan internet hanya bila opsi tersebut diaktifkan. Pengujian unit, kesetaraan skor, build, dan uji HP menjawab pertanyaan yang berbeda; hasil aktual serta batas perangkat harus dibaca dari dokumen migrasi, bukan disimpulkan dari arsitektur ini. Catatan sebelum migrasi tetap sebagai arsip dan tidak membuktikan keberhasilan implementasi terbaru.
