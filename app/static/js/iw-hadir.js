// Sinyal "masih di sini" untuk pantau guru. Dikirim saat tab terbuka dan aktif, lalu tiap 60 detik.
(function () {
  var JEDA = 60000;
  function kirim() {
    if (document.visibilityState !== "visible") return;
    fetch("/student/ping", { method: "POST", credentials: "same-origin", keepalive: true }).catch(function () {});
  }
  kirim();
  setInterval(kirim, JEDA);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") kirim();
  });
})();
