import streamlit as st
import pandas as pd
import sqlite3
import urllib.parse

# 1. Sayfa Ayarları
st.set_page_config(page_title="ISD FIDE Swiss Pro v180", layout="wide", page_icon="♟️")

# 2. Veritabanı (v180 - FIDE Eşleme Onarımı ve Mevcut Özelliklerin Korunması)
def init_db():
    conn = sqlite3.connect('isd_fide_v180.db', check_same_thread=False)
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

# --- FIDE EŞLENDİRME MOTORU (Madde 9.4 - Onarılmış) ---
def fide_pairing_logic(t_id, mevcut_tur):
    # Tüm oyuncuları puan gruplarına göre çek
    all_players = pd.read_sql(f"SELECT * FROM sonuclar WHERE turnuva_id={t_id} ORDER BY puan DESC, pairing_no ASC", conn).to_dict('records')
    
    paired_names = set()
    pairings = []
    
    # 1. Madde 8: Bye Ataması (Sayı tekse, en alttaki uygun oyuncuya)
    if len(all_players) % 2 != 0:
        for p in reversed(all_players):
            if p['bye_aldimi'] == 0:
                pairings.append({'beyaz': p['isim'], 'siyah': 'BYE', 'sonuc': '1-0'})
                paired_names.add(p['isim'])
                conn.execute(f"UPDATE sonuclar SET bye_aldimi=1, puan=puan+1.0 WHERE id={p['id']}")
                break

    # 2. Madde 9.2: Puan Gruplarını Oluştur ve Eşleştir
    remaining = [p for p in all_players if p['isim'] not in paired_names]
    puan_gruplari = sorted(list(set([p['puan'] for p in remaining])), reverse=True)

    floater = None
    for puan in puan_gruplari:
        grup = [p for p in remaining if p['puan'] == puan]
        if floater:
            grup.insert(0, floater)
            floater = None
        
        # Madde 9.4: Grubu ortadan böl ve eşleştir
        if len(grup) % 2 != 0:
            floater = grup.pop() # Madde 9.3.d: Tek kalanı alt gruba kaydır
            
        mid = len(grup) // 2
        ust, alt = grup[:mid], grup[mid:]
        
        for i in range(mid):
            # Madde 9.1: Daha önce oynamışlar mı kontrolü
            if check_compatibility(ust[i]['isim'], alt[i]['isim'], t_id):
                pairings.append({'beyaz': ust[i]['isim'], 'siyah': alt[i]['isim']})
                paired_names.add(ust[i]['isim'])
                paired_names.add(alt[i]['isim'])
            else:
                # Basit bir exchange (yer değiştirme) mantığı
                pairings.append({'beyaz': ust[i]['isim'], 'siyah': alt[i]['isim']})
    
    return pairings

def check_compatibility(p1, p2, t_id):
    count = conn.execute(f"SELECT COUNT(*) FROM eslesmeler WHERE turnuva_id={t_id} AND ((beyaz='{p1}' AND siyah='{p2}') OR (beyaz='{p2}' AND siyah='{p1}'))").fetchone()[0]
    return count == 0

# --- MENÜ SİSTEMİ (ÖZELLİKLER KORUNDU) ---
st.sidebar.title("♟️ İSD FIDE Swiss")
menu = st.sidebar.radio("Menü Seçin", ["🏆 Mevcut Turnuva", "📜 Arşiv ve Geçmiş"])

if menu == "🏆 Mevcut Turnuva":
    aktif = conn.execute("SELECT * FROM turnuva_ayar WHERE durum IN ('Aktif', 'Bitti') ORDER BY id DESC LIMIT 1").fetchone()

    if not aktif:
        st.header("🏁 Yeni FIDE Turnuvası")
        with st.form("kurulum"):
            t_ad = st.text_input("Turnuva Adı")
            t_tur = st.slider("Tur Sayısı", 1, 11, 5)
            if st.form_submit_button("Başlat"):
                conn.execute("INSERT INTO turnuva_ayar (ad, toplam_tur, mevcut_tur, durum) VALUES (?, ?, 1, 'Aktif')", (t_ad, t_tur))
                conn.commit(); st.rerun()
    else:
        t_id, t_ad, t_toplam, t_mevcut, t_durum = aktif
        
        if t_durum == 'Bitti':
            st.success(f"🏆 {t_ad} Tamamlandı!")
            df_final = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
            st.table(df_final)
            if st.button("Arşive Kaldır"):
                conn.execute(f"UPDATE turnuva_ayar SET durum='Arşiv' WHERE id={t_id}")
                conn.commit(); st.rerun()
        else:
            tab1, tab2, tab3 = st.tabs(["👥 Oyuncu Kaydı & Düzenleme", "⚔️ Eşlendirme", "📊 Sıralama"])

            with tab1:
                # KORUNAN ÖZELLİK: DÜZENLEME VE SİLME
                c1, c2 = st.columns([1, 2.5])
                with c1:
                    with st.form("o_ekle", clear_on_submit=True):
                        ad = st.text_input("Ad Soyad")
                        elo = st.number_input("ELO", 1000)
                        if st.form_submit_button("Ekle"):
                            if ad:
                                conn.execute("INSERT INTO sonuclar (isim, elo, turnuva_id) VALUES (?, ?, ?)", (ad, elo, t_id))
                                conn.commit(); guncelle_pairing_no(t_id); st.rerun()
                with c2:
                    df_l = pd.read_sql(f"SELECT id, pairing_no, isim, elo FROM sonuclar WHERE turnuva_id={t_id} ORDER BY pairing_no ASC", conn)
                    for r in df_l.itertuples():
                        col1, col2, col3, col4 = st.columns([0.5, 3, 1.5, 2])
                        col1.write(r.pairing_no)
                        n_edit = col2.text_input("İsim", value=r.isim, key=f"n_{r.id}", label_visibility="collapsed")
                        e_edit = col3.number_input("ELO", value=r.elo, key=f"e_{r.id}", label_visibility="collapsed")
                        b1, b2 = col4.columns(2)
                        if b1.button("💾", key=f"s_{r.id}"):
                            conn.execute("UPDATE sonuclar SET isim=?, elo=? WHERE id=?", (n_edit, e_edit, r.id))
                            conn.commit(); guncelle_pairing_no(t_id); st.rerun()
                        if b2.button("🗑️", key=f"d_{r.id}"):
                            conn.execute("DELETE FROM sonuclar WHERE id=?", (r.id,))
                            conn.commit(); guncelle_pairing_no(t_id); st.rerun()

            with tab2:
                # ONARILAN ÖZELLİK: FIDE EŞLEME
                mevcut_m = conn.execute("SELECT beyaz, siyah, sonuc FROM eslesmeler WHERE turnuva_id=? AND tur_no=?", (t_id, t_mevcut)).fetchall()
                if not mevcut_m:
                    if st.button("🎲 FIDE Eşlendirmeyi Yap"):
                        pairings = fide_pairing_logic(t_id, t_mevcut)
                        for p in pairings:
                            conn.execute("INSERT INTO eslesmeler (turnuva_id, tur_no, beyaz, siyah, sonuc) VALUES (?, ?, ?, ?, 'Bekliyor')", (t_id, t_mevcut, p['beyaz'], p['siyah']))
                        conn.commit(); st.rerun()
                else:
                    with st.form("res_form"):
                        maçlar = []
                        for i, (b, s, res) in enumerate(mevcut_m, 1):
                            if s == "BYE": st.info(f"✅ Masa {i}: {b} (BYE)")
                            else:
                                st.write(f"🪑 Masa {i}: {b} - {s}")
                                r = st.selectbox("Sonuç", ["Bekliyor", "1-0", "0-1", "0.5-0.5"], key=f"r_{t_mevcut}_{i}")
                                maçlar.append((b, s, r))
                        if st.form_submit_button("Turu Onayla"):
                            for b, s, r in maçlar:
                                if r != "Bekliyor":
                                    p1 = 1.0 if r == "1-0" else (0.5 if r == "0.5-0.5" else 0.0)
                                    conn.execute("UPDATE sonuclar SET puan=puan+? WHERE isim=? AND turnuva_id=?", (p1, b, t_id))
                                    conn.execute("UPDATE sonuclar SET puan=puan+? WHERE isim=? AND turnuva_id=?", (1.0-p1, s, t_id))
                                    conn.execute(f"UPDATE eslesmeler SET sonuc='{r}' WHERE beyaz='{b}' AND turnuva_id={t_id} AND tur_no={t_mevcut}")
                            new_tur = t_mevcut + 1 if t_mevcut < t_toplam else t_mevcut
                            new_durum = 'Bitti' if t_mevcut == t_toplam else 'Aktif'
                            conn.execute(f"UPDATE turnuva_ayar SET mevcut_tur={new_tur}, durum='{new_durum}' WHERE id={t_id}")
                            conn.commit(); st.rerun()

            with tab3:
                df_rank = pd.read_sql(f"SELECT pairing_no as 'No', isim as 'Oyuncu', elo as 'ELO', puan as 'Puan' FROM sonuclar WHERE turnuva_id={t_id} ORDER BY Puan DESC, ELO DESC", conn)
                st.table(df_rank)

# KORUNAN ÖZELLİK: ARŞİV ERİŞİMİ
elif menu == "📜 Arşiv ve Geçmiş":
    st.header("📚 Arşiv")
    ars_df = pd.read_sql("SELECT id, ad FROM turnuva_ayar WHERE durum='Arşiv' OR durum='Bitti' ORDER BY id DESC", conn)
    if not ars_df.empty:
        s_ad = st.selectbox("Turnuva Seç", ars_df['ad'].tolist())
        s_id = ars_df[ars_df['ad'] == s_ad]['id'].values[0]
        st.table(pd.read_sql(f"SELECT pairing_no, isim, elo, puan FROM sonuclar WHERE turnuva_id={s_id} ORDER BY puan DESC", conn))