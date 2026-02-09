import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse
import random

# 1. Sayfa ve Veritabanı Ayarları
st.set_page_config(page_title="ISD FIDE Swiss Pro", layout="wide")

def init_db():
    conn = sqlite3.connect('isd_fide_pro_v1.db', check_same_thread=False)
    # Eşleşme geçmişi için tabloyu güncel tutuyoruz
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

# --- FIDE EŞLENDİRME MANTIĞI (MADDE 7-12) ---

def get_pairing_numbers(t_id):
    """Madde 7: Başlangıç sıralamasına göre eşleştirme numaraları atar."""
    players = pd.read_sql(f"SELECT id, isim, elo FROM sonuclar WHERE turnuva_id={t_id} ORDER BY elo DESC, isim ASC", conn)
    for i, row in enumerate(players.itertuples(), 1):
        conn.execute("UPDATE sonuclar SET pairing_no = ? WHERE id = ?", (i, row.id))
    conn.commit()

def check_compatibility(p1_isim, p2_isim, t_id):
    """Madde 9.1: İki oyuncu daha önce karşılaştı mı?"""
    query = f"""SELECT COUNT(*) FROM eslesmeler 
                WHERE turnuva_id={t_id} 
                AND ((beyaz='{p1_isim}' AND siyah='{p2_isim}') OR (beyaz='{p2_isim}' AND siyah='{p1_isim}'))"""
    count = conn.execute(query).fetchone()[0]
    return count == 0

def fide_pairing_logic(t_id, mevcut_tur):
    """FIDE Madde 9 ve 10: Puan gruplarına göre eşlendirme."""
    # Tüm oyuncuları çek
    df_players = pd.read_sql(f"SELECT * FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, pairing_no ASC", conn)
    players = df_players.to_dict('records')
    
    paired_names = set()
    pairings = []

    # Madde 8: Bye Ataması (Eğer oyuncu sayısı tekse)
    if len(players) % 2 != 0:
        # Madde 8.1 & 8.2: En düşük puan grubundaki, Bye almamış en düşük pairing numaralı oyuncu
        for p in reversed(players):
            if p['bye_aldimi'] == 0:
                pairings.append({'beyaz': p['isim'], 'siyah': 'BYE', 'sonuc': '1-0'})
                paired_names.add(p['isim'])
                conn.execute(f"UPDATE sonuclar SET bye_aldimi=1, puan=puan+1 WHERE id={p['id']}")
                break

    # Kalan oyuncuları puan gruplarına ayır (Madde 9.2)
    remaining = [p for p in players if p['isim'] not in paired_names]
    
    # Basitleştirilmiş FIDE Puan Grubu Eşleştirmesi (Madde 9.4)
    # Not: Tam algoritma floater (9.3) ve değişim kurallarını (11) içerir.
    i = 0
    while i < len(remaining):
        p1 = remaining[i]
        if p1['isim'] in paired_names:
            i += 1
            continue
        
        found = False
        # Kendisinden sonraki en uygun (daha önce oynamadığı) oyuncuyu bul
        for j in range(i + 1, len(remaining)):
            p2 = remaining[j]
            if p2['isim'] not in paired_names and check_compatibility(p1['isim'], p2['isim'], t_id):
                # Madde 12: Renk Belirleme
                if p1['renk_farki'] <= p2['renk_farki']:
                    pairings.append({'beyaz': p1['isim'], 'siyah': p2['isim']})
                else:
                    pairings.append({'beyaz': p2['isim'], 'siyah': p1['isim']})
                
                paired_names.add(p1['isim'])
                paired_names.add(p2['isim'])
                found = True
                break
        
        if not found and p1['isim'] not in paired_names:
            # Madde 10: Floater durumu (Alt gruba kaydır - Basitleştirilmiş)
            pass 
        i += 1
    
    return pairings

# --- STREAMLIT ARAYÜZÜ ---

st.sidebar.title("♟️ İSD FIDE Swiss")
menu = st.sidebar.radio("Menü", ["🏆 Mevcut Turnuva", "📜 Arşiv"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum='Aktif' OR durum='Bitti' ORDER BY id DESC LIMIT 1").fetchone()

    if not aktif:
        st.header("🏁 Yeni FIDE Turnuvası Başlat")
        with st.form("setup"):
            t_ad = st.text_input("Turnuva Adı")
            t_tur = st.slider("Tur Sayısı", 1, 11, 5)
            if st.form_submit_button("Turnuvayı Oluştur"):
                conn.execute("INSERT INTO turnuva_ayar (ad, toplam_tur, mevcut_tur, durum) VALUES (?, ?, 1, 'Aktif')", (t_ad, t_tur))
                conn.commit()
                st.rerun()
    else:
        t_id, t_ad, t_toplam, t_tur_no, t_durum = aktif
        
        tab1, tab2, tab3 = st.tabs(["👥 Oyuncu Listesi", "⚔️ FIDE Eşlendirme", "📊 Sıralama"])

        with tab1:
            # Oyuncu Kaydı ve Pairing Number Atama (Madde 7)
            with st.form("reg"):
                name = st.text_input("Oyuncu Adı Soyadı")
                elo = st.number_input("Rating (ELO)", 1000)
                if st.form_submit_button("Kaydet"):
                    conn.execute("INSERT INTO sonuclar (isim, elo, turnuva_id) VALUES (?, ?, ?)", (name, elo, t_id))
                    conn.commit()
                    get_pairing_numbers(t_id) # Madde 7 tetiklenir
                    st.rerun()
            
            st.write("### Katılımcı Listesi (Madde 7)")
            df_p = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Ad Soyad', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY pairing_no ASC", conn)
            st.table(df_p)

        with tab2:
            st.write(f"### Tur {t_tur_no} Eşleşmeleri")
            mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_tur_no)).fetchall()
            
            if not mevcut_m:
                if st.button("🎲 FIDE Eşlendirmeyi Yap"):
                    pairings = fide_pairing_logic(t_id, t_tur_no)
                    for p in pairings:
                        conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, 'Bekliyor')", 
                                     (t_id, t_tur_no, p['beyaz'], p['siyah']))
                    conn.commit()
                    st.rerun()
            else:
                with st.form("results"):
                    results = []
                    for i, (b, s, res) in enumerate(mevcut_m, 1):
                        if s == "BYE":
                            st.info(f"✅ Masa {i}: {b} (BYE - 1 Puan)")
                        else:
                            col1, col2 = st.columns([3, 2])
                            col1.write(f"**Masa {i}:** {b} vs {s}")
                            res_val = col2.selectbox("Sonuç", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"r_{i}")
                            results.append((b, s, res_val))
                    
                    if st.form_submit_button("Turu Onayla"):
                        for b, s, r in results:
                            if r != "Bekliyor":
                                p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                conn.execute("UPDATE sonuclar SET puan=puan+?, renk_farki=renk_farki+1, son_renk=1 WHERE isim=? AND turnuva_id=?", (p1, b, t_id))
                                conn.execute("UPDATE sonuclar SET puan=puan+?, renk_farki=renk_farki-1, son_renk=-1 WHERE isim=? AND turnuva_id=?", (1.0-p1, s, t_id))
                                conn.execute(f"UPDATE eslesmeler SET sonuc='{r}' WHERE beyaz='{b}' AND tur_no={t_tur_no}")
                        
                        if t_tur_no < t_toplam:
                            conn.execute(f"UPDATE turnuva_ayar SET mevcut_tur={t_tur_no+1} WHERE id={t_id}")
                        else:
                            conn.execute(f"UPDATE turnuva_ayar SET durum='Bitti' WHERE id={t_id}")
                        conn.commit()
                        st.rerun()

        with tab3:
            st.write("### Güncel Puan Durumu")
            df_rank = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            st.table(df_rank)