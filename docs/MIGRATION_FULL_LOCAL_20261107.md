# Migrasi Essenza B2B ke full local — 7 November 2026

Implementasi aktif sekarang menjalankan **RDKit dan model LightGBM asli pada PC lokal**, sedangkan Android mengirim struktur melalui USB dan menerima hasil. ONNX tidak menjadi runtime, dependency, bridge, atau aset APK. API FastAPI sudah ada sebelum migrasi; algoritma/framework penelitian tidak diganti dan tidak ada training ulang.

## Arsitektur dan alasan

```text
Android: pilih/konfirmasi satu struktur
  -> POST /predict melalui USB + adb reverse
  -> PC: validasi RDKit -> 2.056 fitur float32 -> 109 LGBMClassifier asli
  -> 109 skor + identitas paket -> Android: hasil + Riwayat otomatis
```

Model dimuat sekali dengan `joblib.load` pada startup API. Pemanggilan `predict_proba(..., num_threads=1)[:, 1]` memakai kelas positif 1; satu thread membatasi beban serving dan tidak mengubah bobot model. Paket disalin byte-identik, bukan dilatih, dikonversi, atau diserialisasi ulang. Startup memeriksa checksum dan versi runtime; aplikasi memeriksa kedua ID kontrak, urutan 109 label, threshold, dimensi, dan skor finite 0–1.

| Kontrak | Nilai |
| --- | --- |
| Model | **v7 LightGBM D**, `perfume-five-grouped-v7-m2048-d8/lgbm_D` |
| Input | **2.048 bit Morgan radius 2 tanpa chirality + 8 deskriptor**, 2.056 fitur float32, tanpa scaler tambahan |
| Output | **109 skor**, threshold utama **0,5**, tanpa pemaksaan top-k |
| Source bundle SHA-256 | `e29f8216b0b4ed0dcdbd0f28bac28a485ec0ceebbf81619f8609f5ee637898a9` |
| Feature schema ID | `dd5d2e2455f7fb3a8f127437d2654a1b74a13f88f9404fcf4b644726a2d907f7` — tetap |
| Native bundle ID | `5970c19fffb56f3ff0a4d7f3fa1bcbb1f2b2c5743989c4cf5a5a6d28be68b344` — baru karena berkas paket memakai model asli |
| Model pada PC | `feature_api/models/v7/label_000.joblib` s.d. `label_108.joblib`, **250.210.606 byte** |
| API | `feature_api.app:app`, default **http://127.0.0.1:8000**, PubChem mati |

**Full local bukan operasi mandiri di HP.** PC/API dan USB dibutuhkan untuk prediksi baru. Setup awal dapat membutuhkan internet untuk dependency; setelah tersedia, katalog/SMILES dan prediksi tidak memerlukan hosting atau internet. Riwayat dan Koleksi tetap pada HP. Tidak ada login, transaksi, database server, atau perluasan ke formulasi/campuran.

## Berkas diubah/ditambahkan dan penggantinya

| Area / berkas | Perubahan dan alasan |
| --- | --- |
| `feature_api/app.py` | API lokal menambahkan `/predict`, memuat model saat startup, mengembalikan skor; `/fingerprint` tetap diagnostik. Health memastikan model asli siap. |
| `feature_api/native_model.py` **baru** | Loader model asli, pemeriksaan checksum/versi/kelas/fitur, inferensi lengkap atau gagal seluruhnya. |
| `scripts/prepare-local-models.py` **baru** | Menyalin 109 artefak asli terverifikasi. `--verify-only` tidak membutuhkan sumber penelitian setelah paket tersedia. |
| `scripts/verify-local-predictions.py` **baru** | Memeriksa salinan, fitur, HTTP, seluruh skor/keputusan, dan referensi Python tanpa fitting. |
| `src/assets/metadata/v7_model_manifest.json` | Manifest native dengan hash `.joblib`; label, skema, dan threshold dipertahankan. |
| `src/services/v7Prediction.js` | `/fingerprint` + native bridge diganti `/predict`; validasi hasil, antrean, pembatalan, serta batas metadata nama tetap berlaku. |
| `src/services/featureApiConfig.js` | Default localhost untuk semua build, hanya host lokal/private, namespace lokal dipertahankan; tidak mengambil URL cloud lama. |
| `src/screens/GuideScreen.js` | Penjelasan PC mengerjakan preprocessing dan inferensi; health memeriksa kontrak prediksi asli. |
| `android/app/build.gradle`, `MainApplication.kt` | Runtime, task verifikasi model Android, konstanta URL khusus bridge, dan registrasi paket model dilepas; HTTP lokal tersedia. |
| `feature_api/requirements.txt`, `requirements.txt` | Dependency serving berasal dari framework penelitian; SciPy dipin 1.15.3. Root requirements mengacu satu daftar API. |
| `scripts/start-local-api.ps1`, `scripts/run-local-android.ps1`, `app.py`, `.gitignore` | Setup model asli dan health native; alias API lokal, model PC diabaikan Git; `-ApiUrl` khusus diatur manual pada HP. |
| `__tests__/v7Prediction.test.js`, `__tests__/featureApiConfig.test.js` | Regresi kontrak skor/API dan URL seluruh build; tidak memakai mock native bridge. |
| `feature_api/test_app.py`, `test_native_model.py` **baru**, `fixtures/v7_reference.json` **baru** | Endpoint model asli, 218 skor referensi, input gagal, paket/versi rusak, serta penolakan sebelum deserialisasi. |
| Frontend `README.md`, `AGENTS.md`, `PRODUCT_ROADMAP.md` **baru**, `docs/LOCAL_DEVELOPMENT.md`, `docs/B2B_LAB.md` | Panduan dan instruksi aktif diselaraskan. `docs/VERIFICATION.md` dan `docs/QA_20261106.md` diberi penanda arsip sebelum migrasi, isi historis utuh. |
| Backend `README.md`, `KODE_ML/README.md`, `KODE_ML/01_Materi/Peta_Notebook.md`, `PROJECT_CONTEXT.md`, `PROJECT_OVERVIEW.md`, `IMPLEMENTATION_STATUS.md`, `INFERENCE_GUIDE.md`, `SAFE_EXECUTION_PLAN.md` | Status v7 PC asli dan pemisahan API aplikasi dari API legacy v6; bukti lama diberi konteks historis. |
| Backend `requirements_training.txt` | Lima pin alat konversi yang tidak dipakai dihapus dari instalasi operasional; metode training tidak diubah. Requirements penelitian dan freeze historis tetap identik. |
| `KODE_ML/08_Prediksi_Molekul.ipynb` | Hanya markdown sel 0; **10 sel kode, output, metadata, dan sel lainnya identik**. |
| `KODE_ML/PANDUAN_BELAJAR_DARI_NOL.pdf` dan generator editorial | Panduan tetap **22 halaman/22 bookmark/15 rute**; hanya isi halaman 21 dan tanggal disesuaikan. Seluruh angka dipertahankan. |
| Roadmap referensi workspace | Ditandai arsip, menambahkan keputusan 7 November dan menunjuk roadmap repo aktif; kode salinan lama tidak diubah. |

### Dilepas dari jalur aktif

- Frontend: `EssenzaOnnxModule.kt`, `EssenzaOnnxPackage.kt`, `scripts/export-v7-onnx.py`, `scripts/requirements-export.txt`, `vercel.json`, dependency `onnxruntime-android`, serta **109 `.onnx`** pada `android/app/src/main/assets/models/v7/`.
- Backend: `export_for_mobile.py`, `src/benchmark_onnx.py`, `tests/test_export.py`; salinan asli disimpan di `C:\Users\ACER\Documents\ChatGPT\Project Skripsi\output\full_local_20261106\removed\backend` dan ZIP terverifikasi.
- Pin operasional lama: `onnx`, `onnxruntime`, `onnxmltools`, `skl2onnx`, dan `protobuf` yang hanya diperlukan alat konversi.

**Arsip/provenance tidak dihapus massal.** Freeze environment lama, completion manifest, protokol, keluaran notebook tersimpan, dan catatan bertanggal dapat menyebut teknologi terdahulu. Referensi tersebut bukan dependency/runtime aplikasi. Mengubahnya akan merusak jejak reproduksi; teks status aktif dan laporan terkompilasi sudah memakai arsitektur baru. API root backend v6 tetap berlabel legacy dan tidak dipakai aplikasi v7.

### Revisi laporan utama

Lokasi sumber utama: `C:\Users\ACER\Documents\Marvel\Skripsi\Laporan Skripsi\2521_skripsi_Marvel_Kevin_Nathanael`. **18 berkas** berikut direvisi; artikel template dan grafik/angka hasil penelitian tidak ditulis ulang:

- `CATATAN_PENYELARASAN_BACKEND.md`
- `CATATAN_REVISI_V6.md`
- `CHANGELOG.md`
- `Makefile`
- `PERUBAHAN_HASIL_EKSPERIMEN_20260929.md`
- `README.txt`
- `REVIEW_LAPORAN_20261016.md`
- `REVIEW_LAPORAN_20261028.md`
- `assets/pdf/alur_penelitian_lima_sumber_terperinci.tex`
- `pustaka.bib`
- `src/1.Awal/07a-Abstrak.tex`
- `src/1.Awal/07b-Abstract.tex`
- `src/2.Isi/Bab1.tex`
- `src/2.Isi/Bab2.tex`
- `src/2.Isi/Bab3.tex`
- `src/2.Isi/Bab4.tex`
- `src/2.Isi/Bab5.tex`
- `src/3.Akhir/rincian_reproduksi.tex`

Abstrak Indonesia/Inggris, Bab I–V, kedua diagram arsitektur, tabel pengujian, lampiran, bibliografi aktif, serta dokumentasi/changelog telah diperiksa. **23 tabel nonfungsional, 7 persamaan, angka abstrak, fase diagram 1–4, dan aset ilmiah tetap identik.** Sumber utama dikompilasi ulang dengan sukses menjadi **89 halaman**, tanpa penyebutan ONNX pada PDF aktif dan tanpa error/overfull/rujukan tidak terdefinisi/glyph hilang yang diperiksa.

## Hasil pengujian aktual

| Pemeriksaan | Hasil | Bukti lokal |
| --- | --- | --- |
| Frontend | **7 suite / 82 tes Jest lulus**, ESLint exit 0 | `jest-results.json` |
| API dan integritas model | **18 tes lulus** pada environment biasa dan environment bersih; pip check tidak menemukan dependency rusak | `api-tests.log`, `clean-api-tests.log` |
| Environment bersih | **32 paket**, tanpa `onnx`, `onnxruntime`, `onnxmltools`, `skl2onnx` | `clean-runtime.json` |
| Salinan model vs sumber | **3.706 skor persis sama**, selisih maksimum **0**, keputusan threshold berbeda **0** | `native-parity.json` |
| HTTP `/predict` vs sumber | **34 request / 3.706 skor persis sama**, selisih maksimum **0**, keputusan berbeda **0** | `native-parity.json` |
| Referensi molekul | **218 skor** Vanillin/Ethanol identik; **16/7 label positif** | `native-parity.json` dan fixture |
| Preservasi penelitian | **1.269 berkas dilindungi identik**, tidak ada yang berubah/hilang; **7 tes baca-saja lulus** | `research-preservation.json`, `research-readonly-tests.log` |
| APK | Build local **1m 54s**, terpasang pada **SM-G990E / Android 16 / API 36** | `.local-run/android-build.log`, `device-final.json` |
| Isi APK/dependency | **Tidak ada** model `.onnx`/`.joblib`, library ONNX, atau penanda bridge lama pada DEX; dependency Gradle bersih | `apk-audit.json`, `android-runtime-dependencies.log` |
| Laporan dan panduan | **89 halaman** + **22 halaman**, kompilasi/render/visual QA lulus | `report-final/qa.json`, `guide/qa.json` pada staging bukti |

Matriks kesetaraan berisi **32 vektor train beku + Vanillin/Ethanol**, total 34 × 109. Seluruh fitur hasil RDKit/aplikasi cocok; 34 struktur eligible, tanpa pengecualian guard. Ini menguji kesetaraan implementasi, **bukan pengukuran akurasi, signifikansi, atau generalisasi baru**. Tidak ada data test, label, split, fitting, tuning, atau model penelitian yang diubah.

### Pengujian HP baru, 7 November 2026

| Skenario | Hasil teramati |
| --- | --- |
| Riwayat lama sesudah pembaruan APK | **8 hasil lama tetap ada**, termasuk `UJI-LOCAL-VANILLIN` tanggal 29 Oktober. |
| Vanillin dari katalog | **16 label, Vanilla 99,4%**, otomatis tersimpan melalui API native. |
| Koleksi | Tambah, edit nama/catatan, restart, analisis ulang, dan hapus **lulus**; hasil analisis tetap pada Riwayat. |
| C2H6O | Ethanol/Dimethyl ether tampil terpisah; tanpa konfirmasi prediksi diblokir. Ethanol: **7 label, Ethereal 95,3%**, tersimpan. |
| `not-smiles`, `CCO.O`, `O`, `O=C=O`, `[Na+]` | Ditolak dengan pesan yang sesuai; Riwayat tetap **11** setelah lima kegagalan. |
| Proses API dimatikan | Pesan koneksi tampil; Riwayat **11** dan layar Koleksi tetap dapat dibuka. |
| API dimulai ulang | Prediksi CCO berhasil lagi, **7 label**, tersimpan; pengaturan koneksi menyatakan siap. |
| Restart akhir | Riwayat **12** = 8 lama + 4 QA baru; entri lama tetap dapat dicari, Koleksi uji kosong. |

XML, PNG, prosedur JSON, serta baris PASS pelaksanaan berada di `C:\Users\ACER\Documents\ChatGPT\Project Skripsi\output\full_local_20261106\phone-evidence`. Proses server benar-benar dihentikan dan dimulai ulang, bukan hanya melepas reverse; detailnya ada di `server-interruption.json`. API akhirnya siap di port 8000, reverse USB tersedia, font tetap **1,0**, resolusi **1080 × 2340**.

Empat hasil QA sengaja ditinggalkan untuk diperiksa: **LOCAL-NATIVE-20261107-Vanillin**, **LOCAL-NATIVE-20261107-Koleksi**, **LOCAL-NATIVE-20261107-Ethanol**, dan **LOCAL-NATIVE-20261107-Recovered**. Hanya entri Koleksi buatan pengujian yang dihapus; delapan hasil pengguna sebelumnya dipertahankan.

## Menjalankan dan batas kesimpulan

Terminal PC pertama: `scripts/start-local-api.ps1`. Terminal kedua: `scripts/run-local-android.ps1`. Panduan lengkap ada di [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md). Model yang sudah tersalin dapat diverifikasi dengan `scripts/prepare-local-models.py --verify-only` tanpa repo penelitian. Audit kesetaraan penuh masih membutuhkan sumber penelitian beku.

APK final **28,486,530 byte**, SHA-256 `9fa96e9c47dfcbdfbb02de6270e1760144415efa14d62930e100f63a45cf7c35`. Model tidak disertakan dalam APK; seluruh inferensi memakai LightGBM pada PC. Identitas **com.essenza.lab**, penyimpanan lokal, katalog, tutorial, dan fungsi inti dipertahankan.

Pengujian mencakup satu HP dan skenario di atas. Seluruh 6.686 senyawa, beban konkuren besar, timeout berkepanjangan, iOS, seluruh ukuran/font, manfaat UMKM, serta validasi sensori tidak diuji ulang. Skor tetap **belum terkalibrasi**, bukan intensitas/kadar/komposisi/keamanan. Guard struktur tidak membuktikan semua masukan berada dalam domain pelatihan. Batas evaluasi ilmiah sebelumnya tetap berlaku.

## Daftar lengkap dan backup

Manifest lengkap setiap berkas beserta aksi, hash sebelum/sesudah, model salinan, dan lokasi arsip: `C:\Users\ACER\Documents\ChatGPT\Project Skripsi\output\full_local_20261106\changes.json`. Snapshot frontend (217 berkas) dan laporan (82 berkas), backup dokumentasi/backend/guide, serta manifest ZIP telah diverifikasi di `C:\Users\ACER\Documents\ChatGPT\Project Skripsi\output\full_local_20261106`. Tidak ada reset, commit, push, atau perpindahan branch; frontend tetap **marvel**, backend tetap **main**.

Paket sumber laporan siap diunggah ke Overleaf: `C:\Users\ACER\Documents\ChatGPT\Project Skripsi\output\full_local_20261106\deliverables\laporan_full_local_20261107.zip`; seluruh **82 sumber** diverifikasi terhadap folder utama. PDF hasil kompilasi utama: `C:\Users\ACER\Documents\Marvel\Skripsi\Laporan Skripsi\2521_skripsi_Marvel_Kevin_Nathanael\output\pdf\SKRIPSI_full_local_20261107.pdf`.

## Verifikasi pilihan cepat katalog (23 November 2026)

Pilihan cepat bertambah dari tiga menjadi tujuh dengan Limonene, Eugenol, Menthol, dan Citral. Setiap nama cocok dengan tepat satu entri katalog yang berisi SMILES.

ESLint dan 83 tes Jest pada tujuh rangkaian lulus. APK lokal ARM64 berhasil dibangun dengan ID `com.essenza.lab` dan SHA-256 `9A89EE0775514F69A628C109272AE4B6ACF0E70FAA6BB494C522DDBD8354FC4C`. Build ini belum dipasang atau diperiksa langsung di HP.

## Verifikasi nama umum dan CAS (23 November 2026)

Katalog menampilkan nama umum yang sudah tersedia pada entri yang sama. Alias Stilbene menjadi judul untuk CID 11502, dengan nama asli tetap terlihat. Katalog dasar, SMILES, dan layanan prediksi tidak berubah.

Metadata CAS berasal dari stimulus GoodScents, Leffingwell, dan Arctander yang ditautkan melalui provenans dataset beku. Generator memeriksa checksum, identitas struktur, dan konflik pada audit sumber. Sebanyak 4.431 dari 6.686 entri memiliki satu nomor CAS yang lolos dan dapat dicari. Contoh Vanillin tampil sebagai CID 1183 dan CAS 121-33-5. Regenerasi metadata menghasilkan berkas identik.

ESLint dan 85 tes Jest pada tujuh rangkaian lulus, termasuk pencarian CAS dan kesesuaian struktur yang dikirim untuk prediksi. APK `com.essenza.lab` ARM64 dengan SHA-256 `D564EBE3739C9A463F853C1A50C3A9048A93A72702D1E6103858276FEB82C5AE` memuat tampilan dan metadata CAS. Build ini belum diperiksa langsung di HP.

## Verifikasi senyawa tambahan di luar dataset (23 November 2026)

Katalog aplikasi memprioritaskan empat struktur tambahan dengan tanda **Di luar dataset**. Asal identitas Velberry, Hydrofleur, Mevanyl, dan Petalia dicatat di [berkas katalog tambahan](../src/assets/catalog/external-compounds.json). Hydrofleur memakai representasi yang stereokimianya belum ditentukan di sumber. CID Petalia belum terverifikasi.

RDKit memeriksa setiap tambahan sebagai satu molekul terhubung dan mengonfirmasi nol kecocokan konektivitas tanpa stereokimia terhadap seluruh 6.686 entri beku. Hash `records.csv` cocok dengan manifest dan pasangan ID–SMILES asli tetap identik. Keterangan eksploratif di layar hasil menggunakan SMILES kanonik dari API sehingga status juga dapat ditampilkan saat hasil dibuka dari Riwayat.

Keempat permintaan `POST /predict` ke API lokal mengembalikan 109 skor dari LightGBM D v7 dengan 2.056 fitur dan threshold 0,5. Tes ini memeriksa inferensi dan kontrak keluaran. Pengukuran akurasi eksternal memerlukan label pembanding independen.

ESLint dan 86 tes Jest pada tujuh rangkaian lulus. APK lokal ARM64 `com.essenza.lab` berhasil dibuat dengan SHA-256 `245EEF75A101DD115E39F0C9B234DF3BA9AF708976A05A21D48C18A8A7DA6F23`. Build ini belum diperiksa langsung di HP.

## Perluasan daftar senyawa di luar dataset (23 November 2026)

Sebanyak 54 struktur ditambahkan pada daftar aplikasi. Sumbernya mencakup 50 struktur dari rekaman PubChem yang ditautkan ke IFRA Transparency List dan empat senyawa pewangi Givaudan dari Annex 7.5 laporan OECD ENV/CBC/MONO(2021)9. Pemilihan menyaring kandidat dengan peran fungsional yang tampak, termasuk pelarut, pewarna, polimer, dan campuran. Tautan sumber setiap entri tersedia di [katalog tambahan](../src/assets/catalog/external-compounds.json). Setelah empat entri awal dihitung, katalog berisi 58 struktur tambahan dan 6.744 pilihan total. Nomor CAS ditampilkan untuk 54 entri tambahan yang mempunyai pemetaan tercatat.

Pemeriksaan RDKit dan konektivitas InChI membandingkan 58 entri tambahan dengan 6.686 struktur yang dipakai penelitian. Tidak ditemukan duplikat terhadap katalog penelitian atau di antara entri tambahan. Hash katalog dasar dan hash berkas `records.csv` diverifikasi. Seluruh 58 permintaan `POST /predict` mengembalikan 109 skor valid dengan label, skema fitur, dan identitas LightGBM D v7 sesuai manifest. Skor tersebut berasal dari inferensi dan tidak disimpan ke katalog.

ESLint dan 86 tes Jest pada tujuh rangkaian lulus. Build pertama menganggap bundel tetap mutakhir setelah hanya JSON berubah. Setelah direktori JSON katalog ditetapkan sebagai masukan Gradle, bundel dibuat ulang. Paket Android lokal ARM64 `com.essenza.lab` memuat semua 58 ID dan memiliki SHA-256 `030AFA9E5716E482695C499B832788328A6F1D021763F93D8463F18BFC5264CB`. Build ini belum diperiksa langsung di HP.
