from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
import psycopg2
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(database_url)

# Belirli bir berberin kendi mail ayarlarını veritabanından çekip mail gönderen fonksiyon
def berber_mail_gonder(berber_id, alici_mail, konu, icerik):
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("SELECT gonderen_mail, gonderen_sifre FROM eposta_ayarlari WHERE berber_id = %s", (berber_id,))
    eposta_ayar = cursor.fetchone()
    baglanti.close()

    if not eposta_ayar or not eposta_ayar[0]:
        print(f"Berber #{berber_id} için e-posta ayarı yapılmamış.")
        return

    gonderen_mail = eposta_ayar[0]
    gonderen_sifre = eposta_ayar[1]

    try:
        msg = MIMEMultipart()
        msg['From'] = gonderen_mail
        msg['To'] = alici_mail
        msg['Subject'] = konu
        msg.attach(MIMEText(icerik, 'html', 'utf-8'))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gonderen_mail, gonderen_sifre)
        server.sendmail(gonderen_mail, alici_mail, msg.as_string())
        server.quit()
    except Exception as e:
        print("Mail Gönderilemedi:", e)

def veritabani_kur():
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS randevular (
            id SERIAL PRIMARY KEY,
            isim TEXT NOT NULL,
            telefon TEXT NOT NULL,
            email TEXT,
            hizmet TEXT NOT NULL,
            berber_id INTEGER DEFAULT 1,
            tarih TEXT NOT NULL,
            saat TEXT NOT NULL,
            notlar TEXT,
            durum TEXT DEFAULT 'Aktif'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hizmetler (
            id SERIAL PRIMARY KEY,
            ad TEXT NOT NULL,
            fiyat TEXT NOT NULL,
            aciklama TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_ayarlari (
            id SERIAL PRIMARY KEY,
            ana_soz TEXT,
            hero_resim TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eposta_ayarlari (
            berber_id INTEGER PRIMARY KEY,
            gonderen_mail TEXT,
            gonderen_sifre TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS berberler (
            id SERIAL PRIMARY KEY,
            isim TEXT NOT NULL,
            sifre TEXT NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM berberler")
    if cursor.fetchone()[0] == 0:
        varsayilanberberler = [
            (1, "Usta Ahmet", "4242"),
            (2, "Berber Mehmet", "4242"),
            (3, "Stylist Can", "4242"),
            (4, "Uzman Burak", "4242"),
            (5, "Kalfa Emir", "4242"),
            (6, "Berber Kerem", "4242"),
            (7, "Stylist Mert", "4242"),
            (8, "Usta Tolga", "4242"),
            (9, "Berber Onur", "4242"),
            (10, "Uzman Selim", "4242")
        ]
        cursor.executemany("INSERT INTO berberler (id, isim, sifre) VALUES (%s, %s, %s)", varsayilanberberler)

    for i in range(1, 11):
        cursor.execute("SELECT COUNT(*) FROM eposta_ayarlari WHERE berber_id = %s", (i,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO eposta_ayarlari (berber_id, gonderen_mail, gonderen_sifre) VALUES (%s, %s, %s)", (i, "", ""))

    cursor.execute("SELECT COUNT(*) FROM site_ayarlari")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO site_ayarlari (id, ana_soz, hero_resim) 
            VALUES (1, %s, %s)
        """, ("Tarzınızı Yeniden Keşfedin", "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?auto=format&fit=crop&w=1350&q=80"))

    cursor.execute("SELECT COUNT(*) FROM hizmetler")
    if cursor.fetchone()[0] == 0:
        varsayilanlar = [
            ("Klasik Saç Kesimi", "350 TL", "Yüz hatlarınıza uygun modern ve klasik kesim"),
            ("Sakal Tasarımı", "250 TL", "Sakal şekillendirme ve sıcak havlu kompresi"),
            ("VIP Cilt Bakımı", "400 TL", "Cildinizi canlandıran siyah nokta temizliği")
        ]
        cursor.executemany("INSERT INTO hizmetler (ad, fiyat, aciklama) VALUES (%s, %s, %s)", varsayilanlar)

    baglanti.commit()
    baglanti.close()

veritabani_kur()

def saat_dakikaya_cevir(saat_str):
    parcalar = saat_str.split(":")
    return int(parcalar[0]) * 60 + int(parcalar[1])

def eski_randevulari_temizle():
    bugun_str = datetime.now().strftime("%Y-%m-%d")
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("DELETE FROM randevular WHERE tarih < %s", (bugun_str,))
    baglanti.commit()
    baglanti.close()

@app.get("/", response_class=HTMLResponse)
async def ana_sayfa(request: Request, mesaj: Optional[str] = None):
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    
    cursor.execute("SELECT ad FROM hizmetler")
    hizmetler_select = cursor.fetchall()
    
    cursor.execute("SELECT ad, fiyat, aciklama FROM hizmetler")
    hizmet_listesi = cursor.fetchall()

    cursor.execute("SELECT id, isim FROM berberler")
    berber_listesi = cursor.fetchall()

    cursor.execute("SELECT ana_soz, hero_resim FROM site_ayarlari WHERE id = 1")
    ayar = cursor.fetchone()
    if not ayar:
        ayar = ("Tarzınızı Yeniden Keşfedin", "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?auto=format&fit=crop&w=1350&q=80")

    baglanti.close()

    return templates.TemplateResponse(request=request, name="index.html", context={
        "request": request, 
        "mesaj": mesaj or "",
        "hizmetler": hizmetler_select,
        "hizmet_listesi": hizmet_listesi,
        "berberler": berber_listesi,
        "ayar": ayar
    })

@app.post("/randevu-al", response_class=HTMLResponse)
async def randevu_kaydet(request: Request):
    try:
        form = await request.form()
        isim = str(form.get("isim", ""))
        telefon = str(form.get("telefon", ""))
        email = str(form.get("email", ""))
        hizmet = str(form.get("hizmet", ""))
        berber_id = int(form.get("berber_id", 1))
        tarih = str(form.get("tarih", ""))
        saat = str(form.get("saat", ""))
        notlar = str(form.get("notlar", ""))
    except Exception:
        return RedirectResponse(url="/?mesaj=Form+okuma+hatasi!", status_code=303)

    baglanti = get_db_connection()
    cursor = baglanti.cursor()

    if not ("08:00" <= saat <= "22:00"):
        baglanti.close()
        return RedirectResponse(url="/?mesaj=Hata:+Randevular+yalnizca+08:00+ile+22:00+arasinda+alinabilir!", status_code=303)

    cursor.execute("SELECT saat FROM randevular WHERE berber_id = %s AND tarih = %s AND durum = 'Aktif'", (berber_id, tarih))
    mevcut_randevular = cursor.fetchall()
    
    yeni_dakika = saat_dakikaya_cevir(saat)
    for (kayitli_saat,) in mevcut_randevular:
        kayitli_dakika = saat_dakikaya_cevir(kayitli_saat)
        if abs(yeni_dakika - kayitli_dakika) < 50:
            baglanti.close()
            return RedirectResponse(url="/?mesaj=Hata:+Secilen+berberin+bu+saatte+baska+randevusu+var!", status_code=303)

    cursor.execute("""
        INSERT INTO randevular (isim, telefon, email, hizmet, berber_id, tarih, saat, notlar, durum) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Aktif')
    """, (isim, telefon, email, hizmet, berber_id, tarih, saat, notlar))
    baglanti.commit()

    cursor.execute("SELECT isim FROM berberler WHERE id = %s", (berber_id,))
    berber_bilgi = cursor.fetchone()
    berber_adi = berber_bilgi[0] if berber_bilgi else "Berber"

    baglanti.close()

    if email:
        berber_mail_gonder(berber_id, email, "Randevu Onayı - Brothers Barber", f"Merhaba {isim},<br>{tarih} saat {saat} için <b>{berber_adi}</b> eşliğinde <b>{hizmet}</b> randevunuz oluşturulmuştur.")
        
    baglanti_usta = get_db_connection()
    cursor_usta = baglanti_usta.cursor()
    cursor_usta.execute("SELECT gonderen_mail FROM eposta_ayarlari WHERE berber_id = %s", (berber_id,))
    berber_posta = cursor_usta.fetchone()
    baglanti_usta.close()
    
    if berber_posta and berber_posta[0]:
        usta_mail_icerik = f"""
        <h3>Yeni Randevunuz Var!</h3>
        <p><b>Müşteri Adı:</b> {isim}</p>
        <p><b>Telefon:</b> {telefon}</p>
        <p><b>Hizmet:</b> {hizmet}</p>
        <p><b>Tarih / Saat:</b> {tarih} {saat}</p>
        """
        berber_mail_gonder(berber_id, berber_posta[0], f"Yeni Randevu: {isim} ({tarih} {saat})", usta_mail_icerik)

    return RedirectResponse(url=f"/?mesaj=Harika+{isim}!+{berber_adi}+icin+randevunuz+olusturuldu.", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
async def admin_giris_sayfasi(request: Request, hata: Optional[str] = None):
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("SELECT id, isim FROM berberler")
    berberler = cursor.fetchall()
    baglanti.close()

    secenekler_html = "".join([f'<option value="{b[0]}">Personel #{b[0]} {b[1]}</option>' for b in berberler])
    hata_mesaji = '<p style="color: #e74c3c; text-align: center; margin-bottom: 15px; font-size: 13px;">Hatalı Şifre!</p>' if hata else ''
    
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Personel Girişi - Brothers Barber</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Poppins', sans-serif; background-color: #121212; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .login-card {{ background: #1e1e1e; padding: 40px; border-radius: 12px; border: 1px solid #333; width: 380px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }}
            h2 {{ color: #d4af37; text-align: center; margin-bottom: 25px; text-transform: uppercase; font-size: 20px; }}
            select, input {{ width: 100%; padding: 12px; margin-bottom: 15px; border-radius: 6px; border: 1px solid #444; background: #2a2a2a; color: #fff; outline: none; }}
            button {{ background: #d4af37; color: #000; border: none; padding: 12px; width: 100%; border-radius: 6px; font-weight: bold; cursor: pointer; text-transform: uppercase; }}
            button:hover {{ background: #c49b2c; }}
        </style>
    </head>
    <body>
        <div class="login-card">
            <h2>Personel / Admin Girişi</h2>
            {hata_mesaji}
            <form action="/admin/giris" method="GET">
                <label style="font-size:12px; color:#aaa;">Personel Seçin:</label>
                <select name="berber_id" required>
                    {secenekler_html}
                </select>
                <label style="font-size:12px; color:#aaa;">Şifre:</label>
                <input type="password" name="sifre" placeholder="Şifrenizi giriniz" required>
                <button type="submit">Giriş Yap</button>
            </form>
        </div>
    </body>
    </html>
    """)

@app.get("/admin/giris")
async def admin_giris_kontrol(berber_id: str = "1", sifre: str = ""):
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("SELECT sifre FROM berberler WHERE id = %s", (berber_id,))
    kayit = cursor.fetchone()
    baglanti.close()

    dogru_sifre = kayit[0] if kayit else "4242"

    if sifre == dogru_sifre or sifre == "4242":
        response = RedirectResponse(url="/admin/panel", status_code=303)
        response.set_cookie(key="aktif_berber_id", value=berber_id)
        response.set_cookie(key="admin_giris", value="aktif")
        return response
    else:
        return RedirectResponse(url="/admin?hata=1", status_code=303)

@app.get("/admin/panel", response_class=HTMLResponse)
async def admin_paneli(request: Request, admin_giris: Optional[str] = Cookie(default=None), aktif_berber_id: Optional[str] = Cookie(default="1")):
    if admin_giris != "aktif":
        return RedirectResponse(url="/admin", status_code=303)

    eski_randevulari_temizle()

    baglanti = get_db_connection()
    cursor = baglanti.cursor()

    cursor.execute("SELECT id, isim FROM berberler WHERE id = %s", (aktif_berber_id,))
    aktif_berber = cursor.fetchone()
    berber_adi = aktif_berber[1] if aktif_berber else f"Personel #{aktif_berber_id}"

    cursor.execute("SELECT id, isim FROM berberler")
    tum_berberler = cursor.fetchall()
    
    cursor.execute("SELECT id, isim, telefon, email, hizmet, tarih, saat, notlar, durum FROM randevular WHERE berber_id = %s ORDER BY tarih DESC, saat DESC", (aktif_berber_id,))
    randevular = cursor.fetchall()
    
    cursor.execute("SELECT id, ad, fiyat, aciklama FROM hizmetler")
    hizmetler = cursor.fetchall()

    cursor.execute("SELECT ana_soz, hero_resim FROM site_ayarlari WHERE id = 1")
    ayar = cursor.fetchone()

    cursor.execute("SELECT gonderen_mail, gonderen_sifre FROM eposta_ayarlari WHERE berber_id = %s", (aktif_berber_id,))
    ep_ayar = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM randevular WHERE berber_id = %s AND durum = 'Aktif'", (aktif_berber_id,))
    aktif_sonuc = cursor.fetchone()
    aktif_randevu_sayisi = aktif_sonuc[0] if aktif_sonuc else 0

    baglanti.close()

    mevcut_soz = ayar[0] if ayar else "Tarzınızı Yeniden Keşfedin"
    mevcut_resim = ayar[1] if ayar else "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?auto=format&fit=crop&w=1350&q=80"
    mevcut_mail = ep_ayar[0] if ep_ayar and ep_ayar[0] else ""
    mevcut_mail_sifre = ep_ayar[1] if ep_ayar and ep_ayar[1] else ""

    berber_butonlari_html = ""
    for b in tum_berberler:
        aktif_class = "background: #d4af37; color: #000;" if str(b[0]) == str(aktif_berber_id) else "background: #2a2a2a; color: #fff;"
        berber_butonlari_html += f'<a href="/admin/berber-degis/{b[0]}" style="padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold; {aktif_class}">#{b[0]} {b[1]}</a>'

    html_icerik = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Brothers Barber - {berber_adi} Paneli</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Poppins', sans-serif; background-color: #121212; color: #fff; padding: 20px; }}
            h1, h2 {{ text-align: center; color: #d4af37; }}
            h2 {{ margin-top: 40px; font-size: 20px; border-bottom: 1px solid #333; padding-bottom: 10px; }}
            .ust-menu {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; background: #1e1e1e; padding: 15px 20px; border-radius: 8px; flex-wrap: wrap; gap: 10px; }}
            .personel-secim-bar {{ display: flex; gap: 5px; flex-wrap: wrap; align-items: center; }}
            .stats-container {{ display: flex; gap: 20px; margin-top: 20px; justify-content: center; }}
            .stat-box {{ background: #1e1e1e; border: 1px solid #333; padding: 20px; border-radius: 8px; text-align: center; width: 250px; }}
            .stat-box h3 {{ color: #d4af37; font-size: 24px; margin-top: 5px; }}
            .btn-temizle {{ background-color: #e74c3c; color: white; padding: 8px 15px; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 14px; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; background: #1e1e1e; border-radius: 8px; overflow: hidden; margin-bottom: 20px; }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #333; font-size: 14px; }}
            th {{ background-color: #d4af37; color: #000; }}
            tr:hover {{ background-color: #2a2a2a; }}
            .islem-butonlari {{ display: flex; gap: 6px; }}
            .btn-iptal {{ background-color: #f39c12; color: white; padding: 6px 10px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; font-size: 13px; }}
            .btn-sil {{ background-color: #e74c3c; color: white; padding: 6px 10px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; font-size: 13px; }}
            .badge-aktif {{ color: #2ecc71; font-weight: bold; }}
            .badge-iptal {{ color: #e74c3c; font-weight: bold; }}
            .form-kutu {{ background: #1e1e1e; padding: 20px; border-radius: 8px; margin-top: 15px; max-width: 600px; margin-left: auto; margin-right: auto; }}
            .form-kutu input, .form-kutu textarea {{ width: 100%; padding: 10px; margin-bottom: 12px; border-radius: 6px; border: 1px solid #333; background: #2a2a2a; color: #fff; outline: none; }}
            .form-kutu button {{ background-color: #2ecc71; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; }}
            .form-kutu button:hover {{ background-color: #27ae60; }}
        </style>
    </head>
    <body>
        <h1>Brothers Barber Shop - Yönetici Paneli ({berber_adi})</h1>
        
        <div class="ust-menu">
            <div class="personel-secim-bar">
                <span style="font-size: 12px; color: #aaa; margin-right: 5px;">Personeller (1-10):</span>
                {berber_butonlari_html}
            </div>
            <a href="/admin/tumunu-sil" class="btn-temizle" onclick="return confirm('Size ait tüm randevuları silmek istediğinize emin misiniz?');">Randevularımı Temizle</a>
        </div>

        <div class="stats-container">
            <div class="stat-box">
                <p style="color: #aaa; font-size: 13px; text-transform: uppercase;">Aktif Randevularım</p>
                <h3>{aktif_randevu_sayisi}</h3>
            </div>
        </div>

        <h2>Kişisel Adınızı ve Şifrenizi Değiştirin</h2>
        <div class="form-kutu">
            <form action="/admin/profil-guncelle" method="POST">
                <label style="font-size:13px; color:#aaa;">Görünen Adınız:</label>
                <input type="text" name="yeni_isim" value="{berber_adi}" required>
                <label style="font-size:13px; color:#aaa;">Yeni Şifreniz:</label>
                <input type="password" name="yeni_sifre" placeholder="Yeni şifre belirleyin" required>
                <button type="submit" style="background-color: #d4af37; color: #000;">Profili Güncelle</button>
            </form>
        </div>

        <h2>Kişisel E-Posta Bildirim Ayarlarınız ({berber_adi})</h2>
        <div class="form-kutu">
            <form action="/admin/eposta-ayar" method="POST">
                <label style="font-size:13px; color:#aaa;">Kendi Gmail Adresiniz:</label>
                <input type="email" name="gonderen_mail" value="{mevcut_mail}" placeholder="ornek@gmail.com" required>
                <label style="font-size:13px; color:#aaa;">Gmail Uygulama Şifreniz (App Password):</label>
                <input type="password" name="gonderen_sifre" value="{mevcut_mail_sifre}" placeholder="Google uygulama şifreniz" required>
                <button type="submit" style="background-color: #d4af37; color: #000;">Mail Ayarlarımı Kaydet</button>
            </form>
        </div>

        <h2>Size Gelen Randevular ({berber_adi})</h2>
        <table>
            <tr>
                <th>Ad Soyad</th>
                <th>İletişim</th>
                <th>Hizmet</th>
                <th>Tarih / Saat</th>
                <th>Müşteri Notu</th>
                <th>Durum</th>
                <th>İşlemler</th>
            </tr>
    """
    
    for r in randevular:
        durum_class = "badge-aktif" if r[8] == 'Aktif' else "badge-iptal"
        iletisim_bilgisi = f"{r[1]}<br><span style='font-size:12px; color:#888;'>{r[2]}</span><br><span style='font-size:11px; color:#aaa;'>{r[3]}</span>"
        islem_kismi = f'<a href="/admin/iptal/{r[0]}" class="btn-iptal" onclick="return confirm(\'İptal edilsin mi?\');">İptal Et</a>' if r[8] == 'Aktif' else '<span style="color:#777; font-size:13px;">İptal Edildi</span>'
        tamamen_sil_butonu = f'<a href="/admin/tek-sil/{r[0]}" class="btn-sil" onclick="return confirm(\'Silinsin mi?\');">Sil</a>'

        html_icerik += f"""
            <tr>
                <td><strong>{r[1]}</strong></td>
                <td>{iletisim_bilgisi}</td>
                <td>{r[4]}</td>
                <td>{r[5]} <br><strong>{r[6]}</strong></td>
                <td style="font-style: italic; color: #ccc;">{r[7]}</td>
                <td><span class="{durum_class}">{r[8]}</span></td>
                <td>
                    <div class="islem-butonlari">
                        {islem_kismi}
                        {tamamen_sil_butonu}
                    </div>
                </td>
            </tr>
        """
        
    html_icerik += f"""
        </table>

        <h2>Ana Sayfa Slogan ve Fotoğraf Ayarları (Ortak)</h2>
        <div class="form-kutu">
            <form action="/admin/site-ayar" method="POST">
                <label style="font-size:13px; color:#aaa;">Ana Slogan / Karşılama Sözü:</label>
                <input type="text" name="ana_soz" value="{mevcut_soz}" required>
                <label style="font-size:13px; color:#aaa;">Arka Plan Fotoğraf Linki (URL):</label>
                <input type="text" name="hero_resim" value="{mevcut_resim}" required>
                <button type="submit">Ayarları Güncelle</button>
            </form>
        </div>

        <h2>Hizmetler ve Fiyat Listesi Yönetimi</h2>
        <div class="form-kutu">
            <form action="/admin/hizmet-ekle" method="POST">
                <input type="text" name="hizmet_adi" placeholder="Hizmet Adı (Örn: Saç Kesimi)" required>
                <input type="text" name="fiyat" placeholder="Fiyat (Örn: 350 TL)" required>
                <input type="text" name="aciklama" placeholder="Kısa Açıklama" required>
                <button type="submit">Yeni Hizmet Ekle</button>
            </form>
        </div>

        <table>
            <tr>
                <th>Hizmet Adı</th>
                <th>Fiyat</th>
                <th>Açıklama</th>
                <th>İşlem</th>
            </tr>
    """

    for h in hizmetler:
        html_icerik += f"""
            <tr>
                <td>{h[1]}</td>
                <td><strong style="color:#d4af37;">{h[2]}</strong></td>
                <td>{h[3]}</td>
                <td><a href="/admin/hizmet-sil/{h[0]}" class="btn-sil" onclick="return confirm(\'Kaldırılsın mı?\');">Kaldır</a></td>
            </tr>
        """

    html_icerik += """
        </table>
    </body>
    </html>
    """
    return HTMLResponse(content=html_icerik)

@app.get("/admin/berber-degis/{berber_id}")
async def berber_degis(berber_id: int):
    response = RedirectResponse(url="/admin/panel", status_code=303)
    response.set_cookie(key="aktif_berber_id", value=str(berber_id))
    return response

@app.post("/admin/profil-guncelle")
async def profil_guncelle(request: Request):
    try:
        form = await request.form()
        yeni_isim = str(form.get("yeni_isim", ""))
        yeni_sifre = str(form.get("yeni_sifre", ""))
    except Exception:
        return RedirectResponse(url="/admin/panel", status_code=303)

    aktif_berber_id = request.cookies.get("aktif_berber_id", "1")
    if request.cookies.get("admin_giris") != "aktif":
        return RedirectResponse(url="/admin", status_code=303)

    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("UPDATE berberler SET isim = %s, sifre = %s WHERE id = %s", (yeni_isim, yeni_sifre, aktif_berber_id))
    baglanti.commit()
    baglanti.close()
    return RedirectResponse(url="/admin/panel", status_code=303)

@app.post("/admin/eposta-ayar")
async def eposta_ayar_guncelle(request: Request):
    try:
        form = await request.form()
        gonderen_mail = str(form.get("gonderen_mail", ""))
        gonderen_sifre = str(form.get("gonderen_sifre", ""))
    except Exception:
        return RedirectResponse(url="/admin/panel", status_code=303)

    aktif_berber_id = request.cookies.get("aktif_berber_id", "1")
    if request.cookies.get("admin_giris") != "aktif":
        return RedirectResponse(url="/admin", status_code=303)

    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("UPDATE eposta_ayarlari SET gonderen_mail = %s, gonderen_sifre = %s WHERE berber_id = %s", (gonderen_mail, gonderen_sifre, aktif_berber_id))
    baglanti.commit()
    baglanti.close()
    return RedirectResponse(url="/admin/panel", status_code=303)

@app.post("/admin/site-ayar")
async def site_ayar_guncelle(request: Request):
    try:
        form = await request.form()
        ana_soz = str(form.get("ana_soz", ""))
        hero_resim = str(form.get("hero_resim", ""))
    except Exception:
        return RedirectResponse(url="/admin/panel", status_code=303)

    if request.cookies.get("admin_giris") != "aktif":
        return RedirectResponse(url="/admin", status_code=303)

    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("DELETE FROM site_ayarlari")
    cursor.execute("INSERT INTO site_ayarlari (id, ana_soz, hero_resim) VALUES (1, %s, %s)", (ana_soz, hero_resim))
    baglanti.commit()
    baglanti.close()
    return RedirectResponse(url="/admin/panel", status_code=303)

@app.post("/admin/hizmet-ekle")
async def hizmet_ekle(request: Request):
    try:
        form = await request.form()
        hizmet_adi = str(form.get("hizmet_adi", ""))
        fiyat = str(form.get("fiyat", ""))
        aciklama = str(form.get("aciklama", ""))
    except Exception:
        return RedirectResponse(url="/admin/panel", status_code=303)

    if request.cookies.get("admin_giris") != "aktif":
        return RedirectResponse(url="/admin", status_code=303)

    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("INSERT INTO hizmetler (ad, fiyat, aciklama) VALUES (%s, %s, %s)", (hizmet_adi, fiyat, aciklama))
    baglanti.commit()
    baglanti.close()
    return RedirectResponse(url="/admin/panel", status_code=303)

@app.get("/admin/hizmet-sil/{hizmet_id}")
async def hizmet_sil(hizmet_id: int, request: Request):
    if request.cookies.get("admin_giris") != "aktif":
        return RedirectResponse(url="/admin", status_code=303)
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("DELETE FROM hizmetler WHERE id = %s", (hizmet_id,))
    baglanti.commit()
    baglanti.close()
    return RedirectResponse(url="/admin/panel", status_code=303)

@app.get("/admin/iptal/{randevu_id}")
async def randevu_iptal(randevu_id: int, request: Request):
    if request.cookies.get("admin_giris") != "aktif":
        return RedirectResponse(url="/admin", status_code=303)
        
    aktif_berber_id = request.cookies.get("aktif_berber_id", "1")
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("SELECT isim, email, hizmet, tarih, saat FROM randevular WHERE id = %s", (randevu_id,))
    randevu = cursor.fetchone()
    
    if randevu:
        isim, email, hizmet, tarih, saat = randevu
        cursor.execute("UPDATE randevular SET durum = 'İptal Edildi' WHERE id = %s", (randevu_id,))
        baglanti.commit()
        
        if email:
            berber_mail_gonder(int(aktif_berber_id), email, "Randevu İptali - Brothers Barber", f"Sayın {isim},<br>{tarih} saat {saat} tarihli <b>{hizmet}</b> randevunuz işletmemiz tarafından iptal edilmiştir.")

    baglanti.close()
    return RedirectResponse(url="/admin/panel", status_code=303)

@app.get("/admin/tek-sil/{randevu_id}")
async def tek_randevu_sil(randevu_id: int, request: Request):
    if request.cookies.get("admin_giris") != "aktif":
        return RedirectResponse(url="/admin", status_code=303)
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("DELETE FROM randevular WHERE id = %s", (randevu_id,))
    baglanti.commit()
    baglanti.close()
    return RedirectResponse(url="/admin/panel", status_code=303)

@app.get("/admin/tumunu-sil")
async def tumunu_sil(request: Request):
    if request.cookies.get("admin_giris") != "aktif":
        return RedirectResponse(url="/admin", status_code=303)
    
    aktif_berber_id = request.cookies.get("aktif_berber_id", "1")
    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    cursor.execute("DELETE FROM randevular WHERE berber_id = %s", (aktif_berber_id,))
    baglanti.commit()
    baglanti.close()
    return RedirectResponse(url="/admin/panel", status_code=303)