import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# Sayfa Ayarları
st.set_page_config(page_title="vPOS AML & Fraud Denetim Paneli", layout="wide")

st.title("🛡️ vPOS AML Denetim ve Raporlama Sistemi")

# --- 1. DOSYA YÜKLEME ---
uploaded_file = st.sidebar.file_uploader("İşlem dosyasını yükleyin (Excel)", type=["xlsx"])

if uploaded_file is not None:
    # Veriyi Yükle ve Ön İşleme
    @st.cache_data
    def load_data(file):
        df = pd.read_excel(file)
        # Demo amaçlı merchant_id yoksa ekle
        if 'merchant_id' not in df.columns:
            merchant_ids = [f"MERC_{str(i).zfill(3)}" for i in range(1, 21)]
            df['merchant_id'] = np.random.choice(merchant_ids, size=len(df))
        return df

    df = load_data(uploaded_file)
    
    # --- RİSK MOTORU (MERCHANT SCORING) ---
    # İşyeri bazlı istatistikleri hesapla
    merchant_stats = df.groupby('merchant_id').agg({
        'transaction_id': 'count',
        'amount': 'sum',
        'card_id': 'nunique',
        'response_code': lambda x: (x != '00').sum(), # Hatalı işlem sayısı
        'is_mail_order': 'sum'
    }).reset_index()

    merchant_stats.columns = ['merchant_id', 'total_txn', 'total_amount', 'unique_cards', 'failed_txns', 'mail_orders']
    
    # Türetilmiş Metrikler
    merchant_stats['failure_rate'] = (merchant_stats['failed_txns'] / merchant_stats['total_txn']) * 100
    merchant_stats['txn_per_card'] = merchant_stats['total_txn'] / merchant_stats['unique_cards']

    # Risk Puanlama Fonksiyonu
    def calculate_risk_score(row):
        score = 0
        reasons = []
        
        if row['failure_rate'] > 50: 
            score += 50
            reasons.append("Çok Yüksek Hata Oranı")
        elif row['failure_rate'] > 20: 
            score += 20
            reasons.append("Yüksek Hata Oranı")
            
        if row['txn_per_card'] > 5: 
            score += 30
            reasons.append("Kart Testi Şüphesi (Velocity)")
            
        if (row['mail_orders'] / row['total_txn']) > 0.8: 
            score += 10
            reasons.append("Aşırı Mail Order")
            
        return score, ", ".join(reasons)

    # Apply fonksiyonu ile hem skor hem nedenleri al
    risk_results = merchant_stats.apply(calculate_risk_score, axis=1)
    merchant_stats['risk_score'] = [x[0] for x in risk_results]
    merchant_stats['risk_reasons'] = [x[1] for x in risk_results]

    # --- SEKME YAPISI (TABS) ---
    tab1, tab2 = st.tabs(["📊 Genel Analiz Paneli", "📑 Şüpheli İşlem Raporu"])

    # ==========================================
    # SEKME 1: GÖRSEL ANALİZ (DASHBOARD)
    # ==========================================
    with tab1:
        st.subheader("Genel Durum Özeti")
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Hacim", f"{df['amount'].sum():,.2f} ₺")
        col2.metric("Toplam İşlem", len(df))
        col3.metric("Riskli İşyeri Sayısı (>50 Puan)", len(merchant_stats[merchant_stats['risk_score'] > 50]))
        st.divider()

        # Risk Tablosu
        st.write("### 🚨 Tüm İşyerleri Risk Sıralaması")
        st.dataframe(
            merchant_stats.sort_values(by='risk_score', ascending=False)
            .style.background_gradient(cmap='Reds', subset=['risk_score'])
            .format({"total_amount": "{:,.2f}", "failure_rate": "{:.1f}%"}),
            use_container_width=True
        )

        # Grafikler
        c1, c2 = st.columns(2)
        with c1:
            fig = px.scatter(merchant_stats, x='failure_rate', y='risk_score', size='total_amount', 
                             color='risk_score', hover_name='merchant_id', title="Risk vs Hata Oranı")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            top_risky = merchant_stats.sort_values('risk_score', ascending=False).head(10)
            fig2 = px.bar(top_risky, x='merchant_id', y='risk_score', color='risk_score', title="En Riskli 10 İşyeri")
            st.plotly_chart(fig2, use_container_width=True)

    # ==========================================
    # SEKME 2: ŞÜPHELİ İŞLEM RAPORU (REPORTING)
    # ==========================================
    with tab2:
        st.header("📑 Yüksek Riskli İşyeri Denetim Raporu")
        st.markdown("_Bu ekran, risk puanı **40 ve üzeri** olan işyerlerini ve onların şüpheli işlemlerini detaylandırır._")

        # Sadece Yüksek Riskli İşyerlerini Filtrele
        high_risk_merchants = merchant_stats[merchant_stats['risk_score'] >= 40].sort_values('risk_score', ascending=False)

        if len(high_risk_merchants) == 0:
            st.success("✅ Tebrikler! Sistemde yüksek riskli (Puan >= 40) işyeri bulunamadı.")
        else:
            # 1. ÖZET TABLO
            st.subheader("1. Riskli İşyerleri Özeti")
            st.dataframe(high_risk_merchants[['merchant_id', 'risk_score', 'risk_reasons', 'total_amount', 'failure_rate']], use_container_width=True)

            # Rapor İndirme Butonu
            csv = high_risk_merchants.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Bu Özeti Excel/CSV Olarak İndir",
                data=csv,
                file_name='supheli_isyerleri_raporu.csv',
                mime='text/csv',
            )

            st.divider()

            # 2. DETAYLI İNCELEME (HER İŞYERİ İÇİN AYRI KART)
            st.subheader("2. İşyeri Bazlı Şüpheli İşlem Detayları")

            for index, merchant in high_risk_merchants.iterrows():
                m_id = merchant['merchant_id']
                score = merchant['risk_score']
                
                # Expandable (Açılır/Kapanır) kutu içinde detaylar
                with st.expander(f"🔴 {m_id} (Risk Skoru: {score}) - Detayları Göster"):
                    
                    st.write(f"**Tespit Edilen Risk Nedenleri:** {merchant['risk_reasons']}")
                    
                    # O işyerine ait sadece "Şüpheli" işlemleri getir
                    # Şüpheli işlem tanımı: Label=1 (ML sonucu) VEYA Hata kodu != 00
                    suspicious_txns = df[
                        (df['merchant_id'] == m_id) & 
                        ((df['label'] == 1) | (df['response_code'] != '00'))
                    ]
                    
                    if len(suspicious_txns) > 0:
                        st.warning(f"Bu işyerine ait **{len(suspicious_txns)} adet** şüpheli/hatalı işlem bulundu:")
                        st.dataframe(
                            suspicious_txns[['transaction_id', 'timestamp', 'amount', 'card_id', 'response_code', 'ip_country', 'label']]
                            .sort_values('timestamp', ascending=False),
                            use_container_width=True
                        )
                    else:
                        st.info("Bu işyerinin genel skoru yüksek olsa da, tekil bazda 'flag'lenmiş şüpheli işlem kaydı listelenemedi (Genel hacimsel risk olabilir).")

else:
    st.info("Lütfen analiz edilecek Excel dosyasını sol menüden yükleyin.")