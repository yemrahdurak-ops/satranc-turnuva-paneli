import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="ISD Turnuva Paneli", layout="wide", page_icon="♟️")

# 2. Veritabanı (v80 - Bitiş Ekranı Güncellemesi)
def init_db():
    conn = sqlite3.connect('isd_final_v80.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS turnuva_ayar (id INTEGER PRIMARY KEY, ad TEXT, toplam_tur INTEGER, mevcut_tur INTEGER, durum TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS sonuclar (id INTEGER PRIMARY KEY, isim TEXT, elo INTEGER, puan REAL, turnuva_id INTEGER)')
    conn.execute('CREATE TABLE IF NOT EXISTS eslesmeler (id INTEGER PRIMARY KEY, turnuva_id INTEGER, tur_no INTEGER, beyaz TEXT, siyah TEXT, sonuc TEXT)')
    conn.commit()
    return conn

conn = init_db()

st.sidebar.title("İSD Yönetim")
menu = st.sidebar.radio("Menü Seçin", ["🏆 Mevcut Turnuva", "📜 Arşiv"])

if menu == "🏆 Mevcut Turnuva":
    # Aktif VEYA Yeni Bitmiş turnuvayı çekiyoruz
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum='Aktif' OR durum='Bitti' ORDER BY id DESC LIMIT 1").fetchone()

    if not aktif:
        st.header("🏁 Yeni Turnuva Başlat")
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
            st.balloons() # Tebrik efekti
            st.success(f"🏆 {t_ad} Tamamlandı! İşte Final Sıralaması:")
            
            # FİNAL SIRALAMASI (Kayıbolmayan Tablo)
            df_final = pd.read_sql(f"SELECT isim as Oyuncu, elo as ELO, puan as Puan FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            df_final.index = range(1, len(df_final) + 1)
            df_final['Puan'] = df_final['Puan'].map('{:,.1f}'.format)
            st.table(df_final)
            
            if st.button("Yeni Turnuva Hazırlığına Geç"):
                conn.execute("UPDATE turnuva_ayar SET durum='Arşivlendi' WHERE id=?", (t_id,))
                conn.commit(); st.rerun()
        else:
            st.subheader(f"📍 {t_ad} - Tur {t_mevcut}")
            tab1, tab2, tab3 = st.tabs(["👥 Kayıt & Yönetim", "⚔️ Eşlendirme", "📊 Güncel Sıralama"])

            with tab1:
                col_sol, col_sag = st.columns([1, 2.5])
                with col_sol:
                    st.write("### ➕ Oyuncu Ekle")
                    with st.form("kayit_formu", clear_on_submit=True):
                        y_isim = st.text_input("Ad Soyad")
                        y_elo = st.number_input("ELO", value=1000)
                        if st.form_submit_button("Ekle"):
                            if y_isim:
                                conn.execute("INSERT INTO sonuclar (isim, elo, puan, turnuva_id) VALUES (?, ?, 0.0, ?)", (y_isim, y_elo, t_id))
                                conn.commit(); st.rerun()
                with col_sag:
                    df_oy = pd.read_sql(f"SELECT id, isim, elo FROM sonuclar WHERE turnuva_id={t_id}", conn)
                    if not df_oy.empty:
                        for i, r in enumerate(df_oy.itertuples(), 1):
                            c1, c2, c3, c4 = st.columns([0.5, 3, 1.5, 2])
                            c1.write(f"**{i}**")
                            new_n = c2.text_input("İsim", value=r.isim, key=f"n_{r.id}", label_visibility="collapsed")
                            new_e = c3.number_input("ELO", value=r.elo, key=f"e_{r.id}", label_visibility="collapsed")
                            cb1, cb2 = c4.columns(2)
                            if cb1.button("💾", key=f"s_{r.id}"):
                                conn.execute("UPDATE sonuclar SET isim=?, elo=? WHERE id=?", (new_n, new_e, r.id))
                                conn.commit(); st.rerun()
                            if cb2.button("🗑️", key=f"d_{r.id}"):
                                conn.execute("DELETE FROM sonuclar WHERE id=?", (r.id,))
                                conn.commit(); st.rerun()

            with tab2:
                st.write(f"### Tur {t_mevcut} Maçları")
                mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
                if not mevcut_m:
                    if st.button("🎲 Eşlendirmeyi Yap"):
                        df_p = pd.read_sql(f"SELECT isim FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, elo DESC", conn)
                        liste = df_p['isim'].tolist()
                        if len(liste) >= 2:
                            if len(liste) % 2 != 0:
                                bye = list.pop() if 'list' in locals() else liste.pop()
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, ?)", (t_id, t_mevcut, bye, "BAY", "1-0"))
                            yari = len(liste) // 2
                            ust, alt = liste[:yari], liste[yari:]
                            for i in range(yari):
                                conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, ?)", (t_id, t_mevcut, ust[i], alt[i], "Bekliyor"))
                            conn.commit(); st.rerun()
                else:
                    wa_text = f"*{t_ad} - Tur {t_mevcut} Eşleşmeleri*\n\n"
                    with st.form("sonuclar"):
                        maç_listesi = []
                        for i, (b, s, res) in enumerate(mevcut_m, 1):
                            if s == "BAY":
                                st.info(f"✅ **BAY:** {b}")
                                wa_text += f"🔸 *BAY:* {b}\n"
                            else:
                                st.write(f"🪑 **Masa {i}:** {b} - {s}")
                                wa_text += f"🪑 *Masa {i}:* {b} - {s}\n"
                                skor = st.selectbox("Sonuç", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"m_{t_id}_{t_mevcut}_{i}")
                                maç_listesi.append((b, s, skor))
                        if st.form_submit_button("Sonuçları Onayla"):
                            for b, s, r in maç_listesi:
                                if r != "Bekliyor":
                                    p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                    conn.execute("UPDATE sonuclar SET puan = puan + ? WHERE isim = ? AND turnuva_id = ?", (p1, b, t_id))
                                    conn.execute("UPDATE sonuclar SET puan = puan + ? WHERE isim = ? AND turnuva_id = ?", (1.0-p1, s, t_id))
                                    conn.execute("UPDATE eslesmeler SET sonuc=? WHERE beyaz=? AND turnuva_id=? AND tur_no=?", (r, b, t_id, t_mevcut))
                            if t_mevcut < t_toplam:
                                conn.execute("UPDATE turnuva_ayar SET mevcut_tur = ? WHERE id = ?", (t_mevcut + 1, t_id))
                            else:
                                conn.execute("UPDATE turnuva_ayar SET durum = 'Bitti' WHERE id = ?", (t_id,))
                            conn.commit(); st.rerun()
                    st.link_button("📲 WhatsApp'ta Paylaş", f"https://wa.me/?text={urllib.parse.quote(wa_text)}")

            with tab3:
                df_s = pd.read_sql(f"SELECT isim as Oyuncu, elo as ELO, puan as Puan FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
                df_s.index = range(1, len(df_s) + 1)
                df_s['Puan'] = df_s['Puan'].map('{:,.1f}'.format)
                st.table(df_s)

elif menu == "📜 Arşiv":
    st.header("📚 Turnuva Arşivi")
    arsiv_df = pd.read_sql("SELECT id, ad FROM turnuva_ayar WHERE durum='Bitti' OR durum='Arşivlendi' ORDER BY id DESC", conn)
    if not arsiv_df.empty:
        secilen_turnuva = st.selectbox("Geçmiş Turnuva Seçin", arsiv_df['ad'].tolist())
        s_id = arsiv_df[arsiv_df['ad'] == secilen_turnuva]['id'].values[0]
        f_res = pd.read_sql(f"SELECT isim as Oyuncu, elo as ELO, puan as Puan FROM sonuclar WHERE turnuva_id={s_id} ORDER BY Puan DESC", conn)
        f_res.index = range(1, len(f_res) + 1)
        f_res['Puan'] = f_res['Puan'].map('{:,.1f}'.format)
        st.table(f_res)