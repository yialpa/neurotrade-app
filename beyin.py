import ccxt
import pandas as pd
import requests
import time
import feedparser
from textblob import TextBlob
import numpy as np
import json
from datetime import datetime, timedelta

# ==========================================
# 🦅 NEUROTRADE V7.6 - KUCOIN GEM HUNTER
# ==========================================
# NOT: GitHub (ABD) sunucularında Binance Global çalışmaz.
# Bu yüzden Binance Global kadar güçlü ve hacimli olan KUCOIN'e geçtik.

# --- KİŞİSEL AYARLAR ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# --- JSONBIN AYARLARI ---
JSONBIN_API_KEY = "$2a$10$5cOoQOZABAJQlhbFtkjyk.pTqcw9gawnwvTfznf59FTmprp/cffV6"
JSONBIN_BIN_ID = "696944b1d0ea881f406e6a0c"

# --- STRATEJİ AYARLARI ---
TARAMA_PERIYOTLARI = ['15m', '1h']  
RISK_REWARD_RATIO = 2.0  
HAFIZA_SURESI_SAAT = 4   
CEZA_SURESI_SAAT = 6     
KARI_KITLE_YUZDE = 1.0   
TARANACAK_COIN_SAYISI = 40  # KuCoin'de çok coin var, 40 tane tarayalım 🔥

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

# --- HACİM AVCI MODÜLÜ (KUCOIN) ---
def en_iyi_coinleri_getir(exchange, limit=40):
    """KuCoin üzerindeki en yüksek hacimli USDT paritelerini çeker."""
    try:
        # KuCoin bazen API'de farklı davranabilir, güvenli çekim
        tickers = exchange.fetch_tickers()
        usdt_pairs = {
            symbol: data for symbol, data in tickers.items() 
            if symbol.endswith('/USDT') 
            and 'USDC' not in symbol 
            and 'DAI' not in symbol
            and '3S' not in symbol # Kaldıraçlı tokenları temizle
            and '3L' not in symbol
        }
        
        # Quote Volume (İşlem Hacmi) değerine göre sırala
        sorted_pairs = sorted(usdt_pairs.items(), key=lambda x: x[1]['quoteVolume'] if x[1]['quoteVolume'] else 0, reverse=True)
        
        # En çok işlem gören 'limit' kadar coini al
        top_coins = [pair[0] for pair in sorted_pairs[:limit]]
        print(f"🔥 Hacim Avcısı (KuCoin): En popüler {len(top_coins)} coin seçildi.")
        return top_coins
    except Exception as e:
        print(f"Coin listesi alınamadı: {e}")
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'KAS/USDT', 'FET/USDT', 'RNDR/USDT', 'PEPE/USDT']

# --- GÜNLÜK RAPOR ---
def gunluk_rapor_kontrol(hafiza, market_duygusu, btc_fiyat, taranan_sayisi):
    bugun = datetime.now().strftime("%Y-%m-%d")
    son_rapor = hafiza.get("son_rapor_tarihi", "")
    
    if son_rapor != bugun:
        mesaj = f"📅 **GÜNLÜK PATRON RAPORU**\n\n"
        mesaj += f"✅ **Sistem:** Aktif (V7.6 Gem Hunter)\n"
        mesaj += f"💎 **Borsa:** KuCoin (Yüksek Hacim)\n"
        mesaj += f"🔭 **Kapsama:** Top {taranan_sayisi} Coin\n"
        mesaj += f"🌍 **Piyasa Modu:** {market_duygusu}\n"
        mesaj += f"👑 **BTC Fiyatı:** ${btc_fiyat:.2f}\n"
        mesaj += f"🛡️ **Güvenlik:** ATR Stop Devrede\n\n"
        mesaj += f"🦅 *Binance Global kadar güçlü, GitHub dostu.*"
        
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
        zaman_str = veri.get('zaman')
        kilitlendi = veri.get('kilitlendi', False) 
        
        if not giris_fiyati or kilitlendi: continue

        try:
            islem_zamani = datetime.strptime(zaman_str, "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - islem_zamani).total_seconds() > 86400: continue
        except: continue

        try:
            ticker = exchange.fetch_ticker(coin_full)
            guncel_fiyat = ticker['last']
            
            if sinyal_tipi == "LONG 🟢":
                kar_orani = ((guncel_fiyat - giris_fiyati) / giris_fiyati) * 100
                if kar_orani >= KARI_KITLE_YUZDE:
                    telegram_gonder(f"🛡️ **RİSK SIFIRLANDI!** ({coin_full})\n\nFiyat %{kar_orani:.2f} yükseldi. Stop --> Giriş.\n🚀 Şu an: {guncel_fiyat}")
                    hafiza[key]['kilitlendi'] = True
                    degisiklik_var = True
            elif sinyal_tipi == "SHORT 🔴":
                kar_orani = ((giris_fiyati - guncel_fiyat) / giris_fiyati) * 100
                if kar_orani >= KARI_KITLE_YUZDE:
                    telegram_gonder(f"🛡️ **RİSK SIFIRLANDI!** ({coin_full})\n\nFiyat %{kar_orani:.2f} düştü. Stop --> Giriş.\n📉 Şu an: {guncel_fiyat}")
                    hafiza[key]['kilitlendi'] = True
                    degisiklik_var = True
        except: continue
    return degisiklik_var

# --- ANALİZ MODÜLLERİ ---
def gecmis_hatalari_kontrol_et(hafiza, coin, suanki_fiyat):
    ilgili_kayitlar = [val for key, val in hafiza.items() if coin in key and isinstance(val, dict)]
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
        if not isinstance(son_veri, dict): return False
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
    tip = "Swing" if "1h" in str(df.name) else "Scalp"
    sl = 0.0
    tp = 0.0
    setup_info = ""

    current_rsi = df['rsi'].iloc[-1]
    ema20_val = df['ema20'].iloc[-1]
    ema50_val = df['ema50'].iloc[-1]

    if ema20_val > ema50_val and 45 < current_rsi < 75 and btc_degisim > -3.0:
        if son_fiyat > df['highest_20'].iloc[-1]:
            sinyal, setup_info = "LONG 🟢", "BOS (Yapı Kırılımı)"
        elif abs(son_fiyat - ema50_val) / son_fiyat < 0.01:
            sinyal, setup_info = "LONG 🟢", "Trend Desteği (Retest)"
        if sinyal:
            sl = son_fiyat - (df['ATR'].iloc[-1] * 1.5)
            tp = son_fiyat + ((son_fiyat - sl) * RISK_REWARD_RATIO)

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
    # 🔥 DEĞİŞİKLİK: KuCoin kullanıyoruz. ABD sunucusunda çalışır ve hacmi yüksektir.
    exchange = ccxt.kucoin()
    print("🦅 NEUROTRADE AI (V7.6 - KuCoin Mode) Başlatılıyor...")
    
    market_duygusu = piyasa_duygusunu_olc()
    
    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        btc_fiyat = ticker['last']
        btc_degisim = ticker['percentage']
    except:
        btc_fiyat = 0
        btc_degisim = 0
    
    hafiza = hafiza_yukle()
    hafiza_degisti = False
    
    # 🔥 KuCoin'deki En Hacimli 40 Coin
    hedef_coinler = en_iyi_coinleri_getir(exchange, limit=TARANACAK_COIN_SAYISI)
    
    print(f"🌍 Piyasa: {market_duygusu} | BTC: ${btc_fiyat}")
    print(f"🔭 Taranan Coin Sayısı: {len(hedef_coinler)}")

    if gunluk_rapor_kontrol(hafiza, market_duygusu, btc_fiyat, len(hedef_coinler)):
        hafiza_degisti = True
        print("📅 Günlük rapor gönderildi.")

    if pozisyon_takip(exchange, hafiza):
        hafiza_degisti = True
        print("🛡️ Pozisyon takibi yapıldı.")

    raporlar = []
    for coin in hedef_coinler:
        for tf in TARAMA_PERIYOTLARI:
            try:
                # KuCoin'de limit biraz daha düşük olabilir, 100 mum yeterli
                bars = exchange.fetch_ohlcv(coin, timeframe=tf, limit=100)
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
                        print(f"🚫 SPAM: {coin}")
                        continue 

                    if (sinyal == "LONG 🟢" and market_duygusu == "NEGATIF") or (sinyal == "SHORT 🔴" and market_duygusu == "POZITIF"):
                        continue

                    # KuCoin linki farklıdır, onu düzelttik
                    symbol_clean = coin.replace('/', '-').replace('USDT', 'USDT') 
                    # KuCoin grafiği TradingView'da da var, genel linki kullanalım
                    chart_link = f"https://www.tradingview.com/chart/?symbol=KUCOIN:{coin.replace('/', '')}"

                    sl_percent = abs((fiyat - sl) / fiyat) * 100
                    tp_percent = abs((tp - fiyat) / fiyat) * 100

                    mesaj = f"⚡ **NEUROTRADE {sinyal}** ({tip})\n\n"
                    mesaj += f"💎 **Coin:** #{coin.split('/')[0]} (KuCoin)\n"
                    mesaj += f"🛠️ **Setup:** {setup}\n"
                    mesaj += f"💵 **Giriş:** ${fiyat:.4f}\n"
                    if balina: mesaj += f"{balina} 🚨\n"
                    mesaj += f"🛑 **Stop:** ${sl:.4f} (%{sl_percent:.2f})\n"
                    mesaj += f"🎯 **Hedef:** ${tp:.4f} (%{tp_percent:.2f})\n\n"
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
                    
                time.sleep(0.2) 
            except Exception as e:
                print(f"Hata ({coin}): {e}")
                continue

    if raporlar:
        telegram_gonder("\n----------------------\n".join(raporlar))
    
    if hafiza_degisti:
        hafiza_kaydet(hafiza)
        print("💾 Hafıza Güncellendi.")
    else:
        print("💤 Değişiklik yok.")

if __name__ == "__main__":
    calistir()
