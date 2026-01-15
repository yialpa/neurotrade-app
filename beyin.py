import ccxt
import pandas as pd
import requests
import time
import feedparser
from textblob import TextBlob
import numpy as np

# --- KİŞİSEL AYARLAR ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# --- STRATEJİ AYARLARI ---
TARAMA_PERIYOTLARI = ['4h', '1h'] 
RISK_REWARD_RATIO = 2.0 

def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': mesaj, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try:
        requests.post(url, data=payload)
    except:
        pass

# --- 1. MODÜL: BTC PATRON KONTROLÜ ---
def btc_durumu(exchange):
    """
    BTC %3'ten fazla düştüyse piyasa 'KIRMIZI ALARM'dır.
    """
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

# --- YARDIMCI: ADX HESAPLAMA (Trend Gücü) ---
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
        return 25 # Hata olursa varsayılan değer

# --- 3. MODÜL: MEGA TEKNİK ANALİZ ---
def teknik_analiz(exchange, coin, df, btc_degisim):
    df['ATR'] = df['high'] - df['low']
    son_fiyat = df['close'].iloc[-1]
    
    # 1. BALİNA KONTROLÜ 🐋
    hacim_ort = df['volume'].rolling(window=20).mean().iloc[-1]
    son_hacim = df['volume'].iloc[-1]
    balina_notu = "🐋 **BALİNA ALARMI**" if son_hacim > (hacim_ort * 3.0) else ""

    # 2. ADX TREND KONTROLÜ 📉
    adx_degeri = calculate_adx(df)
    trend_notu = "Güçlü Trend" if adx_degeri > 25 else "Zayıf Trend"
    
    # Eğer Trend çok zayıfsa (ADX < 20) işlem açma (Ölü Piyasa)
    if adx_degeri < 20:
        return None, None, 0, 0, None, None

    # 3. FUNDING RATE (TERS KÖŞE) 😈
    try:
        funding_info = exchange.fetch_funding_rate(coin)
        funding_rate = funding_info['fundingRate'] * 100 # Yüzdeye çevir
        funding_yorum = "Aşırı Long" if funding_rate > 0.01 else ("Aşırı Short" if funding_rate < -0.01 else "Nötr")
    except:
        funding_rate = 0
        funding_yorum = "Nötr"

    # 4. ICT & PRICE ACTION
    destek = df['low'].rolling(window=50).min().iloc[-1]
    direnc = df['high'].rolling(window=50).max().iloc[-1]
    dist_to_supp = (son_fiyat - destek) / son_fiyat
    dist_to_res = (direnc - son_fiyat) / son_fiyat
    
    # FVG Tespiti
    fvg_bull = (df['high'].shift(2) < df['low']) & (df['close'].shift(1) > df['open'].shift(1))
    fvg_bear = (df['low'].shift(2) > df['high']) & (df['close'].shift(1) < df['open'].shift(1))

    sinyal = None
    tip = "Swing" if "4h" in str(df.name) else "Scalp"

    # --- KARAR MEKANİZMASI ---

    # LONG SENARYOSU
    # Kural: BTC Çakılmıyor olmalı (> -3%) VE (Destek Yakın VEYA FVG Var)
    if (dist_to_supp < 0.02 or fvg_bull.iloc[-1]) and btc_degisim > -3.0:
        # Funding Kontrolü: Herkes Aşırı Long ise biz girmeyelim (Tuzak olabilir)
        if funding_rate < 0.02: 
            sinyal = "LONG 🟢"
            sl = son_fiyat - (df['ATR'].iloc[-1] * 1.5)
            tp = son_fiyat + ((son_fiyat - sl) * RISK_REWARD_RATIO)

    # SHORT SENARYOSU
    # Kural: (Direnç Yakın VEYA FVG Var)
    elif (dist_to_res < 0.02 or fvg_bear.iloc[-1]):
        # Funding Kontrolü: Herkes Aşırı Short ise biz girmeyelim (Squeeze riski)
        if funding_rate > -0.02:
            sinyal = "SHORT 🔴"
            sl = son_fiyat + (df['ATR'].iloc[-1] * 1.5)
            tp = son_fiyat - ((sl - son_fiyat) * RISK_REWARD_RATIO)

    return sinyal, tip, sl, tp, balina_notu, funding_yorum

# --- ANA MOTOR ---
def calistir():
    exchange = ccxt.binance()
    market_duygusu = piyasa_duygusunu_olc()
    btc_degisim, btc_fiyat = btc_durumu(exchange)
    
    print(f"🌍 Piyasa Modu: {market_duygusu}")
    print(f"👑 BTC Durumu: ${btc_fiyat} (%{btc_degisim:.2f})")
    
    hedef_coinler = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT', 'AVAX/USDT', 'DOGE/USDT', 'APT/USDT']
    raporlar = []

    for coin in hedef_coinler:
        for tf in TARAMA_PERIYOTLARI:
            try:
                bars = exchange.fetch_ohlcv(coin, timeframe=tf, limit=100)
                df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df.name = tf
                
                sinyal, tip, sl, tp, balina, funding = teknik_analiz(exchange, coin, df, btc_degisim)
                
                if sinyal:
                    # GLOBAL HABER FİLTRESİ (VETO)
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
                    mesaj += f"• 😈 Funding: {funding}\n"
                    mesaj += f"• 👑 BTC Filtresi: {'Güvenli ✅' if btc_degisim > -3 else 'Riskli ⚠️'}"

                    raporlar.append(mesaj)
                time.sleep(0.5)
            except Exception as e:
                print(f"Hata ({coin}): {e}")
                continue

    if raporlar:
        telegram_gonder("\n----------------------\n".join(raporlar))
    else:
        print("Uygun Mega-Setup bulunamadı.")

if __name__ == "__main__":
    calistir()
