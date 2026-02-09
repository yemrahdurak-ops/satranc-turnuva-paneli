import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="ISD FIDE Swiss Pro", layout="wide", page_icon="♟️")

# 2. Veritabanı (v120 - ELO Sütunu Görünürlüğü)
def init_db():
    conn = sqlite3.connect('isd_fide_final_v120.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS turnuva_ayar 
                    (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                    (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL DEFAULT 0.0, 
                     turnuva_id INTEGER, renk_farki INTEGER DEFAULT 0, son_renk INTEGER DEFAULT 0, 
                     bye_aldimi INTEGER DEFAULT 0, pairing_no INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS eslesmeler 
                    (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- PAIRING NUMBER GÜNCELLEME (FIDE Madde 7) ---
def update_pairing_numbers(t_id):
    players = pd.read_sql(f"SELECT id FROM sonuclar WHERE turnuva_id={t_id} ORDER BY elo DESC, isim ASC", conn)
    for i, row in enumerate(players.itertuples(), 1):
        conn.execute(f"UPDATE sonuclar SET pairing_no = {i} WHERE id = {row.id}")
    conn.commit()

# --- MENÜ SİSTEMİ ---
st.sidebar.title("♟️ İSD FIDE Yönetim")
menu = st.sidebar.radio("Menü Seçin", ["🏆 Mevcut Turnuva", "📜 Turnuva Arşivi"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum IN ('Aktif', 'Bitti') ORDER BY id DESC LIMIT 1").fetchone()

    if not aktif:
        st.header("🏁 Yeni FIDE Turnuvası")
        with st.form("yeni_t"):
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
            df_final = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            st.table(df_final)
            if st.button("Arşive Kaldır"):
                conn.execute(f"UPDATE turnuva_ayar SET durum='Arşiv' WHERE id={t_id}")
                conn.commit(); st.rerun()
        
        else:
            st.subheader(f"📍 {t_ad} - Tur {t_mevcut}")
            tab1, tab2, tab3 = st.tabs(["👥 Oyuncu Kaydı & Liste", "⚔️ Eşlendirme", "📊 Sıralama"])

            with tab1:
                col_kayit, col_liste = st.columns([1, 2])
                with col_kayit:
                    st.write("### ➕ Yeni Oyuncu")
                    with st.form("o_ekle", clear_on_submit=True):
                        ad = st.text_input("Ad Soyad")
                        elo = st.number_input("ELO (Rating)", 1000)
                        if st.form_submit_button("Listeye Ekle"):
                            if ad:
                                conn.execute("INSERT INTO sonuclar