import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# Hata ayıklama ayarları
st.set_page_config(page_title="ISD Turnuva", layout="wide")

def init_db():
    # Veritabanı adını en basit hale getirdik
    conn = sqlite3.connect('isd_final.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS turnuva_ayar (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS sonuclar (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL, turnuva_id INTEGER)')
    conn.execute('CREATE TABLE IF NOT EXISTS eslesmeler (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)')
    conn.commit()
    return conn

conn = init_db()

st.sidebar.title("ISD Yonetim")
menu = st.sidebar.radio("Menu", ["Mevcut Turnuva", "Arsiv"])

if menu == "Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum='Aktif'").fetchone()

    if not aktif:
        st.header("Yeni Turnuva Baslat")
        with st.form("kurulum"):
            t_ad = st.text_input("Turnuva Adi")
            t_tur = st.slider("Tur Sayisi", 1, 11, 5)
            if st.form_submit_button("Baslat"):
                conn.execute("INSERT INTO turnuva_ayar (ad, toplam_tur, mevcut_tur, durum) VALUES (?, ?, 1, 'Aktif')", (t_ad, t_tur))
                conn.commit()
                st.rerun()
    else:
        t_id, t_ad, t_toplam, t_mevcut, t_durum = aktif
        st.subheader(f"{t_ad} - Tur {t_mevcut}")
        
        tab1, tab2, tab3 = st.tabs(["Kayit", "Eslendirme", "Siralama"])

        with tab1:
            with st.form("kayit_form", clear_on_submit=True):
                y_isim = st.text_input("Ad Soyad")
                y_elo = st.number_input("ELO", value=1000)
                if st.form_submit_button("Ekle"):
                    if y_isim:
                        conn.execute("INSERT INTO sonuclar (isim, elo, puan, turnuva_id) VALUES (?, ?, 0.0, ?)", (y_isim, y_elo, t_id))
                        conn.commit()
                        st.rerun()
            
            # Oyuncu Listesi
            df_oy = pd.read_sql(f"SELECT id, isim, elo FROM sonuclar WHERE turnuva_id={t_id}", conn)
            st.write("### Kayitli Oyuncular")
            st.table(df_oy[['isim', 'elo']])

        with tab2:
            mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
            if not mevcut_m:
                if st.button("Eslendirmeyi Yap"):
                    df_p = pd.read_sql(f"SELECT isim FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, elo DESC", conn)
                    liste = df_p['isim'].tolist()
                    if len(liste) >= 2:
                        if len(liste) % 2 != 0:
                            bye = liste.pop()
                            conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, ?)", (t_id, t_mevcut, bye, "BAY", "1.0"))
                        yari = len(liste) // 2
                        ust, alt = liste[:yari], liste[yari:]
                        for i in range(yari):
                            conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, ?)", (t_id, t_mevcut, ust[i], alt[i], "Bekliyor"))
                        conn.commit()
                        st.rerun()
            else:
                with st.form("sonuc_g"):
                    maçlar = []
                    for i, (b, s, res) in enumerate(mevcut_m, 1):
                        if s == "BAY": st.info(f"BAY: {b}")
                        else:
                            st.write(f"Masa {i}: {b} - {s}")
                            skor = st.selectbox("Sonuc", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"m_{i}")
                            maçlar.append((b, s, skor))
                    if st.form_submit_button("Kaydet"):
                        for b, s, r in maçlar:
                            if r != "Bekliyor":
                                p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                conn.execute("UPDATE sonuclar SET puan = puan + ? WHERE isim = ?", (p1, b))
                                conn.execute("UPDATE sonuclar SET puan = puan + ? WHERE isim = ?", (1.0-p1, s))
                                conn.execute("UPDATE eslesmeler SET sonuc=? WHERE beyaz=?", (r, b))
                        if t_mevcut < t_toplam:
                            conn.execute("UPDATE turnuva_ayar SET mevcut_tur = ?", (t_mevcut + 1,))
                        else:
                            conn.execute("UPDATE turnuva_ayar SET durum = 'Bitti'")
                        conn.commit()
                        st.rerun()

                # WhatsApp Paylas
                txt = f"Tur {t_mevcut} Eslenme:\n" + "\n".join([f"Masa {i+1}: {m[0]}-{m[1]}" for i, m in enumerate(mevcut_m)])
                st.link_button("WhatsApp", f"https://