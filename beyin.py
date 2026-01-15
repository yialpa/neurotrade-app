import ccxt
import pandas as pd
import requests
import time
import feedparser
from textblob import TextBlob
import numpy as np
import json
import os
from datetime import datetime, timedelta

# --- KİŞİSEL AYARLAR ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# --- STRATEJİ AYARLARI ---
TARAMA_PERIYOTLARI = ['4h', '1h'] 
RISK_REWARD_RATIO = 2.0 
HAFIZA_SURESI_SAAT = 4  # Aynı sinyali 4 saat boyunca tekrar atmaz

# Dosya Adı
HAFIZA_DOSYASI = 'hafiza.json'

def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': mesaj, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try:
        requests.post(url, data=payload)
    except:
        pass

# --- HAFIZA YÖNETİMİ ---
def hafiza_yukle():
    if os.path.exists(HAFIZA_DOSYASI):
        try:
            with open(HAFIZA_DOSYASI, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def hafiza_kaydet(hafiza):
    try:
        with open(HAFIZA_DOSYASI, 'w') as f:
            json.dump(hafiza, f)
    except:
        pass

def spam_kontrol(hafiza, coin, sinyal, timeframe):
    """
    Eğer bu sinyal yakın zamanda atıldıysa True döner (Spam var).
    """
    key = f"{coin}_{timeframe}"
    if key in hafiza:
        son_veri = hafiza[key]
        last_signal = son_veri.get('sinyal')
        last_time_str = son_veri.get('zaman')
        
        # Zaman farkını hesapla
        last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
        gecen_sure = datetime.now() - last_time
        
        # 1. Kural: Aynı Sinyal (LONG/LONG) ve Süre Dolmadıysa -> SPAMDIR
        if last_signal == sinyal and gecen_sure < timedelta(hours=HAFIZA_SURESI_SAAT):
            return True
            
    return False

# --- 1. MODÜL: BTC PATRON KONTROLÜ ---
def btc_durumu(exchange):
    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        degisim = ticker['percentage']
        fiyat = ticker['last']
        return degisim, fiyat
    except:
        return 0, 0

# --- 2. MODÜL: HABER ANALİZİ ---
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

# --- YARDIMCI: ADX ---
def calculate_adx(df, period=14):
    try:
        df['up'] = df['high'] - df['high'].shift(1)
        df['down'] = df['low'].shift(1) - df['low']
        df['+dm'] = np.where((df['up'] > df['down']) & (df['up'] > 0), df['up'], 0)
        df['-dm'] = np.where((df['down'] > df['up']) & (df['down'] > 0), df['down'], 0)
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                         abs(df['low'] - df['close'].shift(1))))
        
        df['tr_s'] = df['tr'].rolling(window=period).sum()
        df['+dm_s'] = df['+dm'].rolling(window=period).sum()
        df['-dm_s'] = df['-dm'].rolling(window=period).sum()
        
        df['+di'] = 100 * (df['+dm_s'] / df['tr_s'])
        df['-di'] = 100 * (df['-dm_s'] / df['tr_s'])
        df['dx'] = 100 * abs((df['+di'] - df['-di']) / (df['+di'] + df['-di']))
        df['adx'] = df['dx'].rolling(window=period).mean()
        return df['adx'].iloc[-1]
    except:
        return 25 

# --- 3. MODÜL: MEGA TEKNİK ANALİZ ---
def teknik_analiz(exchange, coin, df, btc_degisim):
    df['ATR'] = df['high'] - df['low']
    son_fiyat = df['close'].iloc[-1]
    
    # Balina ve ADX
    hacim_ort = df['volume'].rolling(window=20).mean().iloc[-1]
    son_hacim = df['volume'].iloc[-1]
    balina_notu = "🐋 **BALİNA ALARMI**" if son_hacim > (hacim_ort * 3.0) else ""
    adx_degeri = calculate_adx(df)
    
    if adx_degeri < 20: return None, None, 0, 0, None, None

    # ICT
    destek = df['low'].rolling(window=50).min().iloc[-1]
    direnc = df['high'].rolling(window=50).max().iloc[-1]
    dist_to_supp = (son_fiyat - destek) / son_fiyat
    dist_to_res = (direnc - son_fiyat) / son_fiyat
    
    fvg_bull = (df['high'].shift(2) < df['low']) & (df['close'].shift(1) > df['open'].shift(1))
    fvg_bear = (df['low'].shift(2) > df['high']) & (df['close'].shift(1) < df['open'].shift(1))

    sinyal = None
    tip = "Swing" if "4h" in str(df.name) else "Scalp"
    sl = 0.0
    tp = 0.0

    if (dist_to_supp < 0.02 or fvg_bull.iloc[-1]) and btc_degisim > -3.0:
        sinyal = "LONG 🟢"
        sl = son_fiyat - (df['ATR'].iloc[-1] * 1.5)
        tp = son_fiyat + ((son_fiyat - sl) * RISK_REWARD_RATIO)

    elif (dist_to_res < 0.02 or fvg_bear.iloc[-1]):
        sinyal = "SHORT 🔴"
        sl = son_fiyat + (df['ATR'].iloc[-1] * 1.5)
        tp = son_fiyat - ((sl - son_fiyat) * RISK_REWARD_RATIO)

    return sinyal, tip, sl, tp, balina_notu, "Nötr"

# --- ANA MOTOR ---
def calistir():
    exchange = ccxt.binanceus() 
    market_duygusu = piyasa_duygusunu_olc()
    btc_degisim, btc_fiyat = btc_durumu(exchange)
    
    # Hafızayı Yükle
    hafiza = hafiza_yukle()
    
    print(f"🌍 Piyasa Modu: {market_duygusu}")
    print(f"👑 BTC Durumu: ${btc_fiyat} (%{btc_degisim:.2f})")
    
    hedef_coinler = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'DOGE/USDT', 'LTC/USDT', 'LINK/USDT']
    raporlar = []

    for coin in hedef_coinler:
        for tf in TARAMA_PERIYOTLARI:
            try:
                bars = exchange.fetch_ohlcv(coin, timeframe=tf, limit=100)
                df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df.name = tf
                
                sinyal, tip, sl, tp, balina, funding = teknik_analiz(exchange, coin, df, btc_degisim)
                
                if sinyal:
                    # 1. SPAM KONTROLÜ (Hafızada var mı?)
                    if spam_kontrol(hafiza, coin, sinyal, tip):
                        print(f"🚫 SPAM ENGELLENDİ: {coin} {sinyal} ({tip}) - Yakın zamanda atıldı.")
                        continue # Mesaj atma, sonraki coine geç

                    # 2. HABER VETOSU
                    if sinyal == "LONG 🟢" and market_duygusu == "NEGATIF": continue
                    if sinyal == "SHORT 🔴" and market_duygusu == "POZITIF": continue

                    fiyat = df['close'].iloc[-1]
                    mesaj = f"⚡ **NEUROTRADE {sinyal}** ({tip})\n\n"
                    mesaj += f"💎 **Coin:** #{coin.split('/')[0]}\n"
                    mesaj += f"💵 **Giriş:** ${fiyat:.4f}\n"
                    
                    if balina: mesaj += f"{balina} 🚨\n"
                    
                    mesaj += f"🛑 **Stop:** ${sl:.4f}\n"
                    mesaj += f"🎯 **Hedef:** ${tp:.4f}\n\n"
                    mesaj += f"📊 **Analiz:**\n"
                    mesaj += f"• 📰 Haber Modu: {market_duygusu}\n"
                    mesaj += f"• 👑 BTC Filtresi: {'Güvenli ✅' if btc_degisim > -3 else 'Riskli ⚠️'}"

                    raporlar.append(mesaj)
                    
                    # 3. HAFIZAYA KAYDET (Mesaj atılacaksa)
                    hafiza[f"{coin}_{tip}"] = {
                        "sinyal": sinyal,
                        "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                time.sleep(0.5)
            except Exception as e:
                print(f"Hata ({coin}): {e}")
                continue

    if raporlar:
        telegram_gonder("\n----------------------\n".join(raporlar))
        # İşlem bitince hafızayı dosyaya yaz
        hafiza_kaydet(hafiza)
    else:
        print("Uygun setup yok veya hepsi spam filtresine takıldı.")

if __name__ == "__main__":
    calistir()
