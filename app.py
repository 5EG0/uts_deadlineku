import os
from datetime import date, datetime

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request
from flask_sqlalchemy import SQLAlchemy

# Muat variabel dari file .env
load_dotenv()

app = Flask(__name__, instance_path ='/tmp')

# ===== DATABASE =====
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url and database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

db = SQLAlchemy(app, engine_options={
    'connect_args': {
        'check_same_thread': False
    },
    "pool_pre_ping": True,
    "pool_recycle": 300,   # opsional: recycle koneksi setiap 5 menit
    "pool_size": 5,        # opsional: batasi jumlah koneksi
    "max_overflow": 10     # opsional: koneksi tambahan saat sibuk
})

# ===== KONSTANTA =====
JENIS_TUGAS = ["Tugas", "Kuis", "Laporan", "UAS", "UTS", "Proyek"]
STATUS_LIST = ["Belum", "Proses", "Selesai"]
HARI_LIST = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
JENIS_KEGIATAN = ["Kuliah", "Organisasi", "Belajar", "Pribadi", "Lainnya"]

ICON_KEGIATAN = {
    "Kuliah": "🎓", "Organisasi": "🤝", "Belajar": "📖",
    "Pribadi": "🙋", "Lainnya": "📌"
}

# Emoji per jenis tugas
ICON_JENIS = {
    "Tugas": "📝", "Kuis": "❓", "Laporan": "📄",
    "UAS": "🎓", "UTS": "📖", "Proyek": "💼"
}

# Warna prioritas
WARNA_PRIORITAS = {
    "merah": "#ef4444", "kuning": "#f59e0b",
    "biru": "#3b82f6", "hijau": "#10b981"
}

# Bobot otomatis berdasarkan kepentingan (dipakai kalau bobot tidak diisi)
BOBOT_KEPENTINGAN = {
    "Penting": 30,
    "Sedang": 15,
    "Santai": 5
}

ICON_KEPENTINGAN = {
    "Penting": "🔴",
    "Sedang": "🟠",
    "Santai": "🟢"
}

# ===== MODEL =====
class Tugas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(150), nullable=False)
    mata_kuliah = db.Column(db.String(100), nullable=False)
    jenis = db.Column(db.String(20), nullable=False)
    kepentingan = db.Column(db.String(20), default="Sedang")   
    bobot = db.Column(db.Integer, nullable=True)
    deadline = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="Belum")
    catatan = db.Column(db.String(300), default="")
    reminder_days = db.Column(db.Integer, default=3)
    tanggal_dibuat = db.Column(db.DateTime, default=datetime.now)

class Kegiatan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(150), nullable=False)
    jenis = db.Column(db.String(30), nullable=False)
    hari = db.Column(db.String(20), nullable=False)
    jam_mulai = db.Column(db.String(10), nullable=False)     # "08:00"
    jam_selesai = db.Column(db.String(10), nullable=False)   # "10:30"
    lokasi = db.Column(db.String(150), default="")
    catatan = db.Column(db.String(300), default="")
    reminder = db.Column(db.Boolean, default=True)            # reminder hari H
    tanggal_dibuat = db.Column(db.DateTime, default=datetime.now)


# ===== FUNCTION =====
def selisih_hari(deadline):
    """OPERATOR: hitung selisih hari dari hari ini (pakai waktu lokal)"""
    return (deadline - date.today()).days

def get_bobot_efektif(tugas):
    """FUNCTION: ambil bobot efektif — kalau bobot kosong, pakai bobot dari kepentingan"""
    if tugas.bobot is not None and tugas.bobot > 0:
        return tugas.bobot
    return BOBOT_KEPENTINGAN.get(tugas.kepentingan, 15)

def hitung_skor_prioritas(tugas):
    """OPERATOR + IF ELSE: rumus prioritas = bobot_efektif / sisa hari"""
    sisa = selisih_hari(tugas.deadline)
    bobot_efektif = get_bobot_efektif(tugas)

    if sisa < 0:
        return 999
    elif sisa == 0:
        return bobot_efektif * 2
    else:
        return round(bobot_efektif / sisa, 2)


def kategori_prioritas(skor, deadline):
    """IF ELSE bertingkat: klasifikasi urgensi"""
    sisa = selisih_hari(deadline)
    if sisa < 0:
        return {"label": "TELAT", "warna": "merah", "emoji": "⚠️", "hex": "#dc2626"}
    elif sisa == 0:
        return {"label": "HARI INI", "warna": "merah", "emoji": "🔥", "hex": "#ef4444"}
    elif skor >= 15:
        return {"label": "KRITIS", "warna": "merah", "emoji": "🔴", "hex": "#ef4444"}
    elif skor >= 8:
        return {"label": "TINGGI", "warna": "kuning", "emoji": "🟠", "hex": "#f59e0b"}
    elif skor >= 3:
        return {"label": "SEDANG", "warna": "biru", "emoji": "🔵", "hex": "#3b82f6"}
    else:
        return {"label": "RENDAH", "warna": "hijau", "emoji": "🟢", "hex": "#10b981"}


def teks_countdown(deadline):
    """IF ELSE: teks countdown human-readable"""
    sisa = selisih_hari(deadline)
    if sisa < 0:
        return f"Telat {abs(sisa)} hari"
    elif sisa == 0:
        return "Hari ini!"
    elif sisa == 1:
        return "Besok"
    elif sisa <= 30:
        return f"{sisa} hari lagi"
    else:
        return f"{sisa} hari lagi"


def hitung_statistik(daftar_tugas):
    """LOOPING + IF + OPERATOR: ringkasan"""
    total = len(daftar_tugas)
    belum = proses = selesai = telat = kritis = 0

    for t in daftar_tugas:
        if t.status == "Selesai":
            selesai += 1
        elif t.status == "Proses":
            proses += 1
        else:
            belum += 1

        if t.status != "Selesai" and selisih_hari(t.deadline) < 0:
            telat += 1

        skor = hitung_skor_prioritas(t)
        if t.status != "Selesai" and skor >= 15:
            kritis += 1

    persen = round((selesai / total * 100), 1) if total > 0 else 0

    return {
        "total": total, "belum": belum, "proses": proses,
        "selesai": selesai, "telat": telat, "kritis": kritis,
        "persen": persen
    }


def urutkan_by_prioritas(daftar):
    """LOOPING NESTED - bubble sort manual"""
    hasil = daftar.copy()
    n = len(hasil)
    for i in range(n):
        for j in range(n - i - 1):
            skor_j = hitung_skor_prioritas(hasil[j])
            skor_j1 = hitung_skor_prioritas(hasil[j + 1])
            if skor_j < skor_j1:
                hasil[j], hasil[j + 1] = hasil[j + 1], hasil[j]
    return hasil


def rekap_per_matkul(daftar):
    """LOOPING NESTED + LIST: rekap per mata kuliah"""
    matkul_unik = []
    for t in daftar:
        if t.mata_kuliah not in matkul_unik:
            matkul_unik.append(t.mata_kuliah)

    rekap = []
    for mk in matkul_unik:
        jumlah = total_bobot = selesai = 0
        for t in daftar:
            if t.mata_kuliah == mk:
                jumlah += 1
                total_bobot += get_bobot_efektif(t)
                if t.status == "Selesai":
                    selesai += 1
        rekap.append({
            "matkul": mk, "jumlah": jumlah,
            "bobot": total_bobot, "selesai": selesai,
            "persen": round(selesai / jumlah * 100) if jumlah > 0 else 0
        })

    # bubble sort by bobot
    n = len(rekap)
    for i in range(n):
        for j in range(n - i - 1):
            if rekap[j]["bobot"] < rekap[j + 1]["bobot"]:
                rekap[j], rekap[j + 1] = rekap[j + 1], rekap[j]
    return rekap


def distribusi_prioritas(daftar):
    """LOOPING + IF: hitung jumlah tugas per kategori prioritas"""
    hitung = {"KRITIS": 0, "TINGGI": 0, "SEDANG": 0, "RENDAH": 0, "TELAT": 0}

    for t in daftar:
        if t.status == "Selesai":
            continue
        skor = hitung_skor_prioritas(t)
        kategori = kategori_prioritas(skor, t.deadline)

        if kategori["label"] == "TELAT" or kategori["label"] == "HARI INI":
            hitung["TELAT"] += 1
        else:
            hitung[kategori["label"]] += 1

    return hitung


def cari_deadline_terdekat(daftar):
    terdekat = None
    for t in daftar:
        if t.status == "Selesai":
            continue
        if terdekat is None or t.deadline < terdekat.deadline:
            terdekat = t
    return terdekat

# ===== FUNCTION: JADWAL KEGIATAN =====
def hitung_durasi_jam(jam_mulai, jam_selesai):
    """OPERATOR: hitung durasi kegiatan dalam jam"""
    try:
        h1, m1 = map(int, jam_mulai.split(":"))
        h2, m2 = map(int, jam_selesai.split(":"))
        total = (h2 * 60 + m2) - (h1 * 60 + m1)
        jam = total // 60
        menit = total % 60
        if jam == 0:
            return f"{menit} menit"
        elif menit == 0:
            return f"{jam} jam"
        return f"{jam} jam {menit} menit"
    except (TypeError, ValueError):
        return "-"


def cek_bentrok_jadwal(kegiatan_baru, semua_kegiatan, exclude_id=None):
    """IF ELSE + LOOPING: cek apakah jadwal bentrok dengan yang lain"""
    bentrok_list = []
    for k in semua_kegiatan:
        if exclude_id and k.id == exclude_id:
            continue
        if k.hari != kegiatan_baru["hari"]:
            continue

        # cek irisan jam
        mulai_baru = kegiatan_baru["jam_mulai"]
        selesai_baru = kegiatan_baru["jam_selesai"]

        if mulai_baru < k.jam_selesai and selesai_baru > k.jam_mulai:
            bentrok_list.append(k)

    return bentrok_list


def jadwal_hari_ini():
    """FUNCTION: nama hari ini dalam bahasa Indonesia"""
    nama_eng = date.today().strftime("%A")
    map_hari = {
        "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
        "Thursday": "Kamis", "Friday": "Jumat",
        "Saturday": "Sabtu", "Sunday": "Minggu"
    }
    return map_hari.get(nama_eng, "Senin")


def kegiatan_hari_ini(daftar):
    """LOOPING + IF: filter kegiatan yang hari ini"""
    hari = jadwal_hari_ini()
    hasil = []
    for k in daftar:
        if k.hari == hari:
            hasil.append(k)
    return sorted(hasil, key=lambda x: x.jam_mulai)


def rekap_per_hari(daftar):
    """LOOPING NESTED + LIST: jumlah kegiatan per hari"""
    rekap = []
    for hari in HARI_LIST:
        jumlah = 0
        for k in daftar:
            if k.hari == hari:
                jumlah += 1
        rekap.append({"hari": hari, "jumlah": jumlah})
    return rekap


# ===== FUNCTION: PENGINGAT =====
def ambil_pengingat_aktif(semua_tugas, semua_kegiatan):
    """
    LOOPING + IF: kumpulkan semua pengingat yang relevan
    - Tugas dengan deadline dalam X hari (sesuai reminder_days)
    - Kegiatan hari ini (jika reminder=True)
    """
    daftar_pengingat = []

    # 1. Tugas yang mendekati deadline
    for t in semua_tugas:
        if t.status == "Selesai":
            continue

        sisa = selisih_hari(t.deadline)
        reminder = t.reminder_days if t.reminder_days else 3

        # Info bobot: tampilkan bobot kalau ada, kalau tidak tampilkan kepentingan
        if t.bobot:
            info_bobot = f"Bobot {t.bobot}%"
        else:
            info_bobot = t.kepentingan or "Sedang"

        if sisa < 0:
            daftar_pengingat.append({
                "tipe": "tugas", "objek": t,
                "urgensi": "merah", "emoji": "🚨",
                "pesan": f"TELAT {abs(sisa)} hari!",
                "info": f"{t.mata_kuliah} • {info_bobot}"
            })
        elif sisa == 0:
            daftar_pengingat.append({
                "tipe": "tugas", "objek": t,
                "urgensi": "merah", "emoji": "🔥",
                "pesan": "Deadline HARI INI!",
                "info": f"{t.mata_kuliah} • {info_bobot}"
            })
        elif sisa <= reminder:
            daftar_pengingat.append({
                "tipe": "tugas", "objek": t,
                "urgensi": "kuning", "emoji": "⏰",
                "pesan": f"{sisa} hari lagi",
                "info": f"{t.mata_kuliah} • {info_bobot}"
            })

    # 2. Kegiatan hari ini
    hari = jadwal_hari_ini()
    for k in semua_kegiatan:
        if k.reminder and k.hari == hari:
            daftar_pengingat.append({
                "tipe": "kegiatan", "objek": k,
                "urgensi": "biru", "emoji": ICON_KEGIATAN.get(k.jenis, "📌"),
                "pesan": f"{k.jam_mulai} - {k.jam_selesai}",
                "info": f"{k.jenis} • {k.lokasi if k.lokasi else 'Tidak ada lokasi'}"
            })

    # urutkan: merah → kuning → biru (bubble sort manual)
    urutan = {"merah": 0, "kuning": 1, "biru": 2}
    n = len(daftar_pengingat)
    for i in range(n):
        for j in range(n - i - 1):
            if urutan[daftar_pengingat[j]["urgensi"]] > urutan[daftar_pengingat[j + 1]["urgensi"]]:
                daftar_pengingat[j], daftar_pengingat[j + 1] = daftar_pengingat[j + 1], daftar_pengingat[j]

    return daftar_pengingat

# Register filters
app.jinja_env.filters['icon_jenis'] = lambda j: ICON_JENIS.get(j, "📝")


# ===== ROUTE =====
@app.route("/")
def dashboard():
    semua = Tugas.query.all()
    semua_kegiatan = Kegiatan.query.all()
    stat = hitung_statistik(semua)
    rekap = rekap_per_matkul(semua)
    terdekat = cari_deadline_terdekat(semua)
    distribusi = distribusi_prioritas(semua)

    # 5 tugas paling urgent
    tugas_aktif = [t for t in semua if t.status != "Selesai"]
    tugas_aktif = urutkan_by_prioritas(tugas_aktif)

    daftar_urgent = []
    for t in tugas_aktif[:5]:
        skor = hitung_skor_prioritas(t)
        daftar_urgent.append({
            "tugas": t, "skor": skor,
            "kategori": kategori_prioritas(skor, t.deadline),
            "countdown": teks_countdown(t.deadline)
        })

    # Data chart distribusi
    chart_labels = list(distribusi.keys())
    chart_data = list(distribusi.values())
    chart_colors = ["#ef4444", "#f59e0b", "#3b82f6", "#10b981", "#dc2626"]

    pengingat = ambil_pengingat_aktif(semua, semua_kegiatan)
    kegiatan_today = kegiatan_hari_ini(semua_kegiatan)

    return render_template("dashboard.html",
                           stat=stat, rekap=rekap,
                           terdekat=terdekat,
                           countdown_terdekat=teks_countdown(terdekat.deadline) if terdekat else None,
                           daftar_urgent=daftar_urgent,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           chart_colors=chart_colors,
                           pengingat=pengingat,
                           kegiatan_today=kegiatan_today,
                           hari_ini=jadwal_hari_ini())


@app.route("/tugas")
def tugas():
    filter_status = request.args.get("status", "semua")
    filter_matkul = request.args.get("matkul", "semua")
    urut = request.args.get("urut", "prioritas")

    semua = Tugas.query.all()

    hasil = []
    for t in semua:
        if filter_status != "semua" and t.status != filter_status:
            continue
        if filter_matkul != "semua" and t.mata_kuliah != filter_matkul:
            continue
        hasil.append(t)

    if urut == "prioritas":
        hasil = urutkan_by_prioritas(hasil)
    elif urut == "deadline":
        hasil = sorted(hasil, key=lambda t: t.deadline)
    elif urut == "bobot":
        hasil = sorted(hasil, key=lambda t: get_bobot_efektif(t), reverse=True)

    daftar = []
    for t in hasil:
        skor = hitung_skor_prioritas(t)
        daftar.append({
            "tugas": t, "skor": skor,
            "kategori": kategori_prioritas(skor, t.deadline),
            "countdown": teks_countdown(t.deadline)
        })

    stat = hitung_statistik(semua)

    matkul_unik = []
    for t in semua:
        if t.mata_kuliah not in matkul_unik:
            matkul_unik.append(t.mata_kuliah)

    return render_template("tugas.html",
                           daftar=daftar, stat=stat,
                           filter_status=filter_status,
                           filter_matkul=filter_matkul,
                           urut=urut,
                           matkul_unik=matkul_unik,
                           jenis_list=JENIS_TUGAS,
                           status_list=STATUS_LIST)


@app.route("/tambah", methods=["POST"])
def tambah():
    deadline = date.fromisoformat(request.form["deadline"])

    # Bobot opsional
    bobot_str = request.form.get("bobot", "").strip()
    bobot = int(bobot_str) if bobot_str else None

    db.session.add(Tugas(
        nama=request.form["nama"],
        mata_kuliah=request.form["mata_kuliah"],
        jenis=request.form["jenis"],
        kepentingan=request.form.get("kepentingan", "Sedang"),
        bobot=bobot,
        deadline=deadline,
        status=request.form.get("status", "Belum"),
        catatan=request.form.get("catatan", ""),
        reminder_days=int(request.form.get("reminder_days", 3))
    ))
    db.session.commit()
    return redirect("/tugas")


@app.route("/toggle/<int:id>")
def toggle(id):
    t = Tugas.query.get_or_404(id)
    if t.status == "Belum":
        t.status = "Proses"
    elif t.status == "Proses":
        t.status = "Selesai"
    else:
        t.status = "Belum"
    db.session.commit()
    return redirect(request.referrer or "/tugas")


@app.route("/hapus/<int:id>")
def hapus(id):
    db.session.delete(Tugas.query.get_or_404(id))
    db.session.commit()
    return redirect(request.referrer or "/tugas")


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    t = Tugas.query.get_or_404(id)

    if request.method == "POST":
        t.nama = request.form["nama"]
        t.mata_kuliah = request.form["mata_kuliah"]
        t.jenis = request.form["jenis"]
        t.kepentingan = request.form.get("kepentingan", "Sedang")

        # Bobot opsional
        bobot_str = request.form.get("bobot", "").strip()
        t.bobot = int(bobot_str) if bobot_str else None

        t.deadline = date.fromisoformat(request.form["deadline"])
        t.status = request.form["status"]
        t.catatan = request.form.get("catatan", "")
        t.reminder_days = int(request.form.get("reminder_days", 3))

        db.session.commit()
        return redirect("/tugas")

    return render_template("edit.html",
                           tugas=t,
                           jenis_list=JENIS_TUGAS,
                           status_list=STATUS_LIST)

@app.route("/riwayat")
def riwayat():
    semua = Tugas.query.order_by(Tugas.deadline.desc()).all()
    daftar = []
    for t in semua:
        skor = hitung_skor_prioritas(t)
        daftar.append({
            "tugas": t,
            "countdown": teks_countdown(t.deadline),
            "kategori": kategori_prioritas(skor, t.deadline)
        })
    return render_template("riwayat.html", daftar=daftar)

# ===== ROUTE: KEGIATAN =====
@app.route("/kegiatan")
def kegiatan():
    filter_hari = request.args.get("hari", "semua")
    filter_jenis = request.args.get("jenis", "semua")

    semua = Kegiatan.query.all()

    # filter
    hasil = []
    for k in semua:
        if filter_hari != "semua" and k.hari != filter_hari:
            continue
        if filter_jenis != "semua" and k.jenis != filter_jenis:
            continue
        hasil.append(k)

    # kelompokin per hari
    hari_urut = HARI_LIST
    hasil = sorted(hasil, key=lambda k: (hari_urut.index(k.hari), k.jam_mulai))

    daftar = []
    for k in hasil:
        daftar.append({
            "kegiatan": k,
            "durasi": hitung_durasi_jam(k.jam_mulai, k.jam_selesai)
        })

    rekap = rekap_per_hari(semua)

    return render_template("kegiatan.html",
                           daftar=daftar,
                           rekap=rekap,
                           filter_hari=filter_hari,
                           filter_jenis=filter_jenis,
                           hari_list=HARI_LIST,
                           jenis_kegiatan=JENIS_KEGIATAN)


@app.route("/kegiatan/tambah", methods=["POST"])
def tambah_kegiatan():
    # validasi bentrok
    data_baru = {
        "hari": request.form["hari"],
        "jam_mulai": request.form["jam_mulai"],
        "jam_selesai": request.form["jam_selesai"]
    }
    semua = Kegiatan.query.all()
    bentrok = cek_bentrok_jadwal(data_baru, semua)

    if bentrok:
        # bisa redirect dengan error (simple: redirect aja)
        return redirect("/kegiatan?error=bentrok")

    db.session.add(Kegiatan(
        nama=request.form["nama"],
        jenis=request.form["jenis"],
        hari=request.form["hari"],
        jam_mulai=request.form["jam_mulai"],
        jam_selesai=request.form["jam_selesai"],
        lokasi=request.form.get("lokasi", ""),
        catatan=request.form.get("catatan", ""),
        reminder=bool(request.form.get("reminder"))
    ))
    db.session.commit()
    return redirect("/kegiatan")


@app.route("/kegiatan/hapus/<int:id>")
def hapus_kegiatan(id):
    db.session.delete(Kegiatan.query.get_or_404(id))
    db.session.commit()
    return redirect("/kegiatan")


@app.route("/kegiatan/edit/<int:id>", methods=["GET", "POST"])
def edit_kegiatan(id):
    k = Kegiatan.query.get_or_404(id)
    if request.method == "POST":
        # Cek bentrok dulu (exclude_id=id agar tidak cek diri sendiri)
        data_baru = {
            "hari": request.form["hari"],
            "jam_mulai": request.form["jam_mulai"],
            "jam_selesai": request.form["jam_selesai"]
        }
        semua = Kegiatan.query.all()
        bentrok = cek_bentrok_jadwal(data_baru, semua, exclude_id=id)

        if bentrok:
            return redirect(f"/kegiatan/edit/{id}?error=bentrok")

        k.nama = request.form["nama"]
        k.jenis = request.form["jenis"]
        k.hari = request.form["hari"]
        k.jam_mulai = request.form["jam_mulai"]
        k.jam_selesai = request.form["jam_selesai"]
        k.lokasi = request.form.get("lokasi", "")
        k.catatan = request.form.get("catatan", "")
        k.reminder = bool(request.form.get("reminder"))
        db.session.commit()
        return redirect("/kegiatan")

    return render_template("edit_kegiatan.html", kegiatan=k,
                           hari_list=HARI_LIST,
                           jenis_kegiatan=JENIS_KEGIATAN)


# ===== ROUTE: PENGINGAT =====
@app.route("/pengingat")
def pengingat():
    semua_tugas = Tugas.query.all()
    semua_kegiatan = Kegiatan.query.all()
    daftar = ambil_pengingat_aktif(semua_tugas, semua_kegiatan)

    return render_template("pengingat.html",
                           daftar=daftar,
                           hari_ini=jadwal_hari_ini())


# Daftarkan filter icon kegiatan
app.jinja_env.filters['icon_kegiatan'] = lambda j: ICON_KEGIATAN.get(j, "📌")

# ===== INIT DB =====
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=False)