import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="ISD FIDE Sistemi", layout="wide", page_icon="♟️")

# 2. Veritabanı (v100 - Tam Stabil Sürüm)
def init_db():
    conn = sqlite3.connect('isd_fide_v100.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS turnuva_ayar (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)')
    conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                    (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL DEFAULT 0.0, turnuva_id INTEGER, 
                     renk_farki INTEGER DEFAULT 0, son_renk INTEGER DEFAULT 0)''')
    conn.execute('CREATE TABLE IF NOT EXISTS eslesmeler (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)')
    conn.commit()
    return conn

conn = init_db()

# --- RENK BELİRLEME (FIDE 4.3.5 - 4.3.8) ---
def renk_belirle(o1, o2):
    # Madde 4.3.5: Renk farkı düşük olana (örn: -1, +1'den küçüktür) Beyaz ver.
    if o1['renk_farki'] < o2['renk_farki']:
        return o1['isim'], o2['isim']
    elif o2['renk_farki'] < o1['renk_farki']:
        return o2['isim'], o1['isim']
    # Madde 4.3.6: Renk farkları eşitse, son rengin tersini uygula.
    if o1['son_renk'] == 1: # o1 son tur Beyazdı
        return o2['isim'], o1['isim']
    return o1['isim'], o2['isim']

# --- MENÜ ---
st.sidebar.title("İSD FIDE Yönetim")
menu = st.sidebar.radio("Menü", ["🏆 Mevcut Turnuva", "📜 Arşiv"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum='Aktif' OR durum='Bitti' ORDER BY id DESC LIMIT 1").fetchone()

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
            st.success(f"🏆 {t_ad} Tamamlandı!")
            # SIRALAMA SORGUSU (Puan ve ELO'ya göre net sıralama)
            df_f = pd.read_sql(f"SELECT isim as Oyuncu, elo as ELO, puan as Puan FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            df_f.index = range(1, len(df_f)+1)
            st.table(df_f)
            if st.button("Arşive Gönder ve Yeni Turnuva Hazırla"):
                conn.execute("UPDATE turnuva_ayar SET durum='Arşiv' WHERE id=?", (t_id,))
                conn.commit(); st.rerun()
        else:
            tab1, tab2, tab3 = st.tabs(["👥 Oyuncu Kaydı", "⚔️ Eşlendirme", "📊 Sıralama"])

            with tab1:
                with st.form("kayit", clear_on_submit=True):
                    y_i = st.text_input("Ad Soyad")
                    y_e = st.number_input("ELO", 1000)
                    if st.form_submit_button("Ekle"):
                        if y_i:
                            conn.execute("INSERT INTO sonuclar (isim, elo, puan, turnuva_id) VALUES (?, ?, 0.0, ?)", (y_i, y_e, t_id))
                            conn.commit(); st.rerun()
                df_l = pd.read_sql(f"SELECT id, isim, elo FROM sonuclar WHERE turnuva_id={t_id}", conn)
                for r in df_l.itertuples():
                    c1, c2, c3 = st.columns([4, 1, 1])
                    c1.write(r.isim)
                    if c3.button("🗑️", key=f"d_{r.id}"):
                        conn.execute("DELETE FROM sonuclar WHERE id=?", (r.id,))
                        conn.commit(); st.rerun()

            with tab2:
                mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
                
                if not mevcut_m:
                    if st.button("🎲 Eşlendirmeyi Yap"):
                        players = pd.read_sql(f"SELECT isim, puan, renk_farki, son_renk FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, elo DESC", conn).to_dict('records')
                        if len(players) >= 2:
                            if len(players) % 2 != 0:
                                bye = players.pop()
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, 'BAY', '1-0')", (t_id, t_mevcut, bye['isim']))
                                conn.execute("UPDATE sonuclar SET puan = puan + 1.0 WHERE isim = ? AND turnuva_id = ?", (bye['isim'], t_id))
                            
                            mid = len(players) // 2
                            ust, alt = players[:mid], players[mid:]
                            for i in range(mid):
                                b, s = renk_belirle(ust[i], alt[i])
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, 'Bekliyor')", (t_id, t_mevcut, b, s))
                            conn.commit(); st.rerun()
                else:
                    with st.form("skor_gir"):
                        maç_verileri = []
                        for i, (b, s, res) in enumerate(mevcut_m, 1):
                            if s == "BAY": st.info(f"✅ BAY: {b}")
                            else:
                                st.write(f"🪑 **Masa {i}:** {b} (B) - {s} (S)")
                                sk = st.selectbox("Sonuç", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"sk_{i}")
                                maç_verileri.append((b, s, sk))
                        
                        if st.form_submit_button("Turu Onayla"):
                            for b, s, r in maç_verileri:
                                if r != "Bekliyor":
                                    p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                    conn.execute("UPDATE sonuclar SET puan = puan + ?, renk_farki = renk_farki + 1, son_renk = 1 WHERE isim = ? AND turnuva_id = ?", (p1, b, t_id))
                                    conn.execute("UPDATE sonuclar SET puan = puan + ?, renk_farki = renk_farki - 1, son_renk = -1 WHERE isim = ? AND turnuva_id = ?", (1.0-p1, s, t_id))
                                    conn.execute("UPDATE eslesmeler SET sonuc=? WHERE beyaz=? AND turnuva_id=? AND tur_no=?", (r, b, t_id, t_mevcut))
                            
                            if t_mevcut < t_toplam:
                                conn.execute("UPDATE turnuva_ayar SET mevcut_tur = ? WHERE id = ?", (t_mevcut + 1, t_id))
                            else:
                                conn.execute("UPDATE turnuva_ayar SET durum = 'Bitti' WHERE id = ?", (t_id,))
                            conn.commit(); st.rerun()
                    
                    wa_t = f"*{t_ad} - Tur {t_mevcut} Eslenme*\n" + "\n".join([f"M{i+1}: {m[0]}-{m[1]}" for i, m in enumerate(mevcut_m)])
                    st.link_button("📲 WhatsApp'ta Paylaş", f"https://wa.me/?text={urllib.parse.quote(wa_t)}")

            with tab3:
                # GÜNCEL SIRALAMA (Buradaki ORDER BY Puan DESC kısmı sıralamayı yapar)
                df_s = pd.read_sql(f"SELECT isim as Oyuncu, elo as ELO, puan as Puan FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
                df_s.index = range(1, len(df_s)+1)
                st.table(df_s)

elif menu == "📜 Arşiv":
    st.header("📚 Arşiv")
    arsiv_df = pd.read_sql("SELECT id, ad FROM turnuva_ayar WHERE durum='Arşiv' OR durum='Bitti'", conn)
    if not arsiv_df.empty:
        s_ad = st.selectbox("Seç", arsiv_df['ad'].tolist())
        s_id = arsiv_df[arsiv_df['ad'] == s_ad]['id'].values[0]
        res = pd.read_sql(f"SELECT isim, elo, puan FROM sonuclar WHERE turnuva_id={s_id} ORDER BY puan DESC", conn)
        st.table(res)