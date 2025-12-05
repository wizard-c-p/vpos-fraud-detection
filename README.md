# 🛡️ vPOS AML & Fraud Detection System

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red)
![Status](https://img.shields.io/badge/Status-Active-success)

## 📌 Proje Hakkında
Bu proje, Sanal POS (vPOS) ekosisteminde gerçekleşen finansal işlemleri analiz etmek, **Kara Para Aklama (AML)** ve **Dolandırıcılık (Fraud)** girişimlerini tespit etmek amacıyla geliştirilmiş uçtan uca bir analiz simülasyonudur.

Sistem, kural tabanlı (Rule-Based) risk motoru ile modern veri analitiği yöntemlerini birleştirerek, üye işyeri (Merchant) davranışlarını denetler ve risk skorlaması yapar.

### 🚀 Temel Özellikler

* **Sentetik Veri Üretimi:** Gerçek hayat senaryolarına (Card Testing, Velocity Attacks, Pos Tefeciliği) uygun, milyonlarca satırlık finansal işlem verisi simüle edebilir.
* **Merchant Scoring (Risk Motoru):** İşyerlerini; Hata Oranı (Failure Rate), Kart Çeşitliliği ve İşlem Tiplerine (Mail Order) göre puanlar.
* **İnteraktif Dashboard:** Streamlit tabanlı arayüz ile riskli işyerlerini ve şüpheli işlemleri görselleştirir.
* **Otomatik Raporlama:** Yüksek riskli (Skor > 40) işyerlerini tespit edip Excel/CSV formatında denetim raporu sunar.

## 🛠️ Kurulum ve Çalıştırma

Projeyi yerel makinenizde çalıştırmak için aşağıdaki adımları izleyin:

1. **Repoyu klonlayın:**
   ```bash
   git clone [https://github.com/wizard-c-p/vpos-fraud-detection.git](https://github.com/wizard-c-p/vpos-fraud-detection.git)
   cd vpos-fraud-detection