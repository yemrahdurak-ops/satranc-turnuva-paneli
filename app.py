import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="İSD FIDE Yönetim Paneli", layout="wide", page_icon="♟️")

# 2. Veritabanı (v170 - Arşiv ve Düzenleme Geri Geldi)
def init_db():
    conn = sqlite3.connect('isd_fide_v170.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS turnuva_ayar (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)')
    conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                    (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL DEFAULT 0.0, 
                     turnuva_id INTEGER, renk_farki INTEGER DEFAULT 0, son_renk INTEGER DEFAULT 0, 
                     bye_aldimi INTEGER DEFAULT 0, pairing_no INTEGER)''')
    conn.execute('CREATE TABLE IF NOT EXISTS eslesmeler (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)')
    conn.commit()
    return conn

conn = init_db()

# --- PAIRING NO GÜNCELLEME (Madde 7) ---
def guncelle_pairing_no(t_id):
    players = pd.read_sql(f"SELECT id FROM sonuclar WHERE turnuva_id={t_id} ORDER BY elo DESC, isim ASC", conn)
    for i, row in enumerate(players.itertuples(), 1):
        conn.execute(f"UPDATE sonuclar SET pairing_no = {i} WHERE id = {row.id}")
    conn.commit()

# --- MENÜ ---
st.sidebar.title("♟️ İSD Yönetim")
menu = st.sidebar.radio("Menü Seçin", ["🏆 Mevcut Turnuva", "📜 Arşiv ve Geçmiş"])

if menu == "🏆 Mevcut Turnuva":
    # Sadece Aktif ve yeni Biten turnuvaları gösterir
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
            st.success(f"🏆 {t_ad} Tamamlandı! Final sıralaması aşağıdadır.")
            df_final = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            st.table(df_final)
            if st.button("Turnuvayı Arşive Kaldır (Yenisi İçin Yer Aç)"):
                conn.execute(f"UPDATE turnuva_ayar SET durum='Arşiv' WHERE id={t_id}")
                conn.commit(); st.rerun()
        else:
            tab1, tab2, tab3 = st.tabs(["👥 Oyuncu Kaydı & Düzenleme", "⚔️ Eşlendirme", "📊 Sıralama"])

            with tab1:
                # DÜZELTME VE SİLME SEÇENEKLERİ GERİ GELDİ
                c1, c2 = st.columns([1, 2])
                with c1:
                    with st.form("o_ekle", clear_on_submit=True):
                        ad = st.text_input("Ad Soyad")
                        elo = st.number_input("ELO", 1000)
                        if st.form_submit_button("Ekle"):
                            if ad:
                                conn.execute("INSERT INTO sonuclar (isim, elo, turnuva_id) VALUES (?, ?, ?)", (ad, elo, t_id))
                                conn.commit(); guncelle_pairing_no(t_id); st.rerun()
                with c2:
                    st.write("### 📋 Oyuncu Listesi")
                    df_l = pd.read_sql(f"SELECT id, pairing_no, isim, elo FROM sonuclar WHERE turnuva_id={t_id} ORDER BY pairing_no ASC", conn)
                    for r in df_l.itertuples():
                        col1, col2, col3, col4 = st.columns([0.5, 3, 1.5, 2])
                        col1.write(r.pairing_no)
                        new_n = col2.text_input("İsim", value=r.isim, key=f"n_{r.id}", label_visibility="collapsed")
                        new_e = col3.number_input("ELO", value=r.elo, key=f"e_{r.id}", label_visibility="collapsed")
                        cb1, cb2 = col4.columns(2)
                        if cb1.button("💾", key=f"s_{r.id}"):
                            conn.execute("UPDATE sonuclar SET isim=?, elo=? WHERE id=?", (new_n, new_e, r.id))
                            conn.commit(); guncelle_pairing_no(t_id); st.rerun()
                        if cb2.button("🗑️", key=f"d_{r.id}"):
                            conn.execute("DELETE FROM sonuclar WHERE id=?", (r.id,))
                            conn.commit(); guncelle_pairing_no(t_id); st.rerun()

            with tab2:
                # EŞLENDİRME MANTIĞI (Madde 9.4)
                mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
                if not mevcut_m:
                    if st.button("🎲 Eşlendirmeyi Yap"):
                        players = pd.read_sql(f"SELECT isim FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, pairing_no ASC", conn)['isim'].tolist()
                        if len(players) >= 2:
                            if len(players) % 2 != 0:
                                bye = players.pop()
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, 'BYE', '1-0')", (t_id, t_mevcut, bye))
                                conn.execute(f"UPDATE sonuclar SET puan=puan+1, bye_aldimi=1 WHERE isim='{bye}' AND turnuva_id={t_id}")
                            yari = len(players) // 2
                            ust, alt = players[:yari], players[yari:]
                            for i in range(yari):
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, 'Bekliyor')", (t_id, t_mevcut, ust[i], alt[i]))
                            conn.commit(); st.rerun()
                else:
                    with st.form("sonuc_g"):
                        maç_list = []
                        for i, (b, s, res) in enumerate(mevcut_m, 1):
                            if s == "BYE": st.info(f"✅ Masa {i}: {b} (BYE)")
                            else:
                                st.write(f"Masa {i}: {b} - {s}")
                                r_val = st.selectbox("Sonuç", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"r_{t_mevcut}_{i}")
                                maç_list.append((b, s, r_val))
                        if st.form_submit_button("Turu Onayla"):
                            for b, s, r in maç_list:
                                if r != "Bekliyor":
                                    p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                    conn.execute("UPDATE sonuclar SET puan=puan+? WHERE isim=? AND turnuva_id=?", (p1, b, t_id))
                                    conn.execute("UPDATE sonuclar SET puan=puan+? WHERE isim=? AND turnuva_id=?", (1.0-p1, s, t_id))
                                    conn.execute(f"UPDATE eslesmeler SET sonuc='{r}' WHERE beyaz='{b}' AND turnuva_id={t_id} AND tur_no={t_mevcut}")
                            if t_mevcut < t_toplam:
                                conn.execute(f"UPDATE turnuva_ayar SET mevcut_tur={t_mevcut+1} WHERE id={t_id}")
                            else:
                                conn.execute(f"UPDATE turnuva_ayar SET durum='Bitti' WHERE id={t_id}")
                            conn.commit(); st.rerun()

            with tab3:
                df_rank = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
                st.table(df_rank)

# --- ARŞİV VE GEÇMİŞ (Geri Geldi ve Geliştirildi) ---
elif menu == "📜 Arşiv ve Geçmiş":
    st.header("📚 Geçmiş Turnuvalar")
    arsiv_df = pd.read_sql("SELECT id, ad FROM turnuva_ayar WHERE durum='Arşiv' OR durum='Bitti' ORDER BY id DESC", conn)
    
    if not arsiv_df.empty:
        secilen_ad = st.selectbox("İncelemek İstediğiniz Turnuvayı Seçin", arsiv_df['ad'].tolist())
        s_id = arsiv_df[arsiv_df['ad'] == secilen_ad]['id'].values[0]
        
        ars_tab1, ars_tab2 = st.tabs(["📊 Final Sıralaması", "📜 Tur Sonuçları"])
        
        with ars_tab1:
            res_df = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={s_id} ORDER BY Puan DESC, ELO DESC", conn)
            st.table(res_df)
            
        with ars_tab2:
            tur_list = pd.read_sql(f"SELECT DISTINCT tur_no FROM eslesmeler WHERE turnuva_id={s_id} ORDER BY tur_no ASC", conn)
            for t_no in tur_list['tur_no']:
                st.write(f"#### Tur {t_no}")
                m_df = pd.read_sql(f"SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id={s_id} AND tur_no={t_no}", conn)
                st.table(m_df)
    else:
        st.info("Henüz arşivlenmiş bir turnuva bulunmuyor.")