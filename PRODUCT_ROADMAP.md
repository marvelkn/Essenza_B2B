# Essenza B2B — cakupan dan keputusan implementasi aktif

Tanggal acuan: **7 November 2026**. Dokumen ini berlaku untuk repo **`marvelkn/Essenza_B2B`**, branch kerja **`marvel`**, pada `C:\Users\ACER\Documents\Marvel\Skripsi\Project Skripsi\Essenza_Frontend`.

## Cakupan yang dipertahankan

Essenza merupakan alat bantu eksplorasi **label aroma satu molekul** bagi UMKM/peracik parfum dengan identitas senyawa yang diketahui. Alur inti: **pilih/identifikasi satu struktur → analisis lokal pada PC → tampilkan skor → Riwayat otomatis**. Koleksi tetap manual dan tersimpan pada HP.

| Termasuk implementasi B2B | Di luar cakupan aplikasi penelitian |
| --- | --- |
| Katalog 6.686 senyawa, nama/rumus dengan konfirmasi, SMILES lanjutan | Penyusunan resep dan prediksi campuran parfum |
| Skor 109 label, threshold 0,5, seluruh skor dapat diperiksa | Intensitas, kadar, ketahanan, keamanan, atau peluang persepsi terkalibrasi |
| Riwayat otomatis; Koleksi dengan edit, hapus, dan analisis ulang | Login, transaksi, database server, atau akun cloud |
| Tutorial dan pengaturan koneksi PC–HP | Klaim manfaat pengguna, kompatibilitas iOS, atau kesiapan produksi tanpa evaluasi |

Rencana formulasi, batch, agregasi aroma, atau empat layar pada dokumen brainstorming lama tidak menjadi persyaratan implementasi ini. Tidak ada perluasan cakupan hanya karena ide tersebut pernah dicatat.

## Keputusan implementasi — 7 November 2026

| Bagian | Keputusan |
| --- | --- |
| Full local | **RDKit + model LightGBM asli pada PC**, Android terhubung lewat USB/ADB reverse |
| API aplikasi | **`feature_api.app:app`**, dalam repo frontend; jalur prediksi **`POST /predict`** |
| Model final | **v7 LightGBM D**, 109 model biner asli, 2.056 fitur float32, threshold 0,5 |
| Representasi | Morgan 2.048 bit, radius 2 tanpa chirality, ditambah 8 deskriptor RDKit dalam urutan beku |
| Artefak | Salinan identik `.joblib` pada PC; verifikasi checksum dan versi runtime, tanpa fitting/serialisasi ulang |
| Android | React Native sebagai antarmuka dan penyimpanan; tidak memuat model atau menjalankan inferensi classifier |
| Koneksi | Default semua build `http://127.0.0.1:8000`; alamat localhost/private dapat diatur dari Panduan |
| Internet | Tidak diperlukan untuk prediksi katalog/SMILES setelah setup; PubChem hanya pencarian tambahan opsional dan mati secara default |
| Data pengguna | Identitas B2B, namespace Riwayat/Koleksi, serta data lama dipertahankan |

Perubahan ini menghilangkan konversi dan runtime ONNX dari implementasi aktif, tanpa mengganti algoritma penelitian atau fungsi utama aplikasi. Komputer/API tetap diperlukan untuk prediksi baru; istilah full local tidak berarti aplikasi melakukan seluruh proses secara mandiri di HP.

## Status dan bukti

| Area | Acuan status |
| --- | --- |
| Kode, penyimpanan model, dan setup lokal | `README.md`, `docs/LOCAL_DEVELOPMENT.md`, `docs/B2B_LAB.md`, serta kode aktual |
| File diubah/dihapus dan alasan migrasi | `docs/MIGRATION_FULL_LOCAL_20261107.md` |
| Hasil tes otomatis, kesetaraan skor, APK, dan pengujian HP baru | Hanya bukti aktual pada dokumen migrasi; dokumen roadmap ini tidak menetapkan jumlah tes atau menyatakan uji perangkat lulus |
| Bukti sebelum migrasi | `docs/VERIFICATION.md` dan `docs/QA_20261106.md`, berlabel arsip |
| Hasil penelitian dan model final | Artefak beku pada `Perfume-MultiLabel-Classifier`; tidak dilatih ulang untuk migrasi |

## Keterkaitan dengan skripsi

Laporan utama berada di `C:\Users\ACER\Documents\Marvel\Skripsi\Laporan Skripsi\2521_skripsi_Marvel_Kevin_Nathanael`. Narasi implementasi harus menggambarkan **preprocessing dan inferensi pada PC lokal**, pertukaran struktur/skor dengan Android, serta batas kebutuhan komputer/USB. Bab hasil tidak boleh mengubah metrik eksperimen atau mengganti bukti pengujian lama dengan klaim runtime baru.

Kesetaraan skor memeriksa konsistensi implementasi terhadap model yang sudah dilatih; pengujian tersebut bukan eksperimen kualitas model baru, validasi sensori, atau bukti manfaat untuk UMKM. Data, split, proses training, artefak final, dan evaluasi penelitian tetap dipertahankan.

## Pemeliharaan berikutnya

1. Cocokkan klaim dengan kode, manifest, artefak, dan bukti pengujian terbaru sebelum memperbarui laporan atau dokumentasi.
2. Pertahankan identitas B2B dan perubahan lokal. Jangan mengubah repo B2C, melakukan reset, commit, atau push tanpa instruksi pengguna.
3. Saat kontrak/model berubah, periksa checksum, skema fitur, urutan label, skor, keputusan threshold, integrasi UI, serta data tersimpan.
4. Catat hasil tes sesuai pelaksanaan, termasuk batas perangkat/font dan kondisi gagal yang belum diuji. Tautkan bukti, bukan hanya prosedur.
5. Jangan menambahkan formulasi, keamanan, login, cloud, atau teknologi konversi model sebagai kebutuhan dasar tanpa keputusan pengguna.

## Changelog

### 11 November 2026 - Komparasi kontekstual Suh pada laporan

- Bab IV laporan utama menambahkan tabel hasil test Suh dan kondisi A/D penelitian ini beserta batas perbandingan data, fitur, validasi, serta definisi AUPRC/AP. Bab V merangkum posisi penelitian dengan rujukan ke bagian tersebut, tanpa klaim superioritas lintas studi.
- Hanya laporan dan catatan editorial berubah. Aplikasi, API, model, data, threshold utama 0,5, dan angka eksperimen tetap; tidak menjalankan training, inferensi, atau uji perangkat baru. Cadangan dan QA: workspace output/komparasi_suh_20261111.

### 10 November 2026 - Penghapusan analisis threshold tambahan OOF dari laporan

- Sesuai permintaan penulis, naskah aktif menghapus analisis threshold tambahan OOF beserta rujukan metode, hasil, simpulan, diagram, dan lampirannya. Hasil utama threshold 0,5, seluruh nilai metrik yang dipertahankan, validasi lima seed/lima fold per label, dan pemilihan model berdasarkan AP validasi tetap.
- Tidak mengubah aplikasi, API, kode penelitian, data, model, atau artefak eksperimen; tidak menjalankan training, tuning, inferensi, atau uji perangkat baru. Cadangan sumber, diff, dan QA laporan: workspace output/hapus_threshold_oof_20261110.

### 9 November 2026 - Perbaikan penyajian hasil laporan

- Bab IV serta lampiran evaluasi diperjelas dengan header tabel konsisten, pemisah algoritma, angka terbaik per kolom, dan indikator arah perubahan. Angka hasil penelitian tetap identik.
- Grafik kurasi dan kontras AP/F1 yang sudah tersedia dimuat dalam Bab IV; grafik trial empat/delapan jam ditambahkan dari jejak studi beku. Grafik threshold di lampiran diganti pasangan titik dengan nilai sumber yang sama.
- Hanya penyajian laporan dan skrip render grafik yang berubah; tidak melakukan training, tuning, inferensi, atau uji aplikasi baru. Snapshot, diff, sumber grafik, serta QA: workspace output/hasil_visual_20261109.

### 9 November 2026 - Sitasi anggaran waktu Optuna pada laporan

- Bab II dan Bab III laporan utama mendapat sitasi akiba2019 untuk contoh penggunaan batas waktu pencarian dan studi empat jam pada evaluasi Optuna dengan dataset SVHN.
- Delapan jam tetap merupakan batas operasional penelitian; contoh literatur tidak diklaim menetapkan durasi optimal. Perbandingan empat/delapan jam, metode, data, model, hasil evaluasi, serta implementasi aplikasi tetap. Tidak menjalankan eksperimen ML atau uji aplikasi baru.
- Berkas laporan: src/2.Isi/Bab2.tex, src/2.Isi/Bab3.tex, dan CHANGELOG.md. Cadangan dan QA: workspace output/optuna_budget_sitasi_20261109.

### 8 November 2026 - Tampilan formulir AI dan TTD penulis

- Laporan menghapus catatan a/b di bawah tabel AI dan judul berulang pada halaman lanjutan; asal tanggal/naskah contoh tetap dibedakan pada sel tabel.
- TTD yang diberikan penulis ditempatkan pada empat ruang tanda tangan penulis. Tidak mengubah model, metode, hasil atau kode aplikasi. Cadangan dan QA: workspace output/form_ai_ttd_20261108.

### 8 November 2026 - Format formulir AI dan bukti screenshot laporan

- Lampiran AI laporan utama mengikuti bentuk tabel enam kolom dan identitas pada contoh skripsi, memuat tiga screenshot Claude tanpa perubahan piksel dan dua entri Codex yang telah tercatat.
- Tanggal Claude mengikuti nama berkas sesuai arahan penulis dengan keterangan bahwa waktu percakapan tidak terlihat; prompt terkait berasal dari dokumen contoh, bukan transkrip terverifikasi. Hasil penelitian, metode, model dan aplikasi tetap. Cadangan dan QA: workspace output/lampiran_ai_screenshot_20261108.

### 8 November 2026 - Revisi laporan berdasarkan audit menyeluruh

- Laporan utama dipadatkan pada latar belakang, justifikasi, studi terdahulu dan simpulan; bibliografi aktif 38 menjadi 33 tanpa penambahan sumber. Angka penelitian, dataset, split, model, fitur, threshold dan implementasi aplikasi tetap.
- Peta reproduksi v7 dan manifest pendamping ditambahkan. Pembimbing diperbarui sesuai konfirmasi penulis; formulir AI disiapkan sebagai draf, sementara email/tanggal resmi, riwayat AI terdahulu serta bukti kemiripan/bimbingan masih menunggu pengisian.
- Cadangan, daftar berkas, diff serta pemeriksaan tersedia pada workspace output/revisi_audit_20261108. Tidak ada perubahan kode aplikasi/ML, training, inferensi, build aplikasi atau uji perangkat baru.

### 7 November 2026 - Penomoran contoh fingerprint pada laporan

- Gambar 3.2 pada Bab III mendapat rentang posisi bit di kiri setiap baris, dari 1-32 sampai 2017-2048. Caption menjelaskan perbedaan penomoran tampilan dan indeks kode; seluruh nilai serta urutan fingerprint tetap.
- Berkas laporan: src/2.Isi/Bab3.tex dan CHANGELOG.md. Cadangan dan pemeriksaan: workspace output/penomoran_bit_20261107. Tidak ada perubahan produk, metode, model, atau data.

### 7 November 2026 - Contoh fitur molekul pada laporan

- Bab III menambahkan satu contoh nyata vanilin: SMILES diproses menjadi Morgan 2.048 bit (radius 2 tanpa kiralitas) menggunakan source dan environment penelitian. Array lengkap memuat 25 bit aktif serta 2.023 bit nol; konsep hash dan masukan numerik dijelaskan singkat.
- Vektor fitur gabungan contoh cocok dengan hash referensi API yang sudah tersimpan. Model, data, fitur eksperimen, hasil, dan implementasi tidak berubah; tidak menjalankan training atau prediksi model. Berkas laporan: src/2.Isi/Bab3.tex dan CHANGELOG.md. Cadangan serta bukti: workspace output/contoh_morgan_vanilin_20261107.

### 7 November 2026 - Interpretasi kesalahan pada laporan

- Pembahasan confusion matrix Bab IV mendapat dua kalimat tentang potensi FP menambah dugaan karakter tanpa dukungan anotasi dan FN melewatkan label tercatat dari daftar prediksi positif. Precision dan recall tetap dibaca bersama; dampak relatif FP/FN bagi pengguna belum dievaluasi.
- Perubahan hanya narasi laporan; tidak mengganti pemilihan berdasarkan macro AP validasi, threshold, hasil, atau implementasi. Berkas laporan: src/2.Isi/Bab4.tex dan CHANGELOG.md. Cadangan dan bukti pemeriksaan: workspace output/confusion_interpretasi_20261107.

### 7 November 2026 — migrasi model asli full local

- Pengguna menetapkan PC lokal menjalankan RDKit dan model asli; HP memakai USB untuk mengirim struktur dan menerima hasil.
- Alur aplikasi diarahkan ke `/predict`; model asli disiapkan di `feature_api/models/v7/`, dimuat sekali saat startup API, dan diverifikasi terhadap manifest/checksum sumber.
- Runtime/bridge/model Android dan exporter format konversi dilepas dari alur aktif. Default cloud dihentikan; data lama, fitur utama, hasil training, dan model penelitian dipertahankan.
- Dokumentasi aktif diselaraskan, sementara catatan tes lama ditandai arsip. Hasil pengujian migrasi dan perubahan laporan dicatat terpisah pada dokumen migrasi; tidak disimpulkan dari changelog ini.
