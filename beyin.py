import ccxt
import pandas as pd
import requests
import time
import feedparser
from textblob import TextBlob
import numpy as np

# --- KİŞİSEL AYARLAR (Hafızadan Alındı) ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# --- STRATEJİ AYARLARI ---
TARAMA_PERIYOTLARI = ['4h', '1h'] 
RISK_REWARD_RATIO = 2.0  
BALINA_CARPANI = 3.0  # Ortalama hacmin 3 katı giriş olursa 'Balina' sayar

def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': mesaj, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try:
        requests.post(url, data=payload)
    except:
        pass

# --- MODÜL 1: FONLAMA ORANI (Kalabalık Nerede?) ---
def get_funding_rate(exchange, symbol):
    try:
        # Binance Vadeli işlemlerden fonlama oranını çek
        funding = exchange.fetch_funding_rate(symbol)
        rate = funding['fundingRate'] * 100 # Yüzdeye çevir
        
        durum = "NORMAL"
        if rate > 0.015: durum = "🔥 AŞIRI LONG (Düşüş Riski)"
        elif rate < -0.015: durum = "❄️ AŞIRI SHORT (Yükseliş Riski)"
        
        return rate, durum
    except:
        return 0.0, "Bilinmiyor"

# --- MODÜL 2: HABER ANALİZİ ---
def piyasa_duygusunu_olc():
    try:
        url = "https://cointelegraph.com/rss"
        feed = feedparser.parse(url)
        toplam_skor = 0
        haber_sayisi = 0
        
        for entry in feed.entries[:7]: 
            analiz = TextBlob(entry.title)
            toplam_skor += analiz.sentiment.polarity
            haber_sayisi += 1
            
        ortalama_skor = toplam_skor / haber_sayisi if haber_sayisi > 0 else 0
        
        if ortalama_skor > 0.15: return "POZITIF"
        elif ortalama_skor < -0.15: return "NEGATIF"
        else: return "NOTR"
    except:
        return "NOTR"

# --- MODÜL 3: TEKNİK ANALİZ (ICT + Balina + FVG) ---
def teknik_analiz(df, symbol, exchange_obj):
    # Temel Veriler
    df['ATR'] = df['high'] - df['low']
    son_fiyat = df['close'].iloc[-1]
    
    # 1. BALİNA KONTROLÜ (Volume Spike)
    # Son 20 mumun hacim ortalamasını al
    avg_vol = df['volume'].rolling(window=20).mean().iloc[-1]
    son_vol = df['volume'].iloc[-1]
    balina_var_mi = False
    
    if son_vol > (avg_vol * BALINA_CARPANI):
        balina_var_mi = True

    # 2. ICT: FVG Tespiti
    df['FVG_Bullish'] = (df['high'].shift(2) < df['low']) & (df['close'].shift(1) > df['open'].shift(1))
    df['FVG_Bearish'] = (df['low'].shift(2) > df['high']) & (df['close'].shift(1) < df['open'].shift(1))
    
    # 3. Destek / Direnç
    destek = df['low'].rolling(window=50).min().iloc[-1]
    direnc = df['high'].rolling(window=50).max().iloc[-1]
    
    dist_to_supp = (son_fiyat - destek) / son_fiyat
    dist_to_res = (direnc - son_fiyat) / son_fiyat

    # --- SİNYAL ÜRETİMİ ---
    sinyal = None
    setup_tipi = ""
    stop_loss = 0.0
    take_profit = 0.0

    # LONG MANTIĞI
    if (dist_to_supp < 0.02 or df['FVG_Bullish'].iloc[-1]):
        sinyal = "LONG 🟢"
        setup_tipi = "Swing" if "4h" in str(df.name) else "Scalp"
        atr = df['ATR'].iloc[-1]
        stop_loss = son_fiyat - (atr * 1.5) 
        take_profit = son_fiyat + ((son_fiyat - stop_loss) * RISK_REWARD_RATIO)

    # SHORT MANTIĞI
    elif (dist_to_res < 0.02 or df['
