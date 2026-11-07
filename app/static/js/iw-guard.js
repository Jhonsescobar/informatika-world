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

  // keluar halaman (pindah tab, pindah aplikasi, alat potong layar yang mengambil fokus)
  async function keluarHalaman() {
    if (sedangKirim) return;
    const sekarang = Date.now();
    if (sekarang - jedaTerakhir < 1500) return;      // blur + visibilitychange dihitung sekali
    jedaTerakhir = sekarang;
    if (mode !== 'exam') { tutupLayar('Isi kisi-kisi ditutup saat kamu meninggalkan halaman ini.', 'Isi disembunyikan', 'Lanjut membaca'); return; }
    const hasil = await catat('pindah_tab');
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
  window.addEventListener('blur', () => { setTimeout(() => { if (!document.hasFocus()) keluarHalaman(); }, 150); });

  // ---- layar penuh (mode ujian) ----
  document.addEventListener('fullscreenchange', async () => {
    if (mode !== 'exam' || sedangKirim || document.fullscreenElement) return;
    const tombol = document.getElementById('guard-fullscreen');
    if (tombol) tombol.hidden = false;
    const hasil = await catat('keluar_layar_penuh');
    peringatan(hasil);
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
