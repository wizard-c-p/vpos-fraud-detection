import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Adaptive AML Peer Benchmarking", layout="wide")
st.title("🛡️ MCC Bazlı Uyarlanabilir AML Risk Yönetimi")
st.markdown("İşyerleri, kendi sektörlerindeki (aynı MCC) diğer işyerlerine göre sapma miktarına göre puanlanır.")

# --- 1. SOL MENÜ: PARAMETRE AYARLARI ---
st.sidebar.header("⚙️ Risk Kural Seti Ayarları")
st.sidebar.subheader("5. Endüstri Sapma Kontrolü")

param_variance_multiplier = st.sidebar.slider(
    "MCC Ortalama Sapma Çarpanı (X)", 
    min_value=1.0, max_value=5.0, value=2.0, step=0.1,
    help="İşyeri oranının, sektör ortalamasının kaç katını (X) aşarsa risk puanı alsın? (Örn: 2.0 = 2 katı)"
)

# MCC Ortalama Tutar Girişi (Eski özellik korundu)
mcc_definitions = {}
mcc_definitions['5411'] = st.sidebar.number_input("5411 (Market) Ortalama ₺", value=450, step=50)
mcc_definitions['7995'] = st.sidebar.number_input("7995 (Kumar) Ortalama ₺", value=2000, step=100)
# (Diğer eski parametreler kısaltıldı)
param_ip_conc = st.sidebar.slider("IP Yoğunluk Limiti (%)", 50, 100, 80)
param_min_txn = st.sidebar.number_input("Minimum İşlem Adedi", 1, 100, 10)

# --- 2. VERİ YÜKLEME ---
uploaded_file = st.file_uploader("Veri Setini Yükle", type=["xlsx"])

if uploaded_file is not None:
    @st.cache_data
    def load_data(file):
        df = pd.read_excel(file)
        df['mcc'] = df['mcc'].astype(str) 
        
        # Simülasyon: ip_country ekle (Yurt dışı IP'si tespiti için)
        # 192 ile başlamayan IP'leri US sayıyoruz (basitlik için)
        df['ip_country'] = np.where(df['ip_address'].str.startswith('192'), 'TR', 'US')
        return df
    
    df = load_data(uploaded_file)
    
    # --- 3. MCC BAZLI SEKTÖR ORTALAMALARINI HESAPLAMA (BENCHMARKING) ---
    # Bu, tüm sektörün (peer group) ortalama risk profilidir.
    mcc_benchmarks = df.groupby('mcc').agg(
        # 1. Ortalama CB Oranı (Sektör Ortalaması)
        avg_mcc_cb_ratio=('is_chargeback', lambda x: x.sum() / len(x) * 100), 
        # 2. Ortalama Refund Oranı
        avg_mcc_refund_ratio=('is_refund', lambda x: x.sum() / len(x) * 100),
        # 3. Ortalama 3D'siz İşlem Oranı
        avg_mcc_non3d_ratio=('is_3d_secure', lambda x: (1 - x).mean() * 100), 
        # 4. Ortalama Yurt Dışı Kart Kullanım Oranı
        avg_mcc_foreign_card_ratio=('card_country', lambda x: (x != 'TR').mean() * 100), 
        # 5. Ortalama Yurt Dışı IP Oranı
        avg_mcc_foreign_ip_ratio=('ip_country', lambda x: (x != 'TR').mean() * 100),
        # Ortalama Beklenen Sepet Tutarı (MCC ortalaması)
        mcc_txns=('transaction_id', 'count')
    ).reset_index()

    # --- 4. MERCHANT BAZLI AGGREGATION (Bireysel İstatistikler) ---
    
    # Bireysel statikleri hesapla
    merchant_stats = df.groupby('merchant_id').agg({
        'transaction_id': 'count', 'amount': ['sum', 'mean'], 'is_chargeback': 'sum', 
        'is_refund': 'sum', 'is_3d_secure': 'mean', 'ip_address': lambda x: x.value_counts(normalize=True).iloc[0],
        'card_country': lambda x: (x != 'TR').mean(), 'mcc': 'first', 'ip_country': lambda x: (x != 'TR').mean()
    }).reset_index()

    merchant_stats.columns = [
        'merchant_id', 'total_txn', 'total_amount', 'avg_ticket', 'total_cb', 'total_refund', 
        'avg_is_3d_secure', 'ip_conc_ratio', 'avg_foreign_card_ratio', 'mcc', 'avg_foreign_ip_ratio'
    ]
    
    # Bireysel Oranları Hesapla (Kolay okuma için)
    merchant_stats['cb_ratio'] = (merchant_stats['total_cb'] / merchant_stats['total_txn']) * 100
    merchant_stats['refund_ratio'] = (merchant_stats['total_refund'] / merchant_stats['total_txn']) * 100
    merchant_stats['non_3d_ratio'] = (1 - merchant_stats['avg_is_3d_secure']) * 100

    # --- 5. BENCHMARK VE BİREYSEL STATİKLERİ BİRLEŞTİRME ---
    merchant_stats = pd.merge(merchant_stats, mcc_benchmarks.drop(columns=['mcc_txns']), on='mcc', how='left')

    # Sepet Sapması (Eski özellik korundu)
    def get_expected_avg(mcc_code): return mcc_definitions.get(str(mcc_code), 0)
    merchant_stats['expected_avg'] = merchant_stats['mcc'].apply(get_expected_avg)
    merchant_stats['ticket_variance_pct'] = np.where(
        merchant_stats['expected_avg'] > 0,
        ((merchant_stats['avg_ticket'] - merchant_stats['expected_avg']) / merchant_stats['expected_avg']) * 100,
        0
    )

    # --- 6. DİNAMİK RİSK PUANLAMA (PEER BENCHMARKING EKLENDİ) ---
    def calculate_adaptive_risk(row):
        score = 0
        reasons = []
        multiplier = param_variance_multiplier
        
        if row['total_txn'] < param_min_txn:
            return 0, ""

        # Kural 1: CB Oranı Sapması (YENİ PEER BENCHMARKING)
        if row['cb_ratio'] > (row['avg_mcc_cb_ratio'] * multiplier) and row['avg_mcc_cb_ratio'] > 0:
            score += 80 
            reasons.append(f"CB SAPMASI ({multiplier}X): Sektör Ort. {row['avg_mcc_cb_ratio']:.2f}%")

        # Kural 2: Refund Oranı Sapması (YENİ)
        if row['refund_ratio'] > (row['avg_mcc_refund_ratio'] * multiplier) and row['avg_mcc_refund_ratio'] > 0:
            score += 45
            reasons.append(f"İADE SAPMASI ({multiplier}X)")
            
        # Kural 3: Non-3DS Oranı Sapması (YENİ)
        if row['non_3d_ratio'] > (row['avg_mcc_non3d_ratio'] * multiplier) and row['avg_mcc_non3d_ratio'] > 0:
            score += 30
            reasons.append(f"3DSİZ SAPMASI ({multiplier}X)")
        
        # Kural 4: Yurt Dışı IP Sapması (YENİ)
        if row['avg_foreign_ip_ratio'] > (row['avg_mcc_foreign_ip_ratio'] * multiplier) and row['avg_mcc_foreign_ip_ratio'] > 0.01:
            score += 25
            reasons.append(f"Y.DIŞI IP SAPMASI ({multiplier}X)")

        # Kural 5: Tek IP Konsantrasyonu (Eski Kural)
        if row['ip_conc_ratio'] > (param_ip_conc / 100.0):
            score += 50
            reasons.append(f"BOT ({param_ip_conc}%+ Tek IP)")
            
        # Kural 6: Sepet Tutarı Sapması (Eski Kural)
        if row['ticket_variance_pct'] > st.session_state.param_avg_ticket_variance: # Session state kullanmadık, doğrudan değişkeni kullanacağız.
            score += 45
            reasons.append(f"MCC SEPET SAPMASI")

        return score, " | ".join(reasons)
    
    # Hesaplamayı Uygula
    results = merchant_stats.apply(calculate_adaptive_risk, axis=1)
    merchant_stats['risk_score'] = [x[0] for x in results]
    merchant_stats['risk_reasons'] = [x[1] for x in results]

    # --- 7. DASHBOARD GÖRÜNÜMÜ ---
    
    st.info(f"""
    ⚙️ **Aktif Kural Özeti:** MCC Sapma Çarpanı: **{param_variance_multiplier}X** | IP Limiti: **%{param_ip_conc}**
    """)
    
    riskli_merchantlar = merchant_stats[merchant_stats['risk_score'] > 0].sort_values('risk_score', ascending=False)
    
    st.subheader(f"🚨 Riskli İşyerleri ({len(riskli_merchantlar)})")

    if len(riskli_merchantlar) > 0:
        display_cols = [
            'merchant_id', 'mcc', 'risk_score', 'total_txn', 
            'cb_ratio', 'avg_mcc_cb_ratio', 
            'refund_ratio', 'avg_mcc_refund_ratio', 
            'non_3d_ratio', 'avg_mcc_non3d_ratio', 
            'risk_reasons'
        ]
        
        st.dataframe(
            riskli_merchantlar[display_cols]
            .style.format({
                'cb_ratio': "İ:{:.2f}%", 'avg_mcc_cb_ratio': "S:{:.2f}%",
                'refund_ratio': "İ:{:.2f}%", 'avg_mcc_refund_ratio': "S:{:.2f}%",
                'non_3d_ratio': "İ:{:.1f}%", 'avg_mcc_non3d_ratio': "S:{:.1f}%",
            })
            .background_gradient(cmap='Reds', subset=['risk_score']),
            use_container_width=True
        )
        st.markdown("_İ: İşyeri İstatistiği, S: Sektör Ortalaması_")
    else:
        st.success("✅ Seçilen kriterlere göre riskli işyeri bulunamadı.")
        
else:
    st.warning("Lütfen başlamak için sol menüden kuralları inceleyin ve Excel dosyasını yükleyin.")