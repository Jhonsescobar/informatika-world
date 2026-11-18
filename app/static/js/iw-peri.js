// iw-peri.js
// Peri kecil di beranda siswa: melayang pelan, bisa diseret (jari atau mouse), dan menaburkan kilau saat diketuk.
// Ketuk 3x cepat: peri jongkok, lalu terbang melengkung keluar layar dengan jejak kilau, menghilang beberapa detik,
// lalu muncul lagi di tempat acak. Hanya dimuat di beranda. Tidak dipasang di halaman ujian.
// "Kurangi gerakan": tanpa animasi; tiga ketukan cepat hanya memindahkan peri ke tempat acak.
(function () {
  var kurangi = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var KUNCI = 'iw-peri-pos';
  var W = 64, H = 64;
  var peri = document.createElement('div');
  peri.className = 'peri';
  peri.setAttribute('role', 'img');
  peri.setAttribute('aria-label', 'Peri kecil. Geser untuk memindahkan, ketuk untuk kilau, ketuk tiga kali cepat agar ia terbang.');
  peri.innerHTML =
    '<svg viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">' +
    '<defs>' +
    '<linearGradient id="peri-g-sayap" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#b8fff2" stop-opacity=".85"/><stop offset="1" stop-color="#7fd6ff" stop-opacity=".35"/></linearGradient>' +
    '<linearGradient id="peri-g-gaun" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe3a0"/><stop offset="1" stop-color="#ff9fc4"/></linearGradient>' +
    '<radialGradient id="peri-g-aura"><stop offset="0" stop-color="#fff2b8" stop-opacity=".55"/><stop offset="1" stop-color="#fff2b8" stop-opacity="0"/></radialGradient>' +
    '</defs>' +
    '<circle cx="32" cy="34" r="28" fill="url(#peri-g-aura)"/>' +
    '<g class="peri-sayap">' +
    '<path class="sy" d="M30 30C18 14 4 16 6 27c2 9 14 8 24 3z"/>' +
    '<path class="sy" d="M34 30C46 14 60 16 58 27c-2 9-14 8-24 3z"/>' +
    '<path class="sy" d="M30.5 33C20 36 12 44 17 48c5 3 11-6 13.5-15z"/>' +
    '<path class="sy" d="M33.5 33C44 36 52 44 47 48c-5 3-11-6-13.5-15z"/>' +
    '<path class="urat" d="M30 30C21 23 13 21 9 24M30 31C22 31 15 29 11 27M34 30C43 23 51 21 55 24M34 31C42 31 49 29 53 27"/>' +
    '</g>' +
    '<path class="rambut" d="M25 20c-1-8 5-12 8-12 5 0 9 4 7 12-1-4-4-6-8-6s-6 2-7 6z"/>' +
    '<circle class="kepala" cx="32" cy="22" r="6.2"/>' +
    '<path class="poni" d="M25.8 21c1-4 4-6 7-6 3 0 5.3 2 5.8 5.5-2-2.2-4.6-3-7-2.6-2.4.3-4.5 1.4-5.8 3.1z"/>' +
    '<circle class="mata" cx="29.6" cy="22.6" r=".9"/><circle class="mata" cx="34.4" cy="22.6" r=".9"/>' +
    '<circle class="pipi" cx="27.6" cy="24.6" r="1.3"/><circle class="pipi" cx="36.4" cy="24.6" r="1.3"/>' +
    '<path class="senyum" d="M30.6 25.2q1.4 1.3 2.8 0"/>' +
    '<path class="gaun" d="M28 28.5h8l4 13h-16z"/>' +
    '<path class="renda" d="M24 41.5q2 1.8 4 0t4 0 4 0 4 0"/>' +
    '<path class="lengan" d="M28.4 30.5l-4 4M35.6 30.5l5 -3.5"/>' +
    '<path class="kaki" d="M29.5 41.5l-1 5M34.5 41.5l1 5"/>' +
    '<path class="tongkat" d="M40.6 27l4.4-7"/>' +
    '<path class="bintang" d="M45.4 13l1.2 2.7 2.7 1.2-2.7 1.2-1.2 2.7-1.2-2.7-2.7-1.2 2.7-1.2z"/>' +
    '</svg>';
  document.body.appendChild(peri);
  var gambar = peri.firstChild;

  function batas(x, y) {
    return [Math.max(4, Math.min(window.innerWidth - W - 4, x)), Math.max(4, Math.min(window.innerHeight - H - 4, y))];
  }
  function taruh(x, y) { var p = batas(x, y); peri.style.left = p[0] + 'px'; peri.style.top = p[1] + 'px'; return p; }
  function simpan() {
    try { sessionStorage.setItem(KUNCI, JSON.stringify([peri.offsetLeft / window.innerWidth, peri.offsetTop / window.innerHeight])); } catch (e) {}
  }
  var awal = null;
  try { awal = JSON.parse(sessionStorage.getItem(KUNCI)); } catch (e) {}
  if (awal) taruh(awal[0] * window.innerWidth, awal[1] * window.innerHeight);
  else taruh(window.innerWidth - 110, window.innerHeight * 0.28);
  window.addEventListener('resize', function () { if (!sibuk) taruh(peri.offsetLeft, peri.offsetTop); });

  function acak(a, b) { return a + Math.random() * (b - a); }

  function kilau(pusatX, pusatY, jumlah, jarakMin, jarakMaks, kelas) {
    if (kurangi) return;
    for (var i = 0; i < jumlah; i++) {
      var k = document.createElement('span');
      k.className = 'peri-kilau' + (kelas ? ' ' + kelas : '');
      var sudut = (Math.PI * 2 * i) / jumlah + Math.random() * 0.4, jarak = acak(jarakMin, jarakMaks);
      k.style.left = pusatX + 'px';
      k.style.top = pusatY + 'px';
      k.style.setProperty('--dx', Math.cos(sudut) * jarak + 'px');
      k.style.setProperty('--dy', Math.sin(sudut) * jarak + 'px');
      document.body.appendChild(k);
      setTimeout(function (el) { el.remove(); }.bind(null, k), 900);
    }
  }
  function kilauDiPeri(jumlah, jarakMin, jarakMaks) {
    var r = peri.getBoundingClientRect();
    kilau(r.left + W / 2, r.top + H / 2, jumlah, jarakMin, jarakMaks);
  }

  // ---- ketukan: 1 = kilau, 2 = loncat semangat, 3 cepat = terbang
  var ketukan = [], sibuk = false, loncatTimer = null;
  function loncat() {
    if (kurangi) return;
    peri.classList.remove('peri-loncat');
    void peri.offsetWidth;
    peri.classList.add('peri-loncat');
    clearTimeout(loncatTimer);
    loncatTimer = setTimeout(function () { peri.classList.remove('peri-loncat'); }, 420);
  }

  function titikBezier(p0, p1, p2, p3, t) {
    var u = 1 - t;
    return {
      x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
      y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y
    };
  }

  function terbang() {
    sibuk = true;
    peri.classList.add('is-busy');
    if (kurangi) { setTimeout(munculAcak, 0); return; }
    var x0 = peri.offsetLeft, y0 = peri.offsetTop;
    var lebar = window.innerWidth, tinggi = window.innerHeight;
    // 1) jongkok sebentar (ancang-ancang), 2) meluncur melengkung ke luar layar
    peri.classList.add('peri-ancang');
    setTimeout(function () {
      peri.classList.remove('peri-ancang');
      peri.classList.add('is-flying');
      var sisi = Math.floor(Math.random() * 3);                  // 0 atas, 1 kiri, 2 kanan
      var target = sisi === 0 ? { x: acak(0, lebar), y: -140 } : sisi === 1 ? { x: -140, y: acak(0, tinggi * 0.7) } : { x: lebar + 140, y: acak(0, tinggi * 0.7) };
      var p0 = { x: x0, y: y0 }, p3 = target;
      var dx = p3.x - p0.x, dy = p3.y - p0.y, panjang = Math.sqrt(dx * dx + dy * dy) || 1;
      var nx = -dy / panjang, ny = dx / panjang;                  // arah tegak lurus untuk lengkungan
      var arah = Math.random() < 0.5 ? -1 : 1, lengkung = acak(90, 170) * arah;
      var p1 = { x: p0.x + dx * 0.2 + nx * lengkung, y: p0.y + dy * 0.2 + ny * lengkung - 70 };
      var p2 = { x: p0.x + dx * 0.65 - nx * lengkung * 0.7, y: p0.y + dy * 0.65 - ny * lengkung * 0.7 };
      var durasi = 1700, mulai = null, jejak = 0, terakhir = { x: x0, y: y0 };
      function langkah(ts) {
        if (mulai === null) mulai = ts;
        var t = Math.min(1, (ts - mulai) / durasi);
        var e = t * t * (0.55 + 0.45 * t);                        // pelan di awal, makin cepat
        var tit = titikBezier(p0, p1, p2, p3, e);
        var goyang = Math.sin(t * Math.PI * 6) * 12 * (1 - t);    // goyangan halus seperti serangga
        var px = tit.x + nx * goyang, py = tit.y + ny * goyang;
        peri.style.left = px + 'px';
        peri.style.top = py + 'px';
        var vx = px - terakhir.x, vy = py - terakhir.y;
        var kecepatan = Math.sqrt(vx * vx + vy * vy) || 1;
        var miring = Math.max(-28, Math.min(28, (vx / kecepatan) * 28));
        var skala = 1 - 0.4 * t;
        gambar.style.transform = 'rotate(' + miring.toFixed(1) + 'deg) scale(' + skala.toFixed(3) + ')';
        peri.style.opacity = t > 0.85 ? String(Math.max(0, (1 - t) / 0.15)) : '1';
        if (ts - jejak > 34) {                                    // jejak kilau di belakang peri
          jejak = ts;
          kilau(px + W / 2, py + H / 2, 2, 6, 22, 'peri-jejak');
        }
        terakhir = { x: px, y: py };
        if (t < 1) requestAnimationFrame(langkah);
        else selesaiTerbang();
      }
      requestAnimationFrame(langkah);
    }, 230);
  }

  function selesaiTerbang() {
    peri.classList.remove('is-flying');
    peri.classList.add('is-hidden');
    gambar.style.transform = '';
    setTimeout(munculAcak, acak(1300, 3200));
  }

  function munculAcak() {
    var m = 12, atas = 96, bawah = 150;                            // hindari kepala halaman dan dok menu
    var x = acak(m, Math.max(m + 1, window.innerWidth - W - m));
    var y = acak(atas, Math.max(atas + 1, window.innerHeight - H - bawah));
    taruh(x, y);
    peri.style.opacity = '';
    peri.classList.remove('is-hidden', 'is-flying', 'peri-ancang');
    gambar.style.transform = '';
    if (!kurangi) {
      peri.classList.add('peri-muncul');
      kilauDiPeri(12, 30, 62);
      setTimeout(function () { peri.classList.remove('peri-muncul'); peri.classList.remove('is-busy'); sibuk = false; simpan(); }, 800);
    } else {
      peri.classList.remove('is-busy'); sibuk = false; simpan();
    }
  }

  // ---- seret
  var seret = null, geser = 0;
  peri.addEventListener('pointerdown', function (e) {
    if (sibuk) return;
    seret = { dx: e.clientX - peri.offsetLeft, dy: e.clientY - peri.offsetTop, x: e.clientX, y: e.clientY };
    geser = 0;
    peri.classList.add('is-dragged');
    peri.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  peri.addEventListener('pointermove', function (e) {
    if (!seret) return;
    geser = Math.max(geser, Math.abs(e.clientX - seret.x) + Math.abs(e.clientY - seret.y));   // jarak geser dari titik sentuh awal
    taruh(e.clientX - seret.dx, e.clientY - seret.dy);
  });
  function lepas() {
    if (!seret) return;
    seret = null;
    peri.classList.remove('is-dragged');
    simpan();
    if (geser > 8) { ketukan = []; return; }                         // digeser lebih dari 8 piksel: bukan ketukan
    var kini = Date.now();
    ketukan = ketukan.filter(function (t) { return kini - t < 1100; });
    ketukan.push(kini);
    if (ketukan.length >= 3) { ketukan = []; terbang(); return; }
    kilauDiPeri(9, 34, 60);
    if (ketukan.length === 2) loncat();
  }
  peri.addEventListener('pointerup', lepas);
  peri.addEventListener('pointercancel', lepas);
})();
