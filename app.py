import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# Hata ayıklama için sayfa ayarını en başa alıyoruz
st.set_page_config(page_title="İSD Turnuva Sistemi", layout="wide")

# Veritabanı bağlantısını internete uyumlu hale getiriyoruz
def init_db():
    try:
        conn = sqlite3.connect('isd_final_v15.db', check_same_thread=False)
        conn.execute('''CREATE TABLE IF NOT EXISTS turnuva_ayar 
                        (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                        (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL, turnuva_id INTEGER)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS eslesmeler 
                        (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)''')
        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Veritabanı başlatma hatası: {e}")
        return None

conn = init_db()

if conn:
    st.title("♟️ İSD Turnuva Yönetim Sistemi")
    st.success("Sistem başarıyla bağlandı. Lütfen sol menüden turnuva başlatın.")
    
    # Menü ve diğer fonksiyonlar buraya gelecek...
    # (Önceki en kapsamlı kodun geri kalanını buraya ekleyebilirsin)
else:
    st.error("Sistem başlatılamadı. Lütfen Logs kısmını kontrol edin.")