import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="İSD Turnuva Paneli", layout="wide", page_icon="♟️")

# 2. Veritabanı (v40)
def init_db():
    conn = sqlite3.connect('isd_final_v40.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS turnuva_ayar 
                    (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                    (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL, turnuva_id INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS eslesmeler 
                    (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- MENÜ VE AKTİF TURNUVA KONTROLÜ ---
st.sidebar.title("İSD Yönetim")
menu = st.sidebar.radio("Menü", ["🏆 Mevcut Turnuva", "📜 Turnuva Arşivi"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum='Aktif'").fetchone()

    if aktif:
        t_id, t_ad, t_toplam, t_mevcut, t_durum = aktif
        tab1, tab2, tab3 = st.tabs(["👥 Kayıt", "⚔️ Eşlendirme", "📊 Sıralama"])

        # --- TAB 2: EŞLENDİRME VE WHATSAPP (DÜZELTİLMİŞ) ---
        with tab2:
            mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
            
            if mevcut_m:
                st.write(f"### Tur {t_mevcut} Maçları")
                
                # WHATSAPP MESAJI OLUŞTURMA (GÜVENLİ KODLAMA)
                es_msj = f"*{t_ad} - Tur {t_mevcut} Eslesmeleri*\n\n"
                for i, (b, s, r) in enumerate(mevcut_m, 1):
                    if s == "BAY":
                        es_msj += f"BYE: {b}\n"
                    else:
                        es_msj += f"Masa {i}: {b} - {s}\n"
                
                # Emojisiz ve temiz url kodlama testi
                encoded_msj = urllib.parse.quote(es_msj.encode('utf-8'))
                st.link_button("📲 WhatsApp'ta Paylas", f"https://wa.me/?text={encoded_msj}")
                
                # (Sonuç giriş formu burada devam eder...)

        # --- TAB 3: SIRALAMA VE WHATSAPP (DÜZELTİLMİŞ) ---
        with tab3:
            df_rank = pd.read_sql(f"SELECT isim as Oyuncu, elo as ELO, puan as Puan FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            df_rank.index = range(1, len(df_rank) + 1)
            
            sir_msj = f"*{t_ad} - Guncel Siralama*\n\n"
            for i, r in df_rank.iterrows():
                sir_msj += f"{i}. {r['Oyuncu']} ({r['Puan']:.1f} Pn)\n"
            
            encoded_sir = urllib.parse.quote(sir_msj.encode('utf-8'))
            st.link_button("📲 Siralamayi Paylas", f"https://wa.me/?text={encoded_sir}")
            st.table(df_rank)

# (Kayıt ve Arşiv bölümleri önceki stabil yapıda kalabilir)