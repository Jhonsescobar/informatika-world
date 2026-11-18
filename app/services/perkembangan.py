# app/services/perkembangan.py
# Riwayat nilai ujian satu siswa (untuk grafik naik/turun) dan perhitungan bentuk grafiknya.
# Nilai ujian = persen tertinggi siswa, sama seperti rekap; urutan = waktu pertama kali selesai mengerjakan.

from statistics import mean
from sqlalchemy.orm import Session

from app.models.exam import ExamSession
from app.models.grade import ScoreComponent
from app.services.rekap import (kkm_akhir, kkm_ujian, persen_terbaik, siswa_kelas, tahun_aktif, tingkat_siswa,
                                ujian_dihitung)

AMBANG_TETAP = 2.0      # selisih sekecil ini (poin persen) dianggap "tetap"


def _waktu_selesai(db: Session, student_id: int, exam_ids: list[int]) -> dict:
    """{exam_id: waktu pertama kali siswa selesai mengerjakan}"""
    waktu = {}
    for s in (db.query(ExamSession).filter(ExamSession.student_id == student_id, ExamSession.exam_id.in_(exam_ids),
                                           ExamSession.status != "active").order_by(ExamSession.id)):
        waktu.setdefault(s.exam_id, s.submitted_at or s.started_at)
    return waktu


def arah(selisih: float | None) -> str:
    if selisih is None:
        return "baru"
    if selisih > AMBANG_TETAP:
        return "naik"
    if selisih < -AMBANG_TETAP:
        return "turun"
    return "tetap"


def riwayat_siswa(db: Session, student_id: int, bandingkan_rombel: bool = False) -> dict:
    """Titik grafik per ujian yang SUDAH dikerjakan siswa (urut waktu) + ringkasan tren.
    bandingkan_rombel: tambahkan rata-rata teman satu rombel di tiap ujian (untuk tampilan guru)."""
    tahun = tahun_aktif(db)
    kelas = tingkat_siswa(db, student_id)
    kosong = {"kelas": kelas, "titik": [], "tren": "baru", "selisih": None, "rata": None, "terbaik": None,
              "tuntas": 0, "belum": 0}
    if not kelas:
        return kosong
    ujian = ujian_dihitung(db, kelas, tahun)
    if not ujian:
        return kosong
    ids = [e.id for e in ujian]
    nilai = persen_terbaik(db, ids, [student_id])
    waktu = _waktu_selesai(db, student_id, ids)
    komp = {k.id: k for k in db.query(ScoreComponent).filter(ScoreComponent.class_target == kelas)}
    kkm_tahun = kkm_akhir(tahun)

    rata_rombel = {}
    if bandingkan_rombel:
        murid = siswa_kelas(db, kelas, tahun)
        rombel_saya = next((rid for s, _, rid in murid if s.id == student_id), None)
        teman = [s.id for s, _, rid in murid if rid == rombel_saya] if rombel_saya else []
        semua = persen_terbaik(db, ids, teman)
        for e in ujian:
            v = [semua[(sid, e.id)] for sid in teman if (sid, e.id) in semua]
            rata_rombel[e.id] = round(mean(v), 1) if v else None

    titik = []
    for e in ujian:
        v = nilai.get((student_id, e.id))
        if v is None:
            continue
        kkm = kkm_ujian(e, komp, kkm_tahun)
        titik.append({"exam_id": e.id, "judul": e.title, "nilai": round(v, 1), "kkm": kkm, "tuntas": v >= kkm,
                      "waktu": waktu.get(e.id), "rombel": rata_rombel.get(e.id)})
    titik.sort(key=lambda t: (t["waktu"] is None, t["waktu"], t["exam_id"]))
    prev = None
    for t in titik:
        t["selisih"] = round(t["nilai"] - prev, 1) if prev is not None else None
        t["arah"] = arah(t["selisih"])
        prev = t["nilai"]
    ringkas = dict(kosong, titik=titik, belum=len(ujian) - len(titik))
    if titik:
        ringkas.update(tren=titik[-1]["arah"], selisih=titik[-1]["selisih"],
                       rata=round(mean(t["nilai"] for t in titik), 1), terbaik=max(t["nilai"] for t in titik),
                       tuntas=sum(1 for t in titik if t["tuntas"]))
    return ringkas


# ---------- bentuk grafik (dipakai template SVG) ----------

def _kurva(pts: list[tuple[float, float]], atas: float, bawah: float) -> str:
    """Jalur SVG halus (Catmull-Rom jadi Bezier); tinggi dijepit supaya kurva tidak melewati bingkai."""
    if len(pts) == 1:
        return ""
    jepit = lambda y: max(atas, min(bawah, y))
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, jepit(p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, jepit(p2[1] - (p3[1] - p1[1]) / 6))
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def bentuk_grafik(titik: list[dict], lebar: int = 420, tinggi: int = 240) -> dict:
    """Koordinat siap gambar. Sumbu nilai 0-100; sumbu waktu dibagi rata per ujian."""
    kiri, kanan, atas, bawah = 38, 18, 18, tinggi - 34
    isi_l, isi_t = lebar - kiri - kanan, bawah - atas
    y = lambda v: round(atas + (100 - v) / 100 * isi_t, 1)
    n = len(titik)
    xs = [kiri + (isi_l / 2 if n == 1 else isi_l * i / (n - 1)) for i in range(n)]
    pts = [(x, y(t["nilai"])) for x, t in zip(xs, titik)]
    garis = _kurva(pts, atas, bawah)
    area = f"{garis} L{pts[-1][0]:.1f},{bawah} L{pts[0][0]:.1f},{bawah} Z" if garis else ""
    pembanding = [(x, y(t["rombel"])) for x, t in zip(xs, titik) if t.get("rombel") is not None]
    return {"lebar": lebar, "tinggi": tinggi, "kiri": kiri, "kanan": lebar - kanan, "bawah": bawah, "atas": atas,
            "garis": garis, "area": area, "kkm_y": y(titik[-1]["kkm"]) if titik else None,
            "sumbu": [{"nilai": v, "y": y(v)} for v in (0, 25, 50, 75, 100)],
            "titik": [dict(t, x=round(x, 1), y=yy, no=i + 1) for i, (t, (x, yy)) in enumerate(zip(titik, pts))],
            "pembanding": " ".join(f"{x:.1f},{yy:.1f}" for x, yy in pembanding) if len(pembanding) > 1 else ""}


def pesan_semangat(tren: str, selisih, tuntas_terakhir: bool) -> tuple[str, str]:
    """(judul, kalimat) untuk kartu tren siswa. Nadanya menyemangati, bukan menghakimi."""
    if tren == "naik":
        return f"Naik {abs(selisih):g} poin", "Belajarmu terasa hasilnya. Pertahankan ritmenya!"
    if tren == "turun":
        return f"Turun {abs(selisih):g} poin", "Tidak apa-apa. Baca materinya lagi, lalu coba kejar di ujian berikutnya."
    if tren == "tetap":
        return "Stabil", "Nilaimu konsisten. Satu langkah kecil lagi untuk naik."
    return ("Awal yang baik" if tuntas_terakhir else "Ayo mulai"), "Kerjakan ujian berikutnya untuk melihat perkembanganmu di sini."
