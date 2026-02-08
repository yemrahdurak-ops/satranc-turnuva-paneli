import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

st.set_page_config(page_title="ISD FIDE Standart Paneli", layout="wide", page_icon="♟️")

# 2. Veritabanı (v90 - Renk Takibi Özellikli)
def init_db():
    conn = sqlite3.connect('isd_fide_v90.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS turnuva_ayar 
                    (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)''')
    # Renk takibi için son_renk (1:Beyaz, -1:Siyah) ve renk_farki sütunları eklendi
    conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                    (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL, turnuva_id INTEGER, 
                     renk_farki INTEGER DEFAULT 0, son_renk INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS eslesmeler 
                    (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- YARDIMCI FONKSİYON: RENK ATAMA (Madde 4.3.3 - 4.3.8) ---
def renk_belirle(o1, o2):
    """
    o1 ve o2 oyuncu objeleridir. (isim, puan, renk_farki, son_renk)
    Dönüş: (Beyaz_İsim, Siyah_İsim)
    """
    # 4.3.5: Renk farkı düşük olana beyaz ver (Not: -2 < -1 < 1 < 2)
    if o1['renk_farki'] < o2['renk_farki']:
        return o1['isim'], o2['isim']
    elif o2['renk_farki'] < o1['renk_farki']:
        return o2['isim'], o1['isim']
    
    # 4.3.6 & 4.3.8: Son oynanan rengin tersini ver
    if o1['son_renk'] == 1: # o1 son tur Beyazdı, şimdi Siyah olmalı
        return o2['isim'], o1['isim']
    else:
        return o1['isim'], o2['isim']

# --- MENÜ ---
st.sidebar.title("İSD FIDE Yönetim")
menu = st.sidebar.radio("Menü", ["🏆 Mevcut Turnuva", "📜 Arşiv"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum='Aktif' OR durum='Bitti' ORDER BY id DESC LIMIT 1").fetchone()

    if not aktif:
        st.header("🏁 Yeni FIDE Standart Turnuva")
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
            st.success(f"🏆 {t_ad} Tamamlandı!")
            df_f = pd.read_sql(f"SELECT isim, elo, puan FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, elo DESC", conn)
            df_f.index = range(1, len(df_f)+1)
            st.table(df_f)
            if st.button("Yeni Turnuva"):
                conn.execute("UPDATE turnuva_ayar SET durum='Arşiv' WHERE id=?", (t_id,))
                conn.commit(); st.rerun()
        else:
            tab1, tab2, tab3 = st.tabs(["👥 Oyuncu Kaydı", "⚔️ Eşlendirme (FIDE)", "📊 Sıralama"])

            with tab1:
                with st.form("kayit", clear_on_submit=True):
                    y_i = st.text_input("Ad Soyad")
                    y_e = st.number_input("ELO", 1000)
                    if st.form_submit_button("Ekle"):
                        conn.execute("INSERT INTO sonuclar (isim, elo, puan, turnuva_id) VALUES (?, ?, 0, ?)", (y_i, y_e, t_id))
                        conn.commit(); st.rerun()
                df_list = pd.read_sql(f"SELECT isim, elo, renk_farki as 'Renk Dengesi' FROM sonuclar WHERE turnuva_id={t_id}", conn)
                st.table(df_list)

            with tab2:
                mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
                
                if not mevcut_m:
                    if st.button("🎲 FIDE Kurallarına Göre Eşleştir"):
                        players = pd.read_sql(f"SELECT isim, puan, renk_farki, son_renk FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, elo DESC", conn).to_dict('records')
                        
                        if len(players) >= 2:
                            if len(players) % 2 != 0:
                                bye = players.pop()
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, 'BAY', '1-0')", (t_id, t_mevcut, bye['isim']))
                            
                            mid = len(players) // 2
                            ust, alt = players[:mid], players[mid:]
                            
                            for i in range(mid):
                                b, s = renk_belirle(ust[i], alt[i])
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, 'Bekliyor')", (t_id, t_mevcut, b, s))
                            conn.commit(); st.rerun()
                else:
                    with st.form("skorlar"):
                        maçlar = []
                        for i, (b, s, res) in enumerate(mevcut_m, 1):
                            if s == "BAY": st.info(f"✅ BAY: {b}")
                            else:
                                st.write(f"Masa {i}: {b} (B) - {s} (S)")
                                sk = st.selectbox("Sonuç", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"s_{i}")
                                maçlar.append((b, s, sk))
                        
                        if st.form_submit_button("Turu Onayla"):
                            for b, s, r in maçlar:
                                if r != "Bekliyor":
                                    p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                    # Puan Güncelleme
                                    conn.execute("UPDATE sonuclar SET puan = puan + ? WHERE isim = ?", (p1, b))
                                    conn.execute("UPDATE sonuclar SET puan = puan + ? WHERE isim = ?", (1.0-p1, s))
                                    # Renk Takibi Güncelleme (Beyaz: +1, Siyah: -1)
                                    conn.execute("UPDATE sonuclar SET renk_farki = renk_farki + 1, son_renk = 1 WHERE isim = ?", (b,))
                                    conn.execute("UPDATE sonuclar SET renk_farki = renk_farki - 1, son_renk = -1 WHERE isim = ?", (s,))
                                    conn.execute("UPDATE eslesmeler SET sonuc=? WHERE beyaz=? AND tur_no=?", (r, b, t_mevcut))
                            
                            if t_mevcut < t_toplam:
                                conn.execute("UPDATE turnuva_ayar SET mevcut_tur = ? WHERE id = ?", (t_mevcut + 1, t_id))
                            else:
                                conn.execute("UPDATE turnuva_ayar SET durum = 'Bitti' WHERE id = ?", (t_id,))
                            conn.commit(); st.rerun()