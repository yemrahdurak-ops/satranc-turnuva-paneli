import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="ISD FIDE Swiss Pro", layout="wide", page_icon="♟️")

# 2. Veritabanı (v110 - Bitiş Sorunu Giderildi)
def init_db():
    conn = sqlite3.connect('isd_fide_final_v110.db', check_same_thread=False)
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

# --- MENÜ SİSTEMİ ---
st.sidebar.title("♟️ İSD FIDE Yönetim")
menu = st.sidebar.radio("Menü Seçin", ["🏆 Mevcut Turnuva", "📜 Turnuva Arşivi"])

if menu == "🏆 Mevcut Turnuva":
    # Biten turnuvanın da görünmesi için sorguyu güncelledik
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

        # TURNUVA BİTİŞ EKRANI (Madde 16)
        if t_durum == 'Bitti':
            st.balloons()
            st.header(f"🏆 {t_ad} Tamamlandı!")
            st.subheader("Final Sıralaması")
            
            df_final = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            df_final.index = range(1, len(df_final) + 1)
            st.table(df_final)
            
            sir_wa = f"🏆 *{t_ad} Final Sonuçları*\n\n"
            for i, r in df_final.iterrows():
                sir_wa += f"{i}. {r['Oyuncu']} ({r['Puan']} Pn)\n"
            st.link_button("📲 Final Sıralamasını Paylaş", f"https://wa.me/?text={urllib.parse.quote(sir_wa)}")
            
            if st.button("Yeni Turnuva İçin Arşive Gönder"):
                conn.execute("UPDATE turnuva_ayar SET durum='Arşiv' WHERE id=?", (t_id,))
                conn.commit(); st.rerun()
        
        else:
            # AKTİF TURNUVA MODÜLÜ
            st.subheader(f"📍 {t_ad} - Tur {t_mevcut} / {t_toplam}")
            tab1, tab2, tab3 = st.tabs(["👥 Oyuncu Kaydı", "⚔️ Eşlendirme", "📊 Güncel Sıralama"])

            with tab1:
                # Oyuncu Listeleme ve Silme (Lokal kullanım için)
                with st.form("o_ekle", clear_on_submit=True):
                    ad = st.text_input("Ad Soyad")
                    elo = st.number_input("ELO", 1000)
                    if st.form_submit_button("Listeye Ekle"):
                        if ad:
                            conn.execute("INSERT INTO sonuclar (isim, elo, turnuva_id) VALUES (?, ?, ?)", (ad, elo, t_id))
                            conn.commit(); st.rerun()
                
                df_l = pd.read_sql(f"SELECT id, isim, elo FROM sonuclar WHERE turnuva_id={t_id}", conn)
                for r in df_l.itertuples():
                    c1, c2 = st.columns([5, 1])
                    c1.write(r.isim)
                    if c2.button("🗑️", key=f"del_{r.id}"):
                        conn.execute("DELETE FROM sonuclar WHERE id=?", (r.id,))
                        conn.commit(); st.rerun()

            with tab2:
                # Eşlendirme ve Sonuç Girişi
                mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
                if not mevcut_m:
                    if st.button("🎲 FIDE Eşlendirmeyi Yap"):
                        # (Burada önceki mesajda verdiğim fide_pairing_logic fonksiyonu çalışacak)
                        # Test için basit eşleme:
                        players = pd.read_sql(f"SELECT isim FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, elo DESC", conn)['isim'].tolist()
                        if len(players) % 2 != 0:
                            bye = players.pop()
                            conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, 'BYE', '1-0')", (t_id, t_mevcut, bye))
                            conn.execute("UPDATE sonuclar SET puan=puan+1, bye_aldimi=1 WHERE isim=? AND turnuva_id=?", (bye, t_id))
                        for i in range(0, len(players), 2):
                            conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, 'Bekliyor')", (t_id, t_mevcut, players[i], players[i+1]))
                        conn.commit(); st.rerun()
                else:
                    with st.form("sonuc_giris"):
                        form_verileri = []
                        for i, (b, s, res) in enumerate(mevcut_m, 1):
                            if s == "BYE": st.info(f"✅ Masa {i}: {b} (BYE)")
                            else:
                                st.write(f"Masa {i}: {b} - {s}")
                                r_val = st.selectbox("Sonuç", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"m_{t_mevcut}_{i}")
                                form_verileri.append((b, s, r_val))
                        
                        if st.form_submit_button("Turu Onayla"):
                            for b, s, r in form_verileri:
                                if r != "Bekliyor":
                                    p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                    conn.execute("UPDATE sonuclar SET puan=puan+?, renk_farki=renk_farki+1, son_renk=1 WHERE isim=? AND turnuva_id=?", (p1, b, t_id))
                                    conn.execute("UPDATE sonuclar SET puan=puan+?, renk_farki=renk_farki-1, son_renk=-1 WHERE isim=? AND turnuva_id=?", (1.0-p1, s, t_id))
                                    conn.execute("UPDATE eslesmeler SET sonuc=? WHERE beyaz=? AND turnuva_id=? AND tur_no=?", (r, b, t_id, t_mevcut))
                            
                            # TUR KONTROLÜ (Madde 13)
                            if t_mevcut < t_toplam:
                                conn.execute("UPDATE turnuva_ayar SET mevcut_tur = ? WHERE id = ?", (t_mevcut + 1, t_id))
                            else:
                                conn.execute("UPDATE turnuva_ayar SET durum = 'Bitti' WHERE id = ?", (t_id,))
                            conn.commit(); st.rerun()

            with tab3:
                # Madde 16 Sıralama
                df_s = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
                df_s.index = range(1, len(df_s) + 1)
                st.table(df_s)

elif menu == "📜 Turnuva Arşivi":
    # Arşivde sıralama görme
    st.header("📚 Arşiv")
    arsiv_list = pd.read_sql("SELECT id, ad FROM turnuva_ayar WHERE durum IN ('Bitti', 'Arşiv')", conn)
    if not arsiv_list.empty:
        secilen = st.selectbox("Turnuva Seç", arsiv_list['ad'].tolist())
        s_id = arsiv_list[arsiv_df['ad'] == secilen]['id'].values[0] if 'arsiv_df' in locals() else arsiv_list[arsiv_list['ad'] == secilen]['id'].values[0]
        res = pd.read_sql(f"SELECT isim, elo, puan FROM sonuclar WHERE turnuva_id={s_id} ORDER BY puan DESC", conn)
        st.table(res)