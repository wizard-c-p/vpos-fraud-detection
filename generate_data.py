import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Ayarlar
np.random.seed(42)
random.seed(42)
n_total_txns = 2000 # Toplam işlem sayısı

# --- YARDIMCI VERİ HAVUZLARI ---
merchant_profiles = {
    'SAFE': [f"MERC_SAFE_{str(i).zfill(2)}" for i in range(1, 16)],       # 15 Güvenli İşyeri
    'TESTER': [f"MERC_TEST_{str(i).zfill(2)}" for i in range(1, 4)],      # 3 Card Testing Yapan (Yüksek Hata)
    'LAUNDER': [f"MERC_LAUN_{str(i).zfill(2)}" for i in range(1, 3)],     # 2 Kara Para Şüphelisi (Aynı Kart)
    'MO_RISK': [f"MERC_MAIL_{str(i).zfill(2)}" for i in range(1, 3)]      # 2 Mail Order Riskli
}

all_merchants = [m for sublist in merchant_profiles.values() for m in sublist]
card_pool = [f"CARD_{str(i).zfill(4)}" for i in range(1, 1001)] # 1000 Farklı kart

base_time = datetime(2024, 12, 1, 8, 0, 0)
data = []

print("Senaryo bazlı veri üretimi başlıyor...")

# İşlem üretimi için döngü
for i in range(n_total_txns):
    
    # 1. İşyeri Seçimi (Ağırlıklı Rastgelelik)
    # İşlemlerin %60'ı güvenli, %40'ı riskli işyerlerinden gelsin
    category = np.random.choice(['SAFE', 'TESTER', 'LAUNDER', 'MO_RISK'], p=[0.6, 0.15, 0.1, 0.15])
    merchant_id = np.random.choice(merchant_profiles[category])
    
    # --- SENARYOLAR ---
    
    # SENARYO A: GÜVENLİ İŞYERİ (Normal Davranış)
    if category == 'SAFE':
        amount = round(np.random.exponential(scale=300), 2) + 10 # 10-1000 TL arası
        card_id = np.random.choice(card_pool) # Herhangi bir kart
        resp_code = np.random.choice(['00', '51', '05'], p=[0.95, 0.03, 0.02]) # %95 Başarı
        is_mo = np.random.choice([0, 1], p=[0.9, 0.1]) # Çok az mail order
        label = 0 # Fraud değil
        
    # SENARYO B: CARD TESTER (Yüksek Hata Oranı - Saldırı)
    elif category == 'TESTER':
        amount = round(np.random.uniform(1, 50), 2) # Küçük tutarlar (Limit deniyor)
        card_id = np.random.choice(card_pool) # Sürekli farklı kart deniyor
        # %70 Hata alır (Yetersiz bakiye vb.)
        resp_code = np.random.choice(['00', '51', '99'], p=[0.3, 0.6, 0.1]) 
        is_mo = 1 # Genelde botlar mail order dener
        label = 1 # Fraud girişimi
        
    # SENARYO C: PARA AKLAMA / POS TEFECİLİĞİ (Düşük Kart Çeşitliliği)
    elif category == 'LAUNDER':
        amount = round(np.random.uniform(5000, 20000), 2) # Yüksek tutarlar
        # Bu işyeri sadece kendine ait 2-3 kartı kullanır
        special_cards = [f"CARD_LAUNDER_{merchant_id}_1", f"CARD_LAUNDER_{merchant_id}_2"]
        card_id = np.random.choice(special_cards)
        resp_code = '00' # İşlem hep başarılıdır (Limit sorunu yok)
        is_mo = 0 # Fiziksel işlem gibi gösterir
        label = 1 # Fraud (AML şüphesi)

    # SENARYO D: MAIL ORDER RİSKİ
    elif category == 'MO_RISK':
        amount = round(np.random.exponential(scale=1000), 2)
        card_id = np.random.choice(card_pool)
        resp_code = np.random.choice(['00', '51'], p=[0.8, 0.2])
        is_mo = 1 # %100 Mail Order
        label = 0 if resp_code == '00' else 1 # Hatalıysa şüpheli
    
    # Ortak Alanlar
    # Zaman: Rastgele dağıt, mikrosaniye ekle (index hatası olmasın diye)
    txn_time = base_time + timedelta(
        minutes=np.random.randint(0, 43200), # 1 aylık süre
        microseconds=np.random.randint(0, 999999)
    )
    
    # IP Ülkesi (Basit mantık)
    ip_country = 'TR'
    if category == 'TESTER' and random.random() > 0.5:
        ip_country = np.random.choice(['US', 'RU', 'CN']) # Saldırgan IP'leri

    data.append({
        "transaction_id": 10000 + i,
        "timestamp": txn_time,
        "merchant_id": merchant_id,
        "card_id": card_id,
        "amount": amount,
        "response_code": resp_code,
        "is_mail_order": is_mo,
        "ip_country": ip_country,
        "label": label
    })

# DataFrame oluştur
df = pd.DataFrame(data)

# Zaman sıralaması (Grafikler için kritik)
df = df.sort_values(by="timestamp").reset_index(drop=True)

# Excel'e Kaydet
file_name = "vpos_dashboard_data.xlsx"
df.to_excel(file_name, index=False)

print(f"\n✅ Veri seti oluşturuldu: {file_name}")
print(f"Toplam İşlem: {len(df)}")
print("\n--- ÖZET İSTATİSTİKLER ---")
print(df.groupby('merchant_id').agg({'amount':'sum', 'response_code': lambda x: (x!='00').mean()}).head())
print("\nİPUCU: Bu dosyayı 'aml_dashboard_v2.py' uygulamasına yüklediğinde;")
print("1. MERC_TEST_xx -> 'Yüksek Hata Oranı' uyarısı verecek.")
print("2. MERC_LAUN_xx -> 'Kart Testi/Düşük Çeşitlilik' uyarısı verecek.")