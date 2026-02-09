import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="ISD FIDE Swiss Pro", layout="wide", page_icon="♟️")

# 2. Veritabanı (v140 - Yazım Hatası ve ELO Sütunu Onarıldı)
def init_db():
    conn = sqlite3.connect('isd_fide_v140.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS turnuva_ayar (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)')
    conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                    (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL DEFAULT 0.0, 
                     turnuva_id INTEGER, renk_farki INTEGER DEFAULT 0, son_renk INTEGER DEFAULT 0, 
                     bye_aldimi INTEGER DEFAULT 0, pairing_no INTEGER)''')
    conn.execute('CREATE TABLE IF NOT EXISTS eslesmeler (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)')
    conn.commit()
    return conn

conn = init_db()

# --- PAIRING NUMBER GÜNCELLEME (FIDE Madde 7) ---
def guncelle_pairing_no(t_id):
    # Madde 7: ELO'ya göre sıralayıp Pairing Number atar
    players = pd.read_sql(f"SELECT id FROM sonuclar WHERE turnuva_id={t_id} ORDER BY elo DESC, isim ASC", conn)
    for i, row in enumerate(players.itertuples(), 1):
        conn.execute(f"UPDATE sonuclar SET pairing_no = {i} WHERE id = {row.id}")
    conn.commit()

# --- MENÜ ---
st.sidebar.title("♟️ İSD FIDE Yönetim")
menu = st.sidebar.radio("Menü Seçin", ["🏆 Mevcut Turnuva", "📜 Arşiv"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum IN ('Aktif', 'Bitti') ORDER BY id DESC LIMIT 1").fetchone()

    if not aktif:
        st.header("🏁 Yeni FIDE Turnuvası")
        with st.form("kurulum"):
            t_ad = st.text_input("Turnuva Adı")
            t_tur = st.slider("Tur Sayısı", 1, 11, 5)
            if st.form_submit_button("Başlat"):
                if t_ad:
                    conn.execute("INSERT INTO turnuva_ayar (ad, toplam_tur, mevcut_tur, durum) VALUES (?, ?, 1, 'Aktif')", (t_ad, t_tur))
                    conn.commit(); st.rerun()
    else:
        t_id, t_ad, t_toplam, t_mevcut, t_durum = aktif

        if t_durum == 'Bitti':
            st.header(f"🏆 {t_ad} Final Sonuçları")
            # Madde 16: Puan ve ELO'ya göre sıralama
            df_final = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            st.table(df_final)
            if st.button("Yeni Turnuva İçin Arşive Al"):
                conn.execute(f"UPDATE turnuva_ayar SET durum='Arşiv' WHERE id={t_id}")
                conn.commit(); st.rerun()
        
        else:
            tab1, tab2, tab3 = st.tabs(["👥 Oyuncu Kaydı", "⚔️ Eşlendirme", "📊 Sıralama"])

            with tab1:
                c1, c2 = st.columns([1, 2])
                with c1:
                    with st.form("o_ekle", clear_on_submit=True):
                        ad = st.text_input("Ad Soyad")
                        elo = st.number_input("ELO", 1000)
                        if st.form_submit_button("Listeye Ekle"):
                            if ad:
                                # Yazım hatası burada giderildi
                                conn.execute("INSERT INTO sonuclar (isim, elo, turnuva_id) VALUES (?, ?, ?)", (ad, elo, t_id))
                                conn.commit()
                                guncelle_pairing_no(t_id)
                                st.rerun()
                with c2:
                    st.write("### 📋 Katılımcı Listesi")
                    # ELO Sütunu eklendi
                    df_l = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Ad Soyad', elo as 'ELO' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY pairing_no ASC", conn)
                    st.table(df_l)

            with tab2:
                st.write(f"### Tur {t_mevcut} Eşleşmeleri")
                mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
                
                if not mevcut_m:
                    if st.button("🎲 FIDE Eşlendirmeyi Yap"):
                        players = pd.read_sql(f"SELECT isim FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, elo DESC", conn)['isim'].tolist()
                        if len(players) >= 2:
                            # Madde 8: Bye Atama (Sayı tekse)
                            if len(players) % 2 != 0:
                                bye = players.pop()
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, 'BYE', '1-0')", (t_id, t_mevcut, bye))
                                conn.execute(f"UPDATE sonuclar SET puan=puan+1, bye_aldimi=1 WHERE isim='{bye}' AND turnuva_id={t_id}")
                            # Madde 9.4: Üst yarı alt yarı eşleşmesi
                            for i in range