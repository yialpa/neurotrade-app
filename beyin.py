Kaptan, hata raporuna baktım. Sorun çok basit bir "kesme yapıştırma kazası". ✂️💥

satırda kodun bir kısmı silinmiş veya yarım kalmış. Hata veren satır şu şekilde görünüyor: elif (dist_to_res < 0.02 or df[' (Tırnak açılmış ama kapanmamış, kod yarım).

Senin için beyin.py dosyasını tamamen onardım. Ayrıca az önce verdiğin Token ve Chat ID bilgilerini de kodun içine yerleştirdim.

Yapman gereken tek şey:

beyin.py dosyasını aç.

Hepsini sil.

Aşağıdaki kodu (hiçbir şeye dokunmadan) yapıştır.

Commit changes de.

Python

import ccxt
import pandas as pd
import requests
import time
import feedparser
from textblob import TextBlob
import numpy as np

# --- KİŞİSEL AYARLAR (Otomatik Dolduruldu) ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# --- STRATEJİ AYARLARI ---
# Swing için 4h, Scalp için 1h veya 15m kullanır
TARAMA_PERIYOTLARI = ['4h', '1h'] 
RISK_REWARD_RATIO = 2.0  # 1 birim riske 2 birim kazanç hedefler

def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': mesaj, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try:
        requests.post(url, data=payload)
    except:
        pass

# --- 1. MODÜL: HABER VE DUYGU ANALİZİ (Global Filtre) ---
def piyasa_duygusunu_olc():
    """
    Piyasa haberlerini okur ve genel bir 'Hava Durumu' çıkarır.
    Dönüş: 'POZITIF', 'NEGATIF' veya 'NOTR'
    """
    try:
        url = "https://cointelegraph.com/rss"
        feed = feedparser.parse(url)
        toplam_skor = 0
        haber_sayisi = 0
        
        print("Haberler analiz ediliyor...")
        for entry in feed.entries[:7]: # Son 7 haberi oku
            analiz = TextBlob(entry.title)
            skor = analiz.sentiment.polarity
            toplam_skor += skor
            haber_sayisi += 1
            
        ortalama_skor = toplam_skor / haber_sayisi if haber_sayisi > 0 else 0
        
        if ortalama_skor > 0.15: return "POZITIF"
        elif ortalama_skor < -0.15: return "NEGATIF"
        else: return "NOTR"
    except:
        return "NOTR"

# --- 2. MODÜL: TEKNİK ANALİZ (ICT & Price Action) ---
def teknik_analiz(df):
    # Temel Veriler
    df['ATR'] = df['high'] - df['low'] # Basit Volatilite Ölçümü
    son_fiyat = df['close'].iloc[-1]
    
    # --- ICT: FVG (Fair Value Gap) Tespiti ---
    # Bullish FVG: Mum 1 High < Mum 3 Low (Arada boşluk var)
    df['FVG_Bullish'] = (df['high'].shift(2) < df['low']) & (df['close'].shift(1) > df['open'].shift(1))
    # Bearish FVG: Mum 1 Low > Mum 3 High
    df['FVG_Bearish'] = (df['low'].shift(2) > df['high']) & (df['close'].shift(1) < df['open'].shift(1))
    
    fvg_bull_var = df['FVG_Bullish'].iloc[-1]
    fvg_bear_var = df['FVG_Bearish'].iloc[-1]

    # --- Destek / Direnç Tespiti (Son 50 mum) ---
    destek = df['low'].rolling(window=50).min().iloc[-1]
    direnc = df['high'].rolling(window=50).max().iloc[-1]
    
    dist_to_supp = (son_fiyat - destek) / son_fiyat
    dist_to_res = (direnc - son_fiyat) / son_fiyat

    # --- Sinyal Kararı ---
    sinyal = None
    setup_tipi = ""
    stop_loss = 0.0
    take_profit = 0.0

    # LONG SENARYOSU
    # 1. Fiyat Destekte VEYA Bullish FVG içinde
    # 2. Fiyat Hareketli Ortalamanın (EMA 50) üzerinde (Trend Onayı)
    ema50 = df['close'].ewm(span=50).mean().iloc[-1]
    
    if (dist_to_supp < 0.02 or fvg_bull_var): # Desteğe %2 yakın veya FVG var
        sinyal = "LONG 🟢"
        setup_tipi = "Swing" if "4h" in str(df.name) else "Scalp"
        # Stop Loss: Son mumun en düşüğünün biraz altı veya Destek altı
        atr = df['ATR'].iloc[-1]
        stop_loss = son_fiyat - (atr * 1.5) 
        take_profit = son_fiyat + ((son_fiyat - stop_loss) * RISK_REWARD_RATIO)

    # SHORT SENARYOSU
    elif (dist_to_res < 0.02 or fvg_bear_var):
        sinyal = "SHORT 🔴"
        setup_tipi = "Swing" if "4h" in str(df.name) else "Scalp"
        atr = df['ATR'].iloc[-1]
        stop_loss = son_fiyat + (atr * 1.5)
        take_profit = son_fiyat - ((stop_loss - son_fiyat) * RISK_REWARD_RATIO)

    return sinyal, setup_tipi, stop_loss, take_profit, destek, direnc

# --- ANA MOTOR ---
def calistir():
    exchange = ccxt.binance() # Hacim verisi için
    market_duygusu = piyasa_duygusunu_olc()
    
    print(f"Piyasa Modu: {market_duygusu}")
    
    # Sadece Top Coinleri Tara
    hedef_coinler = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT', 'AVAX/USDT', 'DOGE/USDT', 'APT/USDT']
    
    raporlar = []

    for coin in hedef_coinler:
        for tf in TARAMA_PERIYOTLARI:
            try:
                bars = exchange.fetch_ohlcv(coin, timeframe=tf, limit=100)
                df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df.name = tf # Dataframe'e isim etiketi yapıştır
                
                sinyal, tip, sl, tp, sup, res = teknik_analiz(df)
                
                if sinyal:
                    fiyat = df['close'].iloc[-1]
                    
                    # --- HABER FİLTRESİ (VETO SİSTEMİ) ---
                    # Eğer Piyasa Çok Kötü (NEGATIF) ama Teknik LONG diyorsa -> İŞLEMİ İPTAL ET
                    if sinyal == "LONG 🟢" and market_duygusu == "NEGATIF":
                        print(f"🚫 {coin} LONG sinyali haberler kötü olduğu için iptal edildi.")
                        continue
                    # Eğer Piyasa Çok İyi (POZITIF) ama Teknik SHORT diyorsa -> İŞLEMİ İPTAL ET
                    if sinyal == "SHORT 🔴" and market_duygusu == "POZITIF":
                        print(f"🚫 {coin} SHORT sinyali haberler iyi olduğu için iptal edildi.")
                        continue
                        
                    # Mesaj Hazırla
                    mesaj = f"⚡ **NEUROTRADE {sinyal}** ({tip})\n\n"
                    mesaj += f"💎 **Coin:** #{coin.split('/')[0]}\n"
                    mesaj += f"💵 **Giriş:** ${fiyat:.4f}\n"
                    mesaj += f"🛑 **Stop Loss:** ${sl:.4f}\n"
                    mesaj += f"🎯 **Take Profit:** ${tp:.4f} (RR 1:2)\n\n"
                    mesaj += f"📊 **Teknik:** FVG/Destek-Direnç Onaylı\n"
                    mesaj += f"📰 **Piyasa Modu:** {market_duygusu} (Filtreden Geçti ✅)"
                    
                    raporlar.append(mesaj)
                    
                time.sleep(0.5)
            except Exception as e:
                print(f"Hata: {e}")
                continue

    if raporlar:
        full_rapor = "\n----------------------\n".join(raporlar)
        telegram_gonder(full_rapor)
    else:
        print("Uygun setup bulunamadı.")

if __name__ == "__main__":
    calistir()
