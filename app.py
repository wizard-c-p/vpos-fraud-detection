import streamlit as st
import pandas as pd
import numpy as np

# Sayfa Ayarları
st.set_page_config(page_title="Dynamic MCC Risk Manager", layout="wide")
st.title("🛡️ Dinamik MCC Risk Yönetim Paneli")

# --- 1. SESSION STATE (HAFIZA) BAŞLATMA ---
if 'active_mccs' not in st.session_state:
    st.session_state['active_mccs'] = ['5411', '5812', '5094', '7995']

# --- 2. SOL MENÜ: PARAMETRE AYARLARI ---
st.sidebar.header("⚙️ Kural ve Limit Yönetimi")

# A. GENEL AYARLAR
with st.sidebar.expander("🌍 Genel Sistem Ayarları", expanded=False):
    param_avg_ticket_variance = st.slider("Genel Sepet Sapma Limiti (%)", 20, 200, 50)
    param_ip_conc = st.slider("Bot IP Yoğunluk Limiti (%)", 50, 100, 80)
    param_min_txn = st.number_input("Minimum İşlem Adedi", 10, 100, 10)

st.sidebar.divider()

# B. DİNAMİK MCC YÖNETİMİ
st.sidebar.subheader("🏭 MCC Bazlı Limitler")
thresholds = {} 
mcc_avg_tickets = {} 
mccs_to_remove = []

for mcc in st.session_state['active_mccs']:
    with st.sidebar.expander(f"📍 MCC {mcc} Ayarları", expanded=False):
        mcc_avg_tickets[mcc] = st.number_input(f"Ortalama Sepet (₺)", value=450 if mcc=='5411' else (15000 if mcc=='5094' else 1000), key=f"avg_{mcc}")
        thresholds[mcc] = {}
        thresholds[mcc]['cb_ratio'] = st.number_input("Maks CB (%)", value=1.0, step=0.1, key=f"cb_{mcc}")
        thresholds[mcc]['non_3d_ratio'] = st.number_input("Maks 3D'siz (%)", value=10.0, step=5.0, key=f"3d_{mcc}")
        thresholds[mcc]['refund_ratio'] = st.number_input("Maks İade (%)", value=3.0, step=1.0, key=f"ref_{mcc}")
        thresholds[mcc]['foreign_card_ratio'] = st.number_input("Maks Y.Kart (%)", value=5.0, step=1.0, key=f"fcard_{mcc}")
        thresholds[mcc]['foreign_ip_ratio'] = st.number_input("Maks Y.IP (%)", value=5.0, step=1.0, key=f"fip_{mcc}")
        
        if st.button(f"🗑️ MCC {mcc} Sil", key=f"del_{mcc}"):
            mccs_to_remove.append(mcc)

if mccs_to_remove:
    for m in mccs_to_remove:
        st.session_state['active_mccs'].remove(m)
    st.rerun()

# C. YENİ MCC EKLEME
st.sidebar.markdown("---")
st.sidebar.write("### ➕ Yeni MCC Ekle")
col_add1, col_add2 = st.sidebar.columns([2, 1])
with col_add1:
    new_mcc_input = st.text_input("Kod Gir", label_visibility="collapsed", placeholder="MCC")
with col_add2:
    if st.button("Ekle"):
        if new_mcc_input and new_mcc_input not in st.session_state['active_mccs']:
            st.session_state['active_mccs'].append(new_mcc_input)
            st.rerun()

# --- 3. VERİ YÜKLEME VE İŞLEME ---
uploaded_file = st.file_uploader("Veri Setini Yükle (vpos_test_data_final.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    @st.cache_data
    def load_data(file):
        df = pd.read_excel(file)
        df['mcc'] = df['mcc'].astype(str) 
        return df
    
    df = load_data(uploaded_file)
    
    # Benchmark Hesaplama
    mcc_benchmarks = df.groupby('mcc').agg(
        avg_mcc_cb_ratio=('is_chargeback', lambda x: x.sum() / len(x) * 100), 
        avg_mcc_non3d_ratio=('is_3d_secure', lambda x: (1 - x).mean() * 100), 
        avg_mcc_foreign_card_ratio=('card_country', lambda x: (x != 'TR').mean() * 100), 
        avg_mcc_foreign_ip_ratio=('ip_country', lambda x: (x != 'TR').mean() * 100), 
        avg_mcc_refund_ratio=('is_refund', lambda x: x.sum() / len(x) * 100),
    ).reset_index()

    # Merchant Aggregation
    def get_top_concentration(series): return series.value_counts(normalize=True).iloc[0]
    def get_top_value(series): return series.value_counts().index[0]

    merchant_stats = df.groupby('merchant_id').agg({
        'transaction_id': 'count', 'amount': ['sum', 'mean'], 
        'is_chargeback': 'sum', 'is_refund': 'sum', 'is_3d_secure': 'mean', 
        'ip_address': [get_top_concentration, get_top_value],
        'card_country': lambda x: (x != 'TR').mean(), 
        'ip_country': lambda x: (x != 'TR').mean(), 
        'mcc': 'first',
        'device_id': [get_top_value] if 'device_id' in df.columns else lambda x: "N/A"
    }).reset_index()

    col_names = [
        'merchant_id', 'total_txn', 'total_amount', 'avg_ticket', 'total_cb', 'total_refund', 
        'avg_is_3d_secure', 'ip_conc_ratio', 'top_ip', 'foreign_card_ratio', 'foreign_ip_ratio', 'mcc'
    ]
    if 'device_id' in df.columns: col_names.append('top_device_id')
    else: col_names.append('top_device_id_dummy')

    if len(merchant_stats.columns) == len(col_names): merchant_stats.columns = col_names
    else: merchant_stats.columns = [f"col_{i}" for i in range(len(merchant_stats.columns))]

    # Oranlar
    merchant_stats['cb_ratio'] = (merchant_stats['total_cb'] / merchant_stats['total_txn']) * 100
    merchant_stats['refund_ratio'] = (merchant_stats['total_refund'] / merchant_stats['total_txn']) * 100
    merchant_stats['non_3d_ratio'] = (1 - merchant_stats['avg_is_3d_secure']) * 100
    
    # Merge Benchmark
    merchant_stats = pd.merge(merchant_stats, mcc_benchmarks, on='mcc', how='left')
    
    # Sepet Sapması
    def get_expected_avg(mcc_code): return mcc_avg_tickets.get(str(mcc_code), 0)
    merchant_stats['expected_avg'] = merchant_stats['mcc'].apply(get_expected_avg)
    merchant_stats['ticket_variance_pct'] = np.where(
        merchant_stats['expected_avg'] > 0,
        ((merchant_stats['avg_ticket'] - merchant_stats['expected_avg']) / merchant_stats['expected_avg']) * 100,
        0
    )

    # --- RİSK PUANLAMA ---
    def calculate_adaptive_risk(row, thresholds):
        score = 0
        reasons = []
        if row['total_txn'] < param_min_txn: return 0, ""
        
        mcc_code = row['mcc']
        if mcc_code in thresholds: 
             metrics_to_check = [
                ('cb_ratio', 80, "CB"), ('refund_ratio', 40, "İADE"),
                ('non_3d_ratio', 30, "3DSİZ"), ('foreign_card_ratio', 20, "Y.KART"),
                ('foreign_ip_ratio', 20, "Y.IP"),
             ]
             for indiv_col, points, name in metrics_to_check:
                static_threshold = thresholds[mcc_code].get(indiv_col, 0)
                if static_threshold > 0 and row[indiv_col] > static_threshold:
                    score += points
                    reasons.append(f"LİMİT AŞIMI ({name})") 

        if row['ticket_variance_pct'] > param_avg_ticket_variance:
            score += 45; reasons.append(f"SEPET SAPMASI")
        if row['ip_conc_ratio'] > (param_ip_conc / 100.0):
            score += 50; reasons.append(f"BOT ({param_ip_conc}%+) ")

        return score, " | ".join(reasons)
    
    results = merchant_stats.apply(lambda row: calculate_adaptive_risk(row, thresholds), axis=1)
    merchant_stats['risk_score'] = [x[0] for x in results]
    merchant_stats['risk_reasons'] = [x[1] for x in results]

    # --- DASHBOARD ---
    riskli_merchantlar = merchant_stats[merchant_stats['risk_score'] > 0].sort_values('risk_score', ascending=False)
    
    # 1. YÖNETİCİ ÖZETİ
    st.markdown("---")
    st.subheader("📊 Yönetici Özeti")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam İşyeri", len(merchant_stats))
    c2.metric("Riskli İşyeri", len(riskli_merchantlar), delta_color="inverse")
    c3.metric("Tanımlı MCC", len(st.session_state['active_mccs']))
    c4.metric("Kritik CB", riskli_merchantlar['risk_reasons'].str.contains("CB").sum() if not riskli_merchantlar.empty else 0, delta_color="inverse")
    
    # 2. TABLO VE SEÇİM (DROPDOWN MODU)
    st.markdown("---")
    st.subheader(f"🚨 Riskli İşyeri Listesi")
    
    selected_merchant_id = None
    
    if len(riskli_merchantlar) > 0:
        display_cols = [
            'merchant_id', 'mcc', 'risk_score', 'total_txn', 
            'cb_ratio', 'avg_mcc_cb_ratio', 
            'refund_ratio', 'avg_mcc_refund_ratio', 
            'non_3d_ratio', 'avg_mcc_non3d_ratio', 
            'foreign_card_ratio', 'foreign_ip_ratio',
            'ip_conc_ratio', 'risk_reasons'
        ]
        
        # TABLOYU NORMAL GÖSTER (Tıklama Özelliği Yok - Eski Sürüm Uyumlu)
        st.dataframe(
            riskli_merchantlar[display_cols].style.format({
                'cb_ratio': "CB İ:{:.2f}%", 'refund_ratio': "İade İ:{:.2f}%", 'non_3d_ratio': "3D İ:{:.1f}%",
                'foreign_card_ratio': "YK İ:{:.1f}%", 'foreign_ip_ratio': "YIP İ:{:.1f}%", 'ip_conc_ratio': "IP Yoğ:{:.0%}",
                'avg_mcc_cb_ratio': "S:{:.2f}%", 'avg_mcc_refund_ratio': "S:{:.2f}%", 'avg_mcc_non3d_ratio': "S:{:.1f}%",
            }).background_gradient(cmap='Reds', subset=['risk_score']),
            use_container_width=True
        )

        st.info("👇 Detaylı inceleme için aşağıdaki kutudan seçim yapınız (Performans için sadece en riskli ilk 50 işyeri listelenir).")
        
        # Dropdown donmaması için sadece ilk 50 riskli işyeri
        top_risky_list = riskli_merchantlar['merchant_id'].head(50).tolist()
        
        selected_merchant_id = st.selectbox(
            "İncelemek için İşyeri Seçiniz:", 
            options=top_risky_list
        )

    else:
        st.success("Riskli işyeri bulunamadı.")

    # 3. DRILL-DOWN (SEÇİME GÖRE)
    if selected_merchant_id:
        st.markdown("---")
        st.subheader(f"🕵️ Detaylı İnceleme: {selected_merchant_id}")
        
        merc_data = df[df['merchant_id'] == selected_merchant_id]
        
        co1, co2, co3 = st.columns(3)
        with co1:
            st.write("**Top 10 IP**")
            ip_s = merc_data['ip_address'].value_counts().head(10).reset_index()
            ip_s.columns = ['IP', 'Adet']
            st.dataframe(ip_s.style.background_gradient(cmap='Blues'), use_container_width=True)
        with co2:
            st.write("**Top 10 Cihaz**")
            if 'device_id' in merc_data.columns:
                dev_s = merc_data['device_id'].value_counts().head(10).reset_index()
                dev_s.columns = ['Device', 'Adet']
                st.dataframe(dev_s.style.background_gradient(cmap='Purples'), use_container_width=True)
        with co3:
            st.write("**Kart Ülke Dağılımı**")
            cnt_s = merc_data['card_country'].value_counts().reset_index()
            cnt_s.columns = ['Ülke', 'Adet']
            st.dataframe(cnt_s.style.background_gradient(cmap='Oranges'), use_container_width=True)
            
        st.info(f"📌 **Özet:** Toplam {len(merc_data)} işlem | Hacim: {merc_data['amount'].sum():,.2f} ₺ | Chargeback: {merc_data['is_chargeback'].sum()} adet")

else:
    st.warning("Lütfen veri seti yükleyin.")