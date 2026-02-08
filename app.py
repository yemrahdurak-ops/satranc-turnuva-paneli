import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="İSD Turnuva Paneli", layout="wide", page_icon="♟️")

# 2. Veritabanı (İsim çakışmaması için v30 yapıyoruz)
def init_db():
    conn = sqlite3.connect('isd_final_v30.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS turnuva_ayar 
                    (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sonuclar 
                    (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL, turnuva_id INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS eslesmeler 
                    (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# Menü
st.sidebar.title("♟️ İSD Yönetim")
menu = st.sidebar.radio("Menü Seçin", ["🏆 Mevcut Turnuva", "📜 Turnuva Arşivi"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum='Aktif'").fetchone()

    if not aktif:
        st.header("🏁 Yeni Turnuva Başlat")
        with st.form("kurulum_formu"):
            t_ad = st.text_input("Turnuva Adı")
            t_tur = st.slider("Toplam Tur Sayısı", 1, 11, 5)
            if st.form_submit_button("Turnuvayı Oluştur"):
                if t_ad:
                    conn.execute("INSERT INTO turnuva_ayar (ad, toplam_tur, mevcut_tur, durum) VALUES (?, ?, 1, 'Aktif')", (t_ad, t_tur))
                    conn.commit()
                    st.rerun()
    else:
        t_id, t_ad, t_toplam, t_mevcut, t_durum = aktif
        st.subheader(f"📍 Aktif: {t_ad} ({t_mevcut}. Tur)")

        tab1, tab2, tab3 = st.tabs(["👥 Kayıt & Yönetim", "⚔️ Eşlendirme", "📊 Güncel Sıralama"])

        with tab1:
            col_sol, col_sag = st.columns([1, 2])
            
            with col_sol:
                st.write("### ➕ Oyuncu Ekle")
                # Hata veren manuel sıfırlama yerine clear_on_submit kullanıyoruz
                with st.form("oyuncu_kayit_formu", clear_on_submit=True):
                    y_isim = st.text_input("Ad Soyad")
                    y_elo = st.number_input("ELO", value=1000)
                    kaydet_butonu = st.form_submit_button("Listeye Ekle")
                    
                    if kaydet_butonu:
                        if y_isim:
                            conn.execute("INSERT INTO sonuclar (isim, elo, puan, turnuva_id) VALUES (?, ?, 0.0, ?)", (y_isim, y_elo, t_id))
                            conn.commit()
                            st.toast(f"✅ {y_isim} eklendi!")
                            # Form dışındaki listeyi güncellemek için rerun yapıyoruz
                            st.rerun()
                        else:
                            st.error("İsim boş bırakılamaz!")

            with col_sag:
                st.write("### 📋 Oyuncu Listesi")
                df_oy = pd.read_sql(f"SELECT id, isim, elo FROM sonuclar WHERE turnuva_id={t_id}", conn)
                if not df_oy.empty:
                    for i, r in enumerate(df_oy.itertuples(), 1):
                        c1, c2, c3, c4 = st.columns([0.5, 3, 2, 2])
                        c1.write(f"**{i}**")
                        # Düzenleme kısımları form dışında kalmalı ki anlık güncellensin
                        new_n = c2.text_input("İsim", value=r.isim, key=f"n_{r.id}", label_visibility="collapsed")
                        new_e = c3.number_input("ELO", value=r.elo, key=f"e_{r.id}", label_visibility="collapsed")
                        cb1, cb2 = c4.columns(2)
                        if cb1.button("💾", key=f"s_{r.id}"):
                            conn.execute("UPDATE sonuclar SET isim=?, elo=? WHERE id=?", (new_n, new_e, r.id))
                            conn.commit()
                            st.rerun()
                        if cb2.button("🗑️", key=f"d_{r.id}"):
                            conn.execute("DELETE FROM sonuclar WHERE id=?", (r.id,))
                            conn.commit()
                            st.rerun()

        # --- EŞLENDİRME TABI ---
        with tab2:
            st.write(f"### Tur {t_mevcut} Maçları")
            mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
            
            if not mevcut_m:
                if st.button("🎲 Eşlendirmeyi Şimdi Yap"):
                    df_p = pd.read_sql(f"SELECT isim FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, elo DESC", conn)
                    liste = df_p['isim'].tolist()
                    if len(liste) >= 2:
                        if len(liste) % 2 != 0:
                            bye = liste.pop()
                            conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, ?)", (t_id, t_mevcut, bye, "BAY", "1-0"))
                        yari = len(liste) // 2
                        ust, alt = liste[:yari], liste[yari:]
                        for i in range(yari):
                            conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, ?)", (t_id, t_mevcut, ust[i], alt[i], "Bekliyor"))
                        conn.commit()
                        st.rerun()
            else:
                with st.form("sonuc_g"):
                    maçlar = []
                    for b, s, res in mevcut_m:
                        if s == "BAY": st.info(f"✅ {b} BAY geçti.")
                        else:
                            ca, cb = st.columns([3, 2])
                            ca.write(f"**{b}** vs **{s}**")
                            skor = cb.selectbox("Sonuç", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"m_{b}_{s}")
                            maçlar.append((b, s, skor))
                    
                    if st.form_submit_button("Turu Onayla"):
                        for b, s, r in maçlar:
                            if r != "Bekliyor":
                                p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                conn.execute("UPDATE sonuclar SET puan = puan + ? WHERE isim = ? AND turnuva_id = ?", (p1, b, t_id))
                                conn.execute("UPDATE sonuclar SET puan = puan + ? WHERE isim = ? AND turnuva_id = ?", (1.0-p1, s, t_id))
                                conn.execute("UPDATE eslesmeler SET sonuc=? WHERE turnuva_id=? AND tur_no=? AND beyaz=?", (r, t_id, t_mevcut, b))
                        
                        if t_mevcut < t_toplam:
                            conn.execute("UPDATE turnuva_ayar SET mevcut_tur = ? WHERE id = ?", (t_mevcut + 1, t_id))
                        else:
                            conn.execute("UPDATE turnuva_ayar SET durum = 'Tamamlandı' WHERE id = ?", (t_id,))
                        conn.commit()
                        st.rerun()

                # WhatsApp Paylaş
                es_msj = f"⚔️ *{t_ad} - Tur {t_mevcut} Eşleşmeleri*\n\n"
                for i, (b, s, r) in enumerate(mevcut_m, 1):
                    es_msj += f"🔹 Masa {i}: {b} - {s}\n" if s != "BAY" else f"🔸 BAY: {b}\n"
                st.link_button("📲 WhatsApp'ta Paylaş", f"https://wa.me/?text={urllib.parse.quote(es_msj)}")

        # --- SIRALAMA TABI ---
        with tab3:
            df_rank = pd.read_sql(f"SELECT isim as Oyuncu, elo as ELO, puan as Puan FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            df_rank.index = range(1, len(df_rank) + 1)
            df_rank['Puan'] = df_rank['Puan'].map('{:,.1f}'.format)
            st.table(df_rank)
            
            sir_msj = f"🏆 *{t_ad} - Güncel Sıralama*\n\n"
            for i, r in df_rank.iterrows():
                sir_msj += f"{i}. {r['Oyuncu']} ({r['Puan']} Pn)\n"
            st.link_button("📲 Sıralamayı WhatsApp'ta Paylaş", f"https://wa.me/?text={urllib.parse.quote(sir_msj)}")

# --- ARŞİV ---
elif menu == "📜 Turnuva Arşivi":
    st.header("📚 Arşiv")
    arsiv_df = pd.read_sql("SELECT id, ad FROM turnuva_ayar WHERE durum='Tamamlandı'", conn)
    if not arsiv_df.empty:
        secilen = st.selectbox("Seç", arsiv_df['ad'].tolist())
        s_id = arsiv_df[arsiv_df['ad'] == secilen]['id'].values[0]
        f_df = pd.read_sql(f"SELECT isim as Oyuncu, puan as Puan FROM sonuclar WHERE turnuva_id={s_id} ORDER BY Puan DESC", conn)
        f_df.index = range(1, len(f_df) + 1)
        st.table(f_df)