import ccxt
import pandas as pd
import requests
import time
import feedparser
from textblob import TextBlob
import numpy as np
import json
from datetime import datetime, timedelta

# --- KİŞİSEL AYARLAR ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# --- JSONBIN AYARLARI ---
JSONBIN_API_KEY = "$2a$10$5cOoQOZABAJQlhbFtkjyk.pTqcw9gawnwvTfznf59FTmprp/cffV6"
JSONBIN_BIN_ID = "696944b1d0ea881f406e6a0c"

# --- STRATEJİ AYARLARI ---
TARAMA_PERIYOTLARI = ['4h', '1h'] 
RISK_REWARD_RATIO = 2.0 
HAFIZA_SURESI_SAAT = 4 
CEZA_SURESI_SAAT = 6 
KARI_KITLE_YUZDE = 1.5 # %1.5 kârda stopu girişe çeker

def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': mesaj, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try:
        requests.post(url, data=payload)
    except:
        pass

# --- BULUT HAFIZA ---
def hafiza_yukle():
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
    headers = {'X-Master-Key': JSONBIN_API_KEY}
    try:
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            return req.json()['record']
        return {}
    except:
        return {}

def hafiza_kaydet(hafiza):
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    headers = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}
    try:
        requests.put(url, json=hafiza, headers=headers)
    except:
        pass

# --- YENİ: GÜNLÜK RAPOR MODÜLÜ ---
def gunluk_rapor_kontrol(hafiza, market_duygusu, btc_fiyat):
    bugun = datetime.now().strftime("%Y-%m-%d")
    son_rapor = hafiza.get("son_rapor_tarihi", "")
    
    # Eğer bugün rapor atmadıysa AT
    if son_rapor != bugun:
        mesaj = f"📅 **GÜNLÜK PATRON RAPORU**\n\n"
        mesaj += f"✅ **Sistem:** Aktif ve Çalışıyor\n"
        mesaj += f"🌍 **Piyasa Modu:** {market_duygusu}\n"
        mesaj += f"👑 **BTC Fiyatı:** ${btc_fiyat:.2f}\n"
        mesaj += f"🛡️ **Güvenlik:** Korumalar Devrede\n\n"
        mesaj += f"🤖 *Ben buradayım Kaptan, nöbetteyim.*"
        
        telegram_gonder(mesaj)
        hafiza["son_rapor_tarihi"] = bugun
        return True # Hafıza güncellendi
    return False

# --- YENİ: KÂRI KİTLEME (TRAILING) MODÜLÜ ---
def pozisyon_takip(exchange, hafiza):
    degisiklik_var = False
    
    # Hafızadaki TÜM kayıtları gez
    keys = list(hafiza.keys()) # Kopyasını alıyoruz ki loop bozulmasın
    for key in keys:
        if "_" not in key: continue # Sistem ayarları (tarih vs) ise geç
        
        veri = hafiza[key]
        coin_full = key.split("_")[0] # BTC/USDT
        sinyal_tipi = veri.get('sinyal')
        giris_fiyati = veri.get('giris')
        zaman_str = veri.get('zaman')
        kilitlendi = veri.get('kilitlendi', False) # Zaten kilitledik mi?
        
        if not giris_fiyati or kilitlendi: continue

        # İşlem çok eskiyse (24 saatten fazla) takibi bırak
        islem_zamani = datetime.strptime(zaman_str, "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - islem_zamani).total_seconds() > 86400: continue

        try:
            # Güncel fiyatı çek
            ticker = exchange.fetch_ticker(coin_full)
            guncel_fiyat = ticker['last']
            
            # LONG İÇİN KONTROL
            if sinyal_tipi == "LONG 🟢":
                kar_orani = ((guncel_fiyat - giris_fiyati) / giris_fiyati) * 100
                if kar_orani >= KARI_KITLE_YUZDE:
                    telegram_gonder(f"🛡️ **RİSK SIFIRLANDI!** ({coin_full})\n\nFiyat %{kar_orani:.2f} yükseldi. Stop seviyesini **Giriş Fiyatına (Breakeven)** çek!\n\n💵 Giriş: {giris_fiyati}\n🚀 Şu an: {guncel_fiyat}")
                    hafiza[key]['kilitlendi'] = True
                    degisiklik_var = True
            
            # SHORT İÇİN KONTROL
            elif sinyal_tipi == "SHORT 🔴":
                kar_orani = ((giris_fiyati - guncel_fiyat) / giris_fiyati) * 100
                if kar_orani >= KARI_KITLE_YUZDE:
                    telegram_gonder(f"🛡️ **RİSK SIFIRLANDI!** ({coin_full})\n\nFiyat %{kar_orani:.2f} düştü. Stop seviyesini **Giriş Fiyatına (Breakeven)** çek!\n\n💵 Giriş: {giris_fiyati}\n📉 Şu an: {guncel_fiyat}")
                    hafiza[key]['kilitlendi'] = True
                    degisiklik_var = True
                    
        except:
            continue
            
    return degisiklik_var

# --- DİĞER FONKSİYONLAR (BEYİN) ---
def gecmis_hatalari_kontrol_et(hafiza, coin, suanki_fiyat):
    ilgili_kayitlar = [val for key, val in hafiza.items() if coin in key]
    if not ilgili_kayitlar: return False, ""

    son_islem = sorted(ilgili_kayitlar, key=lambda x: x['zaman'], reverse=True)[0]
    last_time = datetime.strptime(son_islem['zaman'], "%Y-%m-%d %H:%M:%S")
    
    if (datetime.now() - last_time) < timedelta(hours=CEZA_SURESI_SAAT):
        giris = float(son_islem.get('giris', 0))
        yon = son_islem.get('sinyal')
        if yon == "LONG 🟢" and suanki_fiyat < giris * 0.99: return True, "🚫 Bot terste, pas geçiyor."
        if yon == "SHORT 🔴" and suanki_fiyat > giris * 1.01: return True, "🚫 Bot terste, pas geçiyor."
    return False, ""

def spam_kontrol(hafiza, coin, sinyal, timeframe):
    key = f"{coin}_{timeframe}"
    if key in hafiza:
        son_veri = hafiza[key]
        last_signal = son_veri.get('sinyal')
        last_time = datetime.strptime(son_veri.get('zaman'), "%Y-%m-%d %H:%M:%S")
        if last_signal == sinyal and (datetime.now() - last_time) < timedelta(hours=HAFIZA_SURESI_SAAT):
            return True
    return False

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def btc_durumu(exchange):
    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        return ticker['percentage'], ticker['last']
    except:
        return 0, 0

def piyasa_duygusunu_olc():
    try:
        url = "https://cointelegraph.com/rss"
        feed = feedparser.parse(url)
        toplam = sum([TextBlob(e.title).sentiment.polarity for e in feed.entries[:7]])
        ort = toplam / 7
        return "POZITIF" if ort > 0.15 else ("NEGATIF" if ort < -0.15 else "NOTR")
    except:
        return "NOTR"

def teknik_analiz(exchange, coin, df, btc_degisim):
    df['ATR'] = df['high'] - df['low']
    son_fiyat = df['close'].iloc[-1]
    
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['rsi'] = calculate_rsi(df['close'])
    
    df['highest_20'] = df['high'].rolling(window=20).max().shift(1)
    df['lowest_20'] = df['low'].rolling(window=20).min().shift(1)
    
    hacim_ort = df['volume'].rolling(window=20).mean().iloc[-1]
    balina_notu = "🐋 **BALİNA ALARMI**" if df['volume'].iloc[-1] > (hacim_ort * 3.0) else ""

    sinyal = None
    tip = "Swing" if "4h" in str(df.name) else "Scalp"
    sl = 0.0
    tp = 0.0
    setup_info = ""

    current_rsi = df['rsi'].iloc[-1]
    ema20_val = df['ema20'].iloc[-1]
    ema50_val = df['ema50'].iloc[-1]

    # STRATEJİ (LONG)
    if ema20_val > ema50_val and 45 < current_rsi < 75 and btc_degisim > -3.0:
        if son_fiyat > df['highest_20'].iloc[-1]:
            sinyal, setup_info = "LONG 🟢", "BOS (Yapı Kırılımı)"
        elif abs(son_fiyat - ema50_val) / son_fiyat < 0.01:
            sinyal, setup_info = "LONG 🟢", "Trend Desteği (Retest)"
        
        if sinyal:
            sl = son_fiyat - (df['ATR'].iloc[-1] * 1.5)
            tp = son_fiyat + ((son_fiyat - sl) * RISK_REWARD_RATIO)

    # STRATEJİ (SHORT)
    elif ema20_val < ema50_val and 25 < current_rsi < 55:
        if son_fiyat < df['lowest_20'].iloc[-1]:
            sinyal, setup_info = "SHORT 🔴", "BOS (Aşağı Kırılım)"
        elif abs(son_fiyat - ema50_val) / son_fiyat < 0.01:
            sinyal, setup_info = "SHORT 🔴", "Trend Direnci (Retest)"
            
        if sinyal:
            sl = son_fiyat + (df['ATR'].iloc[-1] * 1.5)
            tp = son_fiyat - ((sl - son_fiyat) * RISK_REWARD_RATIO)

    return sinyal, tip, sl, tp, balina_notu, setup_info

# --- ANA MOTOR ---
def calistir():
    exchange = ccxt.binanceus() 
    market_duygusu = piyasa_duygusunu_olc()
    btc_degisim, btc_fiyat = btc_durumu(exchange)
    
    hafiza = hafiza_yukle()
    hafiza_degisti = False
    
    print(f"🌍 Piyasa: {market_duygusu} | BTC: ${btc_fiyat}")

    # 1. GÜNLÜK RAPOR KONTROLÜ
    if gunluk_rapor_kontrol(hafiza, market_duygusu, btc_fiyat):
        hafiza_degisti = True
        print("📅 Günlük rapor gönderildi.")

    # 2. AÇIK POZİSYON TAKİBİ (Trailing Stop)
    if pozisyon_takip(exchange, hafiza):
        hafiza_degisti = True
        print("🛡️ Pozisyon takibi yapıldı, güncellemeler var.")

    # 3. YENİ FIRSAT TARAMASI
    hedef_coinler = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'DOGE/USDT', 'LTC/USDT', 'LINK/USDT', 'XRP/USDT']
    raporlar = []

    for coin in hedef_coinler:
        for tf in TARAMA_PERIYOTLARI:
            try:
                bars = exchange.fetch_ohlcv(coin, timeframe=tf, limit=200)
                df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df.name = tf
                fiyat = df['close'].iloc[-1]

                hatali, msg = gecmis_hatalari_kontrol_et(hafiza, coin, fiyat)
                if hatali:
                    print(f"{msg} ({coin})")
                    continue 

                sinyal, tip, sl, tp, balina, setup = teknik_analiz(exchange, coin, df, btc_degisim)
                
                if sinyal:
                    if spam_kontrol(hafiza, coin, sinyal, tip):
                        print(f"🚫 SPAM: {coin} - Hafızada var.")
                        continue 

                    if (sinyal == "LONG 🟢" and market_duygusu == "NEGATIF") or (sinyal == "SHORT 🔴" and market_duygusu == "POZITIF"):
                        continue

                    # YENİ: GRAFİK LİNKİ HAZIRLAMA
                    symbol_clean = coin.replace('/', '') # BTCUSDT
                    chart_link = f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol_clean}"

                    mesaj = f"⚡ **NEUROTRADE {sinyal}** ({tip})\n\n"
                    mesaj += f"💎 **Coin:** #{coin.split('/')[0]}\n"
                    mesaj += f"🛠️ **Setup:** {setup}\n"
                    mesaj += f"💵 **Giriş:** ${fiyat:.4f}\n"
                    if balina: mesaj += f"{balina} 🚨\n"
                    mesaj += f"🛑 **Stop:** ${sl:.4f}\n"
                    mesaj += f"🎯 **Hedef:** ${tp:.4f}\n\n"
                    mesaj += f"📊 **Analiz:**\n"
                    mesaj += f"• 🧱 Market Yapısı: {'Kırılım (BOS)' if 'BOS' in setup else 'Retest'}\n"
                    mesaj += f"• 🌡️ RSI Modu: Uygun\n\n"
                    mesaj += f"🔗 [Grafiği İncele (TradingView)]({chart_link})"

                    raporlar.append(mesaj)
                    
                    hafiza[f"{coin}_{tip}"] = {
                        "sinyal": sinyal,
                        "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "giris": fiyat,
                        "kilitlendi": False 
                    }
                    hafiza_degisti = True
                    
                time.sleep(0.5)
            except Exception as e:
                print(f"Hata ({coin}): {e}")
                continue

    if raporlar:
        telegram_gonder("\n----------------------\n".join(raporlar))
    
    if hafiza_degisti:
        hafiza_kaydet(hafiza)
        print("💾 Hafıza Güncellendi (Rapor/Takip/Sinyal).")
    else:
        print("💤 Değişiklik yok.")

if __name__ == "__main__":
    calistir()
