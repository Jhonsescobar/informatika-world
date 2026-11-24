/* Interaksi ringan: sorot mengikuti kursor pada panel kaca dan angka besar yang naik pelan.
   Dimatikan bila pengguna memilih gerak minimal. Tidak dipakai di layar ujian. */
(function () {
  var diam = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (diam) return;
  var sentuh = window.matchMedia && window.matchMedia("(hover: none)").matches;
  if (!sentuh) {
    document.addEventListener("pointermove", function (e) {
      var p = e.target.closest && e.target.closest(".shell .panel, .s-main .panel");
      if (!p) return;
      var r = p.getBoundingClientRect();
      p.style.setProperty("--mx", (e.clientX - r.left) + "px");
      p.style.setProperty("--my", (e.clientY - r.top) + "px");
    }, { passive: true });
  }
  document.querySelectorAll(".stat-value").forEach(function (el) {
    if (el.children.length || el.id) return;          // yang berisi satuan atau diperbarui langsung dibiarkan
    var t = el.textContent.trim();
    if (!/^\d+([.,]\d+)?$/.test(t)) return;
    var koma = t.indexOf(",") >= 0, desimal = (t.split(/[.,]/)[1] || "").length;
    var akhir = parseFloat(t.replace(",", "."));
    if (!isFinite(akhir) || akhir === 0) return;
    var mulai = performance.now(), lama = 700;
    function langkah(now) {
      var k = Math.min(1, (now - mulai) / lama), e = 1 - Math.pow(1 - k, 3);
      var v = (akhir * e).toFixed(desimal);
      el.textContent = koma ? v.replace(".", ",") : v;
      if (k < 1) requestAnimationFrame(langkah); else el.textContent = t;
    }
    requestAnimationFrame(langkah);
  });
})();
