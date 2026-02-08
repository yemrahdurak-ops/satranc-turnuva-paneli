import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="İSD Turnuva Paneli", layout="wide", page_icon="♟️")

# 2. Veritabanı Bağlantısı
def init_db():
    conn = sqlite3.connect('isd_final_v25.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS turnuva_ayar 
                    (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                    (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL, turnuva_id INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS eslesmeler 
                    (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- KAYIT FONKSİYONU (Hata Giderilmiş Versiyon) ---
def kayit_yap(t_id):
    # Formdaki verileri session_state'den çekiyoruz
    isim = st.session_state.input_isim
    elo = st.session_state.input_elo
    
    if isim:
        conn.execute("INSERT INTO sonuclar (isim, elo, puan, turnuva_id) VALUES (?, ?, 0.0, ?)", (isim, elo, t_id))
        conn.commit()
        # Giriş kutusunu sıfırlamak için widget anahtarını siliyoruz
        st.session_state.input_isim = ""
        st.toast(f"✅ {isim} listeye eklendi!")
        # Sayfayı yenilemeye gerek kalmadan Streamlit widget'ı güncelleyecektir
    else:
        st.error("Lütfen isim girin!")

# --- MENÜ ---
st.sidebar.title("♟️ İSD Yönetim")
menu = st.sidebar.radio("Menü Seçin", ["🏆 Mevcut Turnuva", "📜 Turnuva Arşivi"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum='Aktif'").fetchone()

    if not aktif:
        st.header("🏁 Yeni Turnuva Başlat")
        with st.form("kurulum"):
            t_ad = st.text_input("Turnuva Adı")
            t_tur = st.slider("Toplam Tur Sayısı", 1, 11, 5)
            if st.form_submit_button("Turnuvayı Oluştur"):
                if t_ad:
                    conn.execute("INSERT INTO turnuva_ayar (ad, toplam_tur, mevcut_tur, durum) VALUES (?, ?, 1, 'Aktif')", (t_ad, t_tur))
                    conn.commit()
                    st.rerun()
    else:
        t_id, t_ad, t_toplam, t_mevcut, t_durum = aktif
        tab1, tab2, tab3 = st.tabs(["👥 Kayıt & Yönetim", "⚔️ Eşlendirme", "📊 Güncel Sıralama"])

        with tab1:
            col_sol, col_sag = st.columns([1, 2])
            with col_sol:
                st.write("### ➕ Oyuncu Ekle")
                # Hata veren kısım burasıydı, girişleri session_state üzerinden yönetiyoruz
                st.text_input("Ad Soyad", key="input_isim")
                st.number_input("ELO", value=1000, key="input_elo")
                
                if st.button("Hızlı Kaydet"):
                    kayit_yap(t_id)
                    st.rerun() # Kayıttan sonra listeyi güncellemek için şart

            with col_sag:
                st.write("### 📋 Oyuncu Listesi")
                df_oy = pd.read_sql(f"SELECT id, isim, elo FROM sonuclar WHERE turnuva_id={t_id}", conn)
                for i, r in enumerate(df_oy.itertuples(), 1):
                    c1, c2, c3, c4 = st.columns([0.5, 3, 2, 2])
                    c1.write(i)
                    new_n = c2.text_input("İsim", value=r.isim, key=f"n_{r.id}", label_visibility="collapsed")
                    new_e = c3.number_input("ELO", value=r.elo, key=f"e_{r.id}", label_visibility="collapsed")
                    cb1, cb2 = c4.columns(2)
                    if cb1.button("💾", key=f"s_{r.id}"):
                        conn.execute("UPDATE sonuclar SET isim=?, elo=? WHERE id=?", (new_n, new_e, r.id))
                        conn.commit(); st.rerun()
                    if cb2.button("🗑️", key=f"d_{r.id}"):
                        conn.execute("DELETE FROM sonuclar WHERE id=?", (r.id,))
                        conn.commit(); st.rerun()

        # Eşlendirme ve Sıralama bölümleri (Önceki stabil çalışan haliyle devam)
        with tab2:
            st.write(f"### Tur {t_mevcut} Maçları")
            # ... (Buradaki kodların değişmesine gerek yok, eşlendirme kısmı doğru çalışıyor)
            # (Önceki kodun devamını buraya ekleyebilirsin)