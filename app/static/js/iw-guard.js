// Pengaman halaman ujian & kisi-kisi.
// Catatan jujur: browser TIDAK bisa memblokir screenshot / rekam layar sistem operasi
// atau kamera HP. Skrip ini mempersulit dan mencatat, bukan menjamin.
//
// <body data-guard="exam|read" data-violation-url="/student/exam/violation/12">
(function () {
  const body = document.body;
  const mode = body.dataset.guard;
  if (!mode) return;
  const urlCatat = body.dataset.violationUrl || '';
  const tameng = document.getElementById('guard-shield');
  const teksTameng = document.getElementById('guard-shield-text');
  const judulTameng = document.getElementById('guard-shield-title');
  const tombolTameng = document.getElementById('guard-resume');
  let jedaTerakhir = 0;
  let sedangKirim = false;

  // ---- pelanggaran: dicatat ke server (mode ujian) ----
  async function catat(jenis) {
    if (mode !== 'exam' || !urlCatat || sedangKirim) return null;
    try {
      const r = await fetch(urlCatat, { method: 'POST', body: new URLSearchParams({ kind: jenis }), credentials: 'same-origin' });
      return await r.json();
    } catch (e) { return null; }
  }

  function tutupLayar(pesan, judul, tombol) {
    if (!tameng) return;
    if (teksTameng && pesan) teksTameng.textContent = pesan;
    if (judulTameng && judul) judulTameng.textContent = judul;
    if (tombolTameng && tombol) tombolTameng.textContent = tombol;
    tameng.hidden = false;
  }

  // Satu kali keluar dari ujian memicu beberapa event sekaligus: pindah aplikasi di layar penuh =
  // blur + visibilitychange + fullscreenchange. Semuanya dihitung SATU kejadian (server juga menggabungkan,
  // lihat hitung_keluar di student.py). Dulu terhitung 2, sehingga ujian berhenti pada keluar ke-2.
  const JEDA_SATU_KEJADIAN = 3000;
  async function keluarHalaman(jenis) {
    if (sedangKirim) return;
    const sekarang = Date.now();
    if (sekarang - jedaTerakhir < JEDA_SATU_KEJADIAN) return;
    jedaTerakhir = sekarang;
    if (mode !== 'exam') { tutupLayar('Isi materi ditutup saat kamu meninggalkan halaman ini.', 'Isi disembunyikan', 'Lanjut membaca'); return; }
    const hasil = await catat(jenis || 'pindah_tab');
    peringatan(hasil);
  }

  function peringatan(hasil) {
    if (!hasil || !hasil.active) { tutupLayar(); return; }
    if (hasil.count >= hasil.limit) {
      tutupLayar('Kamu ' + hasil.count + ' kali keluar dari layar ujian. Jawaban dikirim otomatis.', 'Ujian dihentikan', 'Mengirim...');
      kirimOtomatis();
      return;
    }
    tutupLayar('Peringatan ' + hasil.count + ' dari ' + hasil.limit + '. Pada pelanggaran ke-' + hasil.limit + ' jawaban dikirim otomatis. Kejadian ini tercatat untuk guru.', 'Kamu keluar dari layar ujian', 'Kembali ke ujian');
  }

  function kirimOtomatis() {
    const form = document.getElementById('form-ujian');
    if (!form || sedangKirim) return;
    sedangKirim = true;
    const tanda = document.createElement('input');      // tercatat di log guru sebagai kiriman otomatis
    tanda.type = 'hidden'; tanda.name = 'otomatis'; tanda.value = '1';
    form.appendChild(tanda);
    form.dispatchEvent(new Event('submit'));            // kirim sisa log aktivitas dulu
    form.submit();
  }
  window.iwGuard = {
    tandaiKirim: () => { sedangKirim = true; },
    batalKirim: () => { sedangKirim = false; },
    kirimOtomatis,
  };

  document.addEventListener('visibilitychange', () => { if (document.hidden) keluarHalaman(); });
  // klik di dalam materi interaktif (iframe) juga memicu blur: itu bukan keluar halaman
  window.addEventListener('blur', () => { setTimeout(() => {
    if (document.activeElement && document.activeElement.tagName === 'IFRAME') return;
    if (!document.hasFocus()) keluarHalaman();
  }, 150); });

  // ---- layar penuh (mode ujian) ----
  document.addEventListener('fullscreenchange', () => {
    if (mode !== 'exam' || sedangKirim || document.fullscreenElement) return;
    const tombol = document.getElementById('guard-fullscreen');
    if (tombol) tombol.hidden = false;
    keluarHalaman('keluar_layar_penuh');
  });

  // ---- salin, klik kanan, seret, cetak, tombol pintas ----
  ['copy', 'cut', 'paste', 'contextmenu', 'dragstart', 'drop', 'selectstart'].forEach((ev) => {
    document.addEventListener(ev, (e) => {
      const diIsian = e.target.closest && e.target.closest('input, textarea');
      // Di kotak esai siswa boleh menyeleksi teksnya sendiri, tapi tidak boleh menempel / menyeret teks dari luar
      if (diIsian && (ev === 'selectstart' || ev === 'copy' || ev === 'cut' || ev === 'contextmenu' || ev === 'dragstart')) return;
      e.preventDefault();
      if (ev === 'copy' || ev === 'cut') catat('salin');
      if (ev === 'paste' || ev === 'drop') catat('tempel');
      if (ev === 'contextmenu') catat('klik_kanan');
    });
  });

  // ---- tempel dari papan klip HP (khusus kotak jawaban ujian) ----
  // Di HP, teks bisa masuk TANPA event "paste": tombol papan klip di keyboard (Gboard, SwiftKey, Samsung)
  // memasukkannya sebagai ketikan biasa. Tiga lapis:
  //   1. jenis masukan "tempel" (insertFromPaste/Drop/Yank) ditolak sebelum masuk
  //   2. teks yang masuk sekaligus lebih dari BATAS_SEKALI_MASUK huruf dibatalkan (ketikan, saran kata,
  //      dan ketik-geser hanya menambah satu kata; tempelan menambah banyak sekaligus)
  //   3. papan klip dikosongkan saat kotak jawaban disentuh, sehingga salinan dari aplikasi lain hilang
  // Batas jujur: riwayat papan klip di aplikasi keyboard tidak bisa dihapus web; lapis 2 yang menahannya.
  const BATAS_SEKALI_MASUK = 20;
  const isianUjian = (el) => mode === 'exam' && el && el.matches && el.matches('textarea, input[type=text]');
  const sebelum = new WeakMap();     // nilai & seleksi terakhir yang sah per kotak

  function simpanKeadaan(el) {
    sebelum.set(el, { nilai: el.value, awal: el.selectionStart, akhir: el.selectionEnd });
  }
  function kosongkanPapanKlip() {
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText('').catch(() => {});
  }
  let jedaPesan;
  function pesanTempel(el) {
    let p = document.getElementById('guard-tempel');
    if (!p) {
      p = document.createElement('div');
      p.id = 'guard-tempel'; p.setAttribute('role', 'alert');
      p.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:60;max-width:calc(100% - 32px);' +
        'padding:12px 16px;border-radius:12px;background:#3a1512;border:1px solid rgba(255,114,98,.5);color:#fff;font-size:14px;text-align:center';
      document.body.appendChild(p);
    }
    p.textContent = 'Menempel teks tidak diizinkan. Ketik jawabanmu sendiri.';
    p.hidden = false;
    clearTimeout(jedaPesan);
    jedaPesan = setTimeout(() => { p.hidden = true; }, 3500);
  }
  function tolakTempel(el) {
    const lama = sebelum.get(el);
    if (lama) {
      el.value = lama.nilai;
      try { el.setSelectionRange(lama.awal, lama.akhir); } catch (e) {}
    }
    catat('tempel');
    kosongkanPapanKlip();
    pesanTempel(el);
  }

  document.addEventListener('focusin', (e) => {
    if (!isianUjian(e.target)) return;
    simpanKeadaan(e.target);
    kosongkanPapanKlip();            // menyentuh kotak = ada gestur pengguna, browser HP mengizinkan
  });
  document.addEventListener('beforeinput', (e) => {
    if (!isianUjian(e.target)) return;
    const jenis = e.inputType || '';
    if (/^insertFrom(Paste|Drop|Yank|PasteAsQuotation)/.test(jenis)) {
      e.preventDefault();
      tolakTempel(e.target);
      return;
    }
    simpanKeadaan(e.target);         // nilai + seleksi tepat sebelum masukan ini
  }, true);
  document.addEventListener('input', (e) => {
    const el = e.target;
    if (!isianUjian(el)) return;
    const lama = sebelum.get(el);
    if (!lama) { simpanKeadaan(el); return; }
    const terseleksi = Math.max(0, (lama.akhir || 0) - (lama.awal || 0));
    const masuk = el.value.length - (lama.nilai.length - terseleksi);   // huruf yang baru masuk sekaligus
    const jenis = e.inputType || '';
    if (/^insertFrom/.test(jenis) || masuk > BATAS_SEKALI_MASUK) {
      e.stopImmediatePropagation();  // log aktivitas tidak mencatat teks tempelan
      tolakTempel(el);
      return;
    }
    simpanKeadaan(el);
  }, true);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && mode === 'exam') kosongkanPapanKlip(); });

  document.addEventListener('keydown', (e) => {
    const k = (e.key || '').toLowerCase();
    const ctrl = e.ctrlKey || e.metaKey;
    const devtools = k === 'f12' || (ctrl && e.shiftKey && ['i', 'j', 'c'].includes(k)) || (ctrl && k === 'u');
    const diIsian = e.target.closest && e.target.closest('input, textarea');
    // Di kotak esai: Ctrl+A/C/X boleh (teks milik sendiri), Ctrl+V tetap diblokir lewat event paste
    const salin = ctrl && (diIsian ? ['s', 'p'] : ['c', 'x', 'a', 's', 'p']).includes(k);
    if (devtools || salin) {
      e.preventDefault();
      catat(devtools ? 'devtools' : (k === 'p' ? 'cetak' : 'salin'));
    }
  });

  // PrintScreen tidak bisa dicegah, tapi isi langsung disembunyikan dan papan klip dikosongkan
  document.addEventListener('keyup', (e) => {
    if (e.key === 'PrintScreen') {
      tutupLayar('Screenshot tidak diizinkan. Kejadian ini tercatat' + (mode === 'exam' ? ' untuk guru.' : '.'), 'Isi disembunyikan', mode === 'exam' ? 'Kembali ke ujian' : 'Lanjut membaca');
      catat('screenshot');
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText('').catch(() => {});
    }
  });

  window.addEventListener('beforeprint', () => catat('cetak'));

  // ---- tombol "lanjutkan" di tameng ----
  const lanjut = document.getElementById('guard-resume');
  if (lanjut) {
    lanjut.addEventListener('click', async () => {
      if (mode === 'exam' && document.documentElement.requestFullscreen && !document.fullscreenElement) {
        try { await document.documentElement.requestFullscreen(); } catch (e) {}
      }
      tameng.hidden = true;
    });
  }

  // ---- tombol kembali browser tidak meninggalkan halaman ujian ----
  if (mode === 'exam') {
    history.pushState(null, '', location.href);
    window.addEventListener('popstate', () => history.pushState(null, '', location.href));
  }
})();
