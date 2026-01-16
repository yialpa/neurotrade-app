import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import feedparser
from textblob import TextBlob
import numpy as np
import json
import io
import mplfinance as mpf
from datetime import datetime, timedelta

# ==========================================
# 🦅 NEUROTRADE V8.0 - GÖRSEL ZEKA & MTF
# ==========================================

# --- KİŞİSEL AYARLAR ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# --- JSONBIN AYARLARI ---
JSONBIN_API_KEY = "$2a$10$5cOoQOZABAJQlhbFtkjyk.pTqcw9gawnwvTfznf59FTmprp/cffV6"
JSONBIN_BIN_ID = "696944b1d0ea881f406e6a0c"

# --- STRATEJİ AYARLARI ---
TARAMA_PERIYODU = '15m'       # İşlem periyodu
ANA_TREND_PERIYODU = '4h'     # Trend filtresi (Büyük Abi)
RISK_REWARD_RATIO = 2.0  
HAFIZA_SURESI_SAAT = 4   
CEZA_SURESI_SAAT = 6     
KARI_KITLE_YUZDE = 1.0   
TARANACAK_COIN_SAYISI = 40  

def telegram_foto_gonder(mesaj, resim_buffer):
    """Grafikli Mesaj Gönderir"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    files = {'photo': ('chart.png', resim_buffer, 'image/png')}
    data = {'chat_id': CHAT_ID, 'caption': mesaj, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, files=files, data=data)
    except Exception as e:
        print(f"Fotoğraf gönderme hatası: {e}")
        # Fotoğraf gitmezse normal mesaj dene
        telegram_gonder(mesaj)

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

# --- GRAFİK ÇİZİCİ (RESSAM MODÜLÜ) ---
def grafik_olustur(df, coin, sinyal, giris, stop, hedef):
    """Sinyal anındaki grafiği çizer ve belleğe kaydeder"""
    try:
        # Son 50 mumu al
        plot_df = df.tail(50).copy()
        plot_df.index = pd.DatetimeIndex(plot_df['timestamp'])
        
        # Çizgiler (Hlines)
        hlines = dict(hlines=[giris, stop, hedef], 
                      colors=['blue', 'red', 'green'], 
                      linewidths=[1, 1, 1],
                      linestyle='-')

        # Stil ayarları
        mc = mpf.make_marketcolors(up='green', down='red', edge='i', wick='i', volume='in', inherit=True)
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)

        # Belleğe kaydetmek için buffer
        buf = io.BytesIO()
        
        # Başlık
        title = f"\nNEUROTRADE AI - {coin} ({sinyal})"

        mpf.plot(plot_df, type='candle', style=s, title=title,
                 hlines=hlines, volume=False, savefig=buf)
        
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"Grafik çizim hatası: {e}")
        return None

# --- KUCOIN HACİM AVCISI ---
def en_iyi_coinleri_getir(exchange, limit=40):
    try:
        tickers = exchange.fetch_tickers()
        usdt_pairs = {
            symbol: data for symbol, data in tickers.items() 
            if symbol.endswith('/USDT') 
            and '3S' not in symbol and '3L' not in symbol 
            and 'UP' not in symbol and 'DOWN' not in symbol
        }
        sorted_pairs = sorted(usdt_pairs.items(), key=lambda x: x[1]['quoteVolume'] if x[1]['quoteVolume'] else 0, reverse=True)
        top_coins = [pair[0] for pair in sorted_pairs[:limit]]
        print(f"🔥 Hacim Avcısı: {len(top_coins)} coin seçildi.")
        return top_coins
    except:
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']

# --- MTF (MULTI TIMEFRAME) ANALİZİ ---
def ana_trend_kontrol(exchange, coin):
    """4 Saatlik grafiğe bakıp ana trendi söyler"""
    try:
        bars = exchange.fetch_ohlcv(coin, timeframe=ANA_TREND_PERIYODU, limit=50)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        ema50 = ta.ema(df['close'], length=50).iloc[-1]
        fiyat = df['close'].iloc[-1]
        
        if fiyat > ema50: return "YUKARI"
        else: return "ASAGI"
    except:
        return "NOTR" # Veri alamazsa engelleme

# --- GÜNLÜK RAPOR ---
def gunluk_rapor_kontrol(hafiza, market_duygusu, btc_fiyat):
    bugun = datetime.now().strftime("%Y-%m-%d")
    son_rapor = hafiza.get("son_rapor_tarihi", "")
    
    if son_rapor != bugun:
        mesaj = f"📅 **GÜNLÜK PATRON RAPORU**\n\n"
        mesaj += f"✅ **Sistem:** V8.0 (Visual Brain)\n"
        mesaj += f"📸 **Özellik:** Grafik Gönderimi Aktif\n"
        mesaj += f"⏳ **Filtre:** MTF (4H Trend) Kontrolü\n"
        mesaj += f"🌍 **Piyasa Modu:** {market_duygusu}\n"
        mesaj += f"👑 **BTC Fiyatı:** ${btc_fiyat:.2f}\n\n"
        mesaj += f"🦅 *Gözümle görmediğim işe girmem Kaptan.*"
        
        telegram_gonder(mesaj)
        hafiza["son_rapor_tarihi"] = bugun
        return True 
    return False

# --- KÂRI KİTLEME ---
def pozisyon_takip(exchange, hafiza):
    degisiklik_var = False
    keys = list(hafiza.keys()) 
    for key in keys:
        veri = hafiza[key]
        if not isinstance(veri, dict): continue 
        
        coin_full = key.split("_")[0] 
        sinyal_tipi = veri.get('sinyal')
        giris_fiyati = veri.get('giris')
        kilitlendi = veri.get('kilitlendi', False) 
        
        if not giris_fiyati or kilitlendi: continue

        try:
            ticker = exchange.fetch_ticker(coin_full)
            guncel_fiyat = ticker['last']
            
            if sinyal_tipi == "LONG 🟢":
                kar_orani = ((guncel_fiyat - giris_fiyati) / giris_fiyati) * 100
                if kar_orani >= KARI_KITLE_YUZDE:
                    telegram_gonder(f"🛡️ **RİSK SIFIRLANDI!** ({coin_full})\nFiyat %{kar_orani:.2f} yükseldi. Stop --> Giriş.")
                    hafiza[key]['kilitlendi'] = True
                    degisiklik_var = True
            elif sinyal_tipi == "SHORT 🔴":
                kar_orani = ((giris_fiyati - guncel_fiyat) / giris_fiyati) * 100
                if kar_orani >= KARI_KITLE_YUZDE:
                    telegram_gonder(f"🛡️ **RİSK SIFIRLANDI!** ({coin_full})\nFiyat %{kar_orani:.2f} düştü. Stop --> Giriş.")
                    hafiza[key]['kilitlendi'] = True
                    degisiklik_var = True
        except: continue
    return degisiklik_var

# --- ANALİZ MODÜLLERİ ---
def spam_kontrol(hafiza, coin, sinyal):
    key = f"{coin}_{sinyal}"
    if key in hafiza:
        son_veri = hafiza[key]
        if not isinstance(son_veri, dict): return False
        last_time = datetime.strptime(son_veri.get('zaman'), "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - last_time) < timedelta(hours=HAFIZA_SURESI_SAAT):
            return True
    return False

def teknik_analiz(coin, df, ana_trend):
    # ATR Hesapla
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    son_fiyat = df['close'].iloc[-1]
    
    # EMA Hesapla
    df['ema50'] = ta.ema(df['close'], length=50)
    df['ema20'] = ta.ema(df['close'], length=20)
    df['rsi'] = ta.rsi(df['close'], length=14)
    
    # BOS Seviyeleri
    df['highest_20'] = df['high'].rolling(window=20).max().shift(1)
    df['lowest_20'] = df['low'].rolling(window=20).min().shift(1)
    
    sinyal = None
    sl = 0.0
    tp = 0.0
    setup_info = ""

    current_rsi = df['rsi'].iloc[-1]
    ema20_val = df['ema20'].iloc[-1]
    ema50_val = df['ema50'].iloc[-1]

    # --- LONG STRATEJİSİ ---
    # 1. Ana Trend (4H) YUKARI olmalı (MTF Kuralı)
    # 2. 15m'de Trend Yukarı olmalı
    if ana_trend == "YUKARI" and ema20_val > ema50_val and 45 < current_rsi < 70:
        # BOS veya Retest
        if son_fiyat > df['highest_20'].iloc[-1]:
            sinyal, setup_info = "LONG 🟢", "BOS (Yukarı Kırılım)"
        elif abs(son_fiyat - ema50_val) / son_fiyat < 0.01:
            sinyal, setup_info = "LONG 🟢", "Trend Desteği (Retest)"
        
        if sinyal:
            sl = son_fiyat - (df['ATR'].iloc[-1] * 1.5)
            tp = son_fiyat + ((son_fiyat - sl) * RISK_REWARD_RATIO)

    # --- SHORT STRATEJİSİ ---
    # 1. Ana Trend (4H) AŞAĞI olmalı (MTF Kuralı)
    # 2. 15m'de Trend Aşağı olmalı
    elif ana_trend == "ASAGI" and ema20_val < ema50_val and 30 < current_rsi < 55:
        if son_fiyat < df['lowest_20'].iloc[-1]:
            sinyal, setup_info = "SHORT 🔴", "BOS (Aşağı Kırılım)"
        elif abs(son_fiyat - ema50_val) / son_fiyat < 0.01:
            sinyal, setup_info = "SHORT 🔴", "Trend Direnci (Retest)"
        
        if sinyal:
            sl = son_fiyat + (df['ATR'].iloc[-1] * 1.5)
            tp = son_fiyat - ((sl - son_fiyat) * RISK_REWARD_RATIO)

    return sinyal, sl, tp, setup_info

# --- ANA MOTOR ---
def calistir():
    exchange = ccxt.kucoin()
    print("🦅 NEUROTRADE V8.0 (Visual Brain) Başlatılıyor...")
    
    # Basit Duygu Analizi (RSS)
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss")
        score = sum([TextBlob(e.title).sentiment.polarity for e in feed.entries[:5]])
        market_duygusu = "POZITIF" if score > 0.1 else ("NEGATIF" if score < -0.1 else "NOTR")
    except:
        market_duygusu = "NOTR"

    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        btc_fiyat = ticker['last']
    except:
        btc_fiyat = 0
    
    hafiza = hafiza_yukle()
    hafiza_degisti = False
    
    hedef_coinler = en_iyi_coinleri_getir(exchange, limit=TARANACAK_COIN_SAYISI)
    
    if gunluk_rapor_kontrol(hafiza, market_duygusu, btc_fiyat):
        hafiza_degisti = True

    if pozisyon_takip(exchange, hafiza):
        hafiza_degisti = True

    print(f"🔭 Tarama Başlıyor ({len(hedef_coinler)} Coin)...")

    for coin in hedef_coinler:
        try:
            # 1. ADIM: Büyük Resme Bak (4H Trend)
            ana_trend = ana_trend_kontrol(exchange, coin)
            
            # 2. ADIM: Küçük Resme Bak (15m İşlem)
            bars = exchange.fetch_ohlcv(coin, timeframe=TARAMA_PERIYODU, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') # Grafik için tarih formatı
            
            sinyal, sl, tp, setup = teknik_analiz(coin, df, ana_trend)
            
            if sinyal:
                if spam_kontrol(hafiza, coin, sinyal):
                    print(f"🚫 SPAM: {coin}")
                    continue 
                
                # Haber Filtresi
                if (sinyal == "LONG 🟢" and market_duygusu == "NEGATIF") or (sinyal == "SHORT 🔴" and market_duygusu == "POZITIF"):
                    continue

                fiyat = df['close'].iloc[-1]
                sl_yuzde = abs((fiyat - sl) / fiyat) * 100
                tp_yuzde = abs((tp - fiyat) / fiyat) * 100
                
                # MESAJI HAZIRLA
                chart_link = f"https://www.tradingview.com/chart/?symbol=KUCOIN:{coin.replace('/', '')}"
                mesaj = f"⚡ **NEUROTRADE {sinyal}**\n\n"
                mesaj += f"💎 **Coin:** #{coin.split('/')[0]} (KuCoin)\n"
                mesaj += f"🛠️ **Setup:** {setup}\n"
                mesaj += f"⏳ **Ana Trend (4H):** {ana_trend}\n\n"
                mesaj += f"💵 **Giriş:** ${fiyat:.4f}\n"
                mesaj += f"🛑 **Stop:** ${sl:.4f} (%{sl_yuzde:.2f})\n"
                mesaj += f"🎯 **Hedef:** ${tp:.4f} (%{tp_yuzde:.2f})\n\n"
                mesaj += f"📊 [TV Grafiği]({chart_link})"

                # 3. ADIM: GRAFİĞİ ÇİZ VE GÖNDER 📸
                print(f"📸 Grafik çiziliyor: {coin}...")
                grafik_buffer = grafik_olustur(df, coin, sinyal, fiyat, sl, tp)
                
                if grafik_buffer:
                    telegram_foto_gonder(mesaj, grafik_buffer)
                else:
                    telegram_gonder(mesaj)
                
                # Hafızaya Kaydet
                hafiza[f"{coin}_{sinyal}"] = {
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
    
    if hafiza_degisti:
        hafiza_kaydet(hafiza)
        print("💾 Hafıza Güncellendi.")
    else:
        print("💤 Değişiklik yok.")

if __name__ == "__main__":
    calistir()
