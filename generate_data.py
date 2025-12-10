import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# --- AYARLAR ---
np.random.seed(42)
random.seed(42)
n_total_txns = 8500 

# --- PARAMETRELER ---
safe_mccs = [5411, 5812]
high_risk_countries = ['CY', 'MT', 'PA', 'VG', 'KY'] 
safe_countries = ['TR', 'US', 'DE', 'UK', 'FR']

# --- SENARYOLAR ---
merchant_profiles = {
    'SAFE': [f"MERC_SAFE_{str(i).zfill(2)}" for i in range(1, 40)],
    'HIGH_CB': [f"MERC_CB_{str(i).zfill(2)}" for i in range(1, 5)],
    'NO_3DS': [f"MERC_NO3D_{str(i).zfill(2)}" for i in range(1, 5)],
    'BOT_ATTACK': [f"MERC_BOT_{str(i).zfill(2)}" for i in range(1, 4)],
    'OFFSHORE': [f"MERC_OFF_{str(i).zfill(2)}" for i in range(1, 3)],
}

data = []
base_time = datetime(2024, 12, 1, 8, 0, 0)

print("🚀 Veri Üretimi Başladı...")

for i in range(n_total_txns):
    
    category = np.random.choice(list(merchant_profiles.keys()), p=[0.65, 0.10, 0.10, 0.08, 0.07])
    merchant_id = np.random.choice(merchant_profiles[category])
    
    if category == 'OFFSHORE':
        mcc = 5094 
        amount = round(np.random.exponential(scale=15000), 2) + 1000
    elif category == 'SAFE':
        mcc = np.random.choice(safe_mccs)
        amount = round(np.random.exponential(scale=400), 2) + 20
    else:
        mcc = np.random.choice([5411, 5812, 7995]) 
        amount = round(np.random.exponential(scale=600), 2) + 50

    if category == 'NO_3DS':
        is_3d_secure = np.random.choice([0, 1], p=[0.85, 0.15]) 
    else:
        is_3d_secure = np.random.choice([0, 1], p=[0.05, 0.95]) 

    is_chargeback = 0
    if category == 'HIGH_CB':
        is_chargeback = np.random.choice([0, 1], p=[0.85, 0.15]) 
    
    ip_country = 'TR'
    if category == 'BOT_ATTACK':
        ip_address = "192.168.1.105"
        device_id = "DEV_BOT_01"
        ip_country = 'US'
    else:
        ip_address = f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"
        device_id = f"DEV_{random.randint(10000, 99999)}"
        if random.random() < 0.05: ip_country = 'US'

    if category == 'OFFSHORE':
        card_country = np.random.choice(high_risk_countries)
    else:
        card_country = np.random.choice(safe_countries, p=[0.90, 0.04, 0.02, 0.02, 0.02])

    is_refund = 1 if random.random() < 0.02 else 0 
    txn_time = base_time + timedelta(minutes=np.random.randint(0, 43200))
    
    data.append({
        "transaction_id": 10000 + i,
        "timestamp": txn_time,
        "merchant_id": merchant_id,
        "mcc": str(mcc),
        "amount": amount,
        "is_3d_secure": is_3d_secure,
        "ip_address": ip_address,
        "ip_country": ip_country,
        "device_id": device_id,
        "card_country": card_country,
        "is_chargeback": is_chargeback,
        "is_refund": is_refund
    })

df = pd.DataFrame(data)
df.to_excel("vpos_test_data_final.xlsx", index=False)
print("✅ Veri Seti Hazır: vpos_test_data_final.xlsx")