/* Kartu balik di daftar ujian: ketuk kartu untuk membuka menunya, tombol X atau Esc untuk menutup. */
(function () {
  var kartu = document.querySelectorAll('[data-kartu]');
  function balik(k, buka) {
    var depan = k.querySelector('.ujk-depan'), belakang = k.querySelector('.ujk-belakang');
    k.classList.toggle('is-balik', buka);
    depan.setAttribute('aria-expanded', buka ? 'true' : 'false');
    if (buka) { belakang.removeAttribute('inert'); depan.setAttribute('inert', ''); }
    else { belakang.setAttribute('inert', ''); depan.removeAttribute('inert'); k.querySelectorAll('details[open]').forEach(function (d) { d.open = false; }); }
    if (buka) setTimeout(function () { var f = belakang.querySelector('a, button, select'); if (f) f.focus({ preventScroll: true }); }, 350);
    else setTimeout(function () { depan.focus({ preventScroll: true }); }, 350);
  }
  kartu.forEach(function (k) {
    var depan = k.querySelector('.ujk-depan');
    depan.addEventListener('click', function (e) { if (e.target.closest('a')) return; balik(k, true); });
    depan.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); balik(k, true); } });
    k.querySelector('[data-tutup]').addEventListener('click', function () { balik(k, false); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (document.querySelector('details.uj-kkm[open]')) return;      // Esc pertama menutup popup pengaturan
    document.querySelectorAll('.ujk.is-balik').forEach(function (k) { balik(k, false); });
  }, true);
})();
