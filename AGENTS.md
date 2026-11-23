# Essenza Lab — React Native B2B, analisis lokal

Scope: alat bantu klasifikasi label aroma **satu molekul**. Repo aktif `marvelkn/Essenza_B2B`, branch kerja `marvel`; jangan mengubah repo Yoga/B2C tanpa instruksi pengguna.

- Periksa branch, remote, status Git, instruksi, dan file aktual sebelum mengubah kode. Pertahankan perubahan lokal yang belum di-commit; jangan reset, commit, atau push tanpa instruksi pengguna.
- Gunakan aset yang sudah dipilih Yoga. Jangan menggambar ulang atau menggantinya tanpa permintaan.
- Layar, logika, dan tes memakai JavaScript. Android memakai bootstrap Kotlin standar; **preprocessing dan inferensi berjalan pada PC melalui API Python lokal**, bukan native bridge model pada HP.
- Model aktif tetap **v7 LightGBM D**, **109 label**, **2.048 bit Morgan radius 2 tanpa chirality + 8 deskriptor RDKit = 2.056 fitur float32**, threshold **0,5**. Jangan mengganti dengan v6, model 25 label, atau RF 143 label.
- Sumber riset `Perfume-MultiLabel-Classifier` tetap beku untuk training, data, evaluasi, dan artefak model. Jangan melakukan fitting, resampling, perubahan hasil, atau serialisasi ulang model untuk migrasi aplikasi.
- API aplikasi ada di `feature_api/` frontend, entrypoint **`feature_api.app:app`**. Paket asli `.joblib` disiapkan di `feature_api/models/v7/` melalui `scripts/prepare-local-models.py`, dengan checksum sumber dan manifest. Model dimuat sekali saat startup dan dipanggil memakai LightGBM asli.
- Frontend memakai **`POST /predict`**, menerima seluruh 109 skor, dan memvalidasi identitas model/bundle/skema serta urutan label. `/fingerprint` hanya diagnostik. Jangan menambahkan kembali konversi ONNX, runtime model Android, atau cloud sebagai kebutuhan alur lokal tanpa keputusan pengguna.
- Semua build memakai default **`http://127.0.0.1:8000`**; USB terhubung lewat `adb reverse`. URL lokal/private dapat diatur dari Panduan. PubChem opsional dan mati secara default; jangan menyebut seluruh alur mandiri di HP atau tanpa komputer.
- Pertahankan **`com.essenza.lab`**, namespace Riwayat/Koleksi, dan data lama. Tidak ada kebutuhan login, transaksi, atau database server pada cakupan ini.
- Jangan membuat prediksi dummy tampak sebagai hasil model. Tandai riwayat demo lama sebagai DEMO. Skor bukan komposisi, kekuatan, kadar, keamanan, atau probabilitas persepsi manusia terkalibrasi.
- Perubahan model/skema harus diperiksa terhadap manifest, checksum model asli, preprocessing, serta kesetaraan skor dan keputusan threshold. Jangan menonaktifkan pemeriksaan kontrak agar error hilang.
- Jalankan lint, tes relevan, verifikasi paket, dan uji Android bila tersedia. Catat bukti aktual pada dokumen migrasi/QA; pisahkan prosedur, hasil lama, dan tes baru. Jangan mengklaim HP, iOS, atau manfaat pengguna sudah diuji tanpa bukti.
- Gunakan `PRODUCT_ROADMAP.md`, `README.md`, dan `docs/LOCAL_DEVELOPMENT.md` pada repo aktif sebagai acuan. Arsip sebelum migrasi bukan deskripsi arsitektur berjalan.
