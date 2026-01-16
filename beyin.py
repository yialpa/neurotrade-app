import ccxt
import pandas as pd
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
# 🦅 NEUROTRADE V12.0 - STRUCTURE SAFE
# ==========================================

# --- KİŞİSEL AYARLAR ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# --- JSONBIN AYARLARI ---
JSONBIN_API_KEY = "$2a$10$5cOoQOZABAJQlhbFtkjyk.pTqcw9gawnwvTfznf59FTmprp/cffV6"
JSONBIN_BIN_ID = "696944b1d0ea881f406e6a0c"

# --- STRATEJİ VE RİSK AYARLARI ---
TARAMA_PERIYODU = '15m'       
ANA_TREND_PERIYODU = '4h'     
RISK_REWARD_RATIO = 2.0  
HAFIZA_SURESI_SAAT = 4   
KARI_KITLE_YUZDE = 1.0   
TARANACAK_COIN_SAYISI = 40

# 🔥 YENİ RİSK AYARLARI
MAX_STOP_YUZDESI = 2.0   # Stop mesafesi %2'den fazlaysa işlemi iptal et
STOP_BUFFER = 0.005      # Destek/Direnç arkasına %0.5 pay bırak (Stop Hunt yememek için)

# --- TELEGRAM FONKSİYONLARI ---
def telegram_foto_gonder(mesaj, resim_buffer):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    files = {'photo': ('chart.png', resim_buffer, 'image/png')}
    data = {'chat_id': CHAT_ID, 'caption': mesaj, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, files=files, data=data)
    except:
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

# --- HABER ANALİZİ ---
def piyasa_haber_analizi():
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss")
        total_score = 0
        bullish_keywords = ['etf', 'approve', 'launch', 'record', 'bull', 'adoption']
        bearish_keywords = ['sec', 'ban', 'hack', 'sued', 'crash', 'delist', 'prison']
        
        for entry in feed.entries[:7]:
            title = entry.title.lower()
            sentiment = TextBlob(entry.title).sentiment.polarity
            if any(k in title for k in bullish_keywords): sentiment += 0.5
            if any(k in title for k in bearish_keywords): sentiment -= 0.5
            total_score += sentiment

        if total_score > 0.5: return "POZITIF"
        elif total_score < -0.5: return "NEGATIF"
        else: return "NOTR"
    except:
        return "NOTR"

# --- TEKNİK GÖSTERGELER ---
def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(window=period).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- MUM & GRAFİK FORMASYONLARI ---
def detect_candle_patterns(df):
    row = df.iloc[-1]
    body = abs(row['close'] - row['open'])
    wick_upper = row['high'] - max(row['close'], row['open'])
    wick_lower = min(row['close'], row['open']) - row['low']
    total_len = row['high'] - row['low']
    
    if body <= total_len * 0.1: return "DOJI (Kararsızlık)"
    if wick_lower > (body * 2) and wick_upper < body: return "HAMMER (Boğa Çekici)"
    if body > total_len * 0.8: return "MARUBOZU (Güçlü Mum)"
    return None

def detect_chart_patterns(df):
    closes = df['close'].values
    lows = df['low'].values
    
    direk_boyu = closes[-15] - closes[-25]
    kanal_hareketi = closes[-1] - closes[-10]
    if direk_boyu > (closes[-25] * 0.03) and abs(kanal_hareketi) < (direk_boyu * 0.3):
         return "BOĞA FLAMASI (Bull Flag)"

    try:
        p1 = min(lows[-30:-20]) 
        p2 = min(lows[-20:-10]) 
        p3 = min(lows[-10:])    
        if p2 < p1 and p2 < p3 and p3 > p2:
            if abs(p1 - p3) / p1 < 0.02: return "TOBO (Dönüş Formasyonu)"
    except: pass
    return None

# --- SMART MONEY KONSEPTLERİ ---
def detect_fvg(df):
    try:
        if df['low'].iloc[-2] > df['high'].iloc[-4]: return "BULLISH_FVG"
        elif df['high'].iloc[-2] < df['low'].iloc[-4]: return "BEARISH_FVG"
    except: pass
    return None

def detect_order_block(df):
    try:
        last_candle_green = df['close'].iloc[-1] > df['open'].iloc[-1]
        prev_candle_red = df['close'].iloc[-2] < df['open'].iloc[-2]
        strong_move = abs(df['close'].iloc[-1] - df['open'].iloc[-1]) > (df['ATR'].iloc[-1] * 1.5)
        if last_candle_green and prev_candle_red and strong_move: return "BULLISH_OB"
        
        last_candle_red = df['close'].iloc[-1] < df['open'].iloc[-1]
        prev_candle_green = df['close'].iloc[-2] > df['open'].iloc[-2]
        if last_candle_red and prev_candle_green and strong_move: return "BEARISH_OB"
    except: pass
    return None

# --- GRAFİK ÇİZİCİ ---
def grafik_olustur(df, coin, sinyal, giris, stop, hedef):
    try:
        plot_df = df.tail(50).copy()
        plot_df.index = pd.DatetimeIndex(plot_df['timestamp'])
        hlines = dict(hlines=[giris, stop, hedef], colors=['blue', 'red', 'green'], linewidths=[1, 1, 1], linestyle='-')
        mc = mpf.make_marketcolors(up='green', down='red', edge='i', wick='i', volume='in', inherit=True)
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
        buf = io.BytesIO()
        title = f"\nNEUROTRADE AI - {coin} ({sinyal})"
        mpf.plot(plot_df, type='candle', style=s, title=title, hlines=hlines, volume=False, savefig=buf)
        buf.seek(0)
        return buf
    except: return None

# --- HACİM VE TREND ---
def en_iyi_coinleri_getir(exchange, limit=40):
    try:
        tickers = exchange.fetch_tickers()
        usdt_pairs = {s: d for s, d in tickers.items() if s.endswith('/USDT') and '3S' not in s and '3L' not in s}
        sorted_pairs = sorted(usdt_pairs.items(), key=lambda x: x[1]['quoteVolume'] if x[1]['quoteVolume'] else 0, reverse=True)
        return [pair[0] for pair in sorted_pairs[:limit]]
    except: return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']

def ana_trend_kontrol(exchange, coin):
    try:
        bars = exchange.fetch_ohlcv(coin, timeframe=ANA_TREND_PERIYODU, limit=50)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        fiyat = df['close'].iloc[-1]
        return "YUKARI" if fiyat > ema50 else "ASAGI"
    except: return "NOTR"

# --- SPAM ENGELLEYİCİ ---
def spam_kontrol(hafiza, coin, sinyal):
    key = f"{coin}_{sinyal}"
    if key in hafiza:
        son_veri = hafiza[key]
        if not isinstance(son_veri, dict): return False
        last_time = datetime.strptime(son_veri.get('zaman'), "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - last_time) < timedelta(hours=HAFIZA_SURESI_SAAT): return True
    return False

# --- ANA ANALİZ MOTORU ---
def teknik_analiz(coin, df, ana_trend):
    df['ATR'] = calculate_atr(df)
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['rsi'] = calculate_rsi(df['close'])
    
    # 🔥 DESTEK / DİRENÇ (SWING POINTS) HESAPLAMA
    # Son 20 mumun en düşüğü (Destek) ve en yükseği (Direnç)
    swing_low = df['low'].rolling(window=20).min().iloc[-1]
    swing_high = df['high'].rolling(window=20).max().iloc[-1]
    
    # BOS Kontrolü için bir önceki tepeler
    df['highest_20'] = df['high'].rolling(window=20).max().shift(1)
    df['lowest_20'] = df['low'].rolling(window=20).min().shift(1)
    
    son_fiyat = df['close'].iloc[-1]
    
    # FORMASYONLAR
    mum_formasyonu = detect_candle_patterns(df)
    grafik_formasyonu = detect_chart_patterns(df)
    fvg_durumu = detect_fvg(df)
    ob_durumu = detect_order_block(df)
    
    sinyal = None
    sl = 0.0
    tp = 0.0
    setup_info = ""
    ek_notlar = []

    if mum_formasyonu: ek_notlar.append(mum_formasyonu)
    if grafik_formasyonu: ek_notlar.append(grafik_formasyonu)

    current_rsi = df['rsi'].iloc[-1]

    # --- LONG SİNYALLERİ ---
    if ana_trend == "YUKARI" and 45 < current_rsi < 70:
        if grafik_formasyonu == "TOBO (Dönüş Formasyonu)": sinyal, setup_info = "LONG 🟢", "TOBO Formasyonu"
        elif grafik_formasyonu == "BOĞA FLAMASI (Bull Flag)": sinyal, setup_info = "LONG 🟢", "Boğa Flaması"
        elif ob_durumu == "BULLISH_OB": sinyal, setup_info = "LONG 🟢", "Order Block (Kale)"
        elif fvg_durumu == "BULLISH_FVG": sinyal, setup_info = "LONG 🟢", "FVG (Boşluk Doldurma)"
        elif son_fiyat > df['highest_20'].iloc[-1]: sinyal, setup_info = "LONG 🟢", "BOS (Yukarı Kırılım)"
        
        if sinyal:
            # 🔥 YENİ STOP MANTIĞI: Destek Altı + Buffer
            # Stopu swing low'un altına koyuyoruz, ATR yerine market yapısı kullanıyoruz
            teknik_stop = swing_low * (1 - STOP_BUFFER) 
            sl = teknik_stop
            tp = son_fiyat + ((son_fiyat - sl) * RISK_REWARD_RATIO)

    # --- SHORT SİNYALLERİ ---
    elif ana_trend == "ASAGI" and 30 < current_rsi < 55:
        if ob_durumu == "BEARISH_OB": sinyal, setup_info = "SHORT 🔴", "Order Block (Kale)"
        elif fvg_durumu == "BEARISH_FVG": sinyal, setup_info = "SHORT 🔴", "FVG (Boşluk Doldurma)"
        elif son_fiyat < df['lowest_20'].iloc[-1]: sinyal, setup_info = "SHORT 🔴", "BOS (Aşağı Kırılım)"
        
        if sinyal:
            # 🔥 YENİ STOP MANTIĞI: Direnç Üstü + Buffer
            teknik_stop = swing_high * (1 + STOP_BUFFER)
            sl = teknik_stop
            tp = son_fiyat - ((sl - son_fiyat) * RISK_REWARD_RATIO)

    # 🔥 RİSK FİLTRESİ: Stop çok uzaksa işlemi iptal et
    if sinyal and sl > 0:
        stop_mesafesi_yuzde = abs((son_fiyat - sl) / son_fiyat) * 100
        if stop_mesafesi_yuzde > MAX_STOP_YUZDESI:
            # Risk uyarısı ile boş dönüyoruz (Console'a yazar ama Telegram atmaz)
            return None, 0, 0, f"RİSKLİ ({stop_mesafesi_yuzde:.2f}%)", ""

    return sinyal, sl, tp, setup_info, ", ".join(ek_notlar)

# --- RAPORLAMA ---
def gunluk_rapor_kontrol(hafiza, market_duygusu, btc_fiyat):
    bugun = datetime.now().strftime("%Y-%m-%d")
    son_rapor = hafiza.get("son_rapor_tarihi", "")
    if son_rapor != bugun:
        mesaj = f"📅 **GÜNLÜK PATRON RAPORU**\n\n"
        mesaj += f"✅ **Sistem:** V12.0 (Structure Safe)\n"
        mesaj += f"🛡️ **Güvenlik:** Market Yapısı Stopu + Max Risk Filtresi\n"
        mesaj += f"📐 **Analiz:** Formasyon + Smart Money + Haber\n"
        mesaj += f"🌍 **Mod:** {market_duygusu}\n"
        mesaj += f"👑 **BTC:** ${btc_fiyat:.2f}\n"
        telegram_gonder(mesaj)
        hafiza["son_rapor_tarihi"] = bugun
        return True 
    return False

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

def spam_kontrol(hafiza, coin, sinyal):
    key = f"{coin}_{sinyal}"
    if key in hafiza:
        son_veri = hafiza[key]
        if not isinstance(son_veri, dict): return False
        last_time = datetime.strptime(son_veri.get('zaman'), "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - last_time) < timedelta(hours=HAFIZA_SURESI_SAAT): return True
    return False

# --- ANA MOTOR ---
def calistir():
    exchange = ccxt.kucoin()
    print("🦅 NEUROTRADE V12.0 (Structure Safe) Başlatılıyor...")
    market_duygusu = piyasa_haber_analizi()
    
    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        btc_fiyat = ticker['last']
    except: btc_fiyat = 0
    
    hafiza = hafiza_yukle()
    hafiza_degisti = False
    
    hedef_coinler = en_iyi_coinleri_getir(exchange, limit=TARANACAK_COIN_SAYISI)
    if gunluk_rapor_kontrol(hafiza, market_duygusu, btc_fiyat): hafiza_degisti = True
    if pozisyon_takip(exchange, hafiza): hafiza_degisti = True

    print(f"🔭 Taranıyor: {len(hedef_coinler)} Coin | Mod: {market_duygusu}")

    for coin in hedef_coinler:
        try:
            ana_trend = ana_trend_kontrol(exchange, coin)
            bars = exchange.fetch_ohlcv(coin, timeframe=TARAMA_PERIYODU, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Teknik Analiz (Risk Filtreli)
            sinyal, sl, tp, setup, ek_notlar = teknik_analiz(coin, df, ana_trend)
            
            if sinyal: # Eğer sinyal varsa (Ve risk filtresine takılmadıysa)
                if spam_kontrol(hafiza, coin, sinyal): continue 
                if (sinyal == "LONG 🟢" and market_duygusu == "NEGATIF"): continue
                if (sinyal == "SHORT 🔴" and market_duygusu == "POZITIF"): continue

                fiyat = df['close'].iloc[-1]
                sl_yuzde = abs((fiyat - sl) / fiyat) * 100
                tp_yuzde = abs((tp - fiyat) / fiyat) * 100
                chart_link = f"https://www.tradingview.com/chart/?symbol=KUCOIN:{coin.replace('/', '')}"
                
                mesaj = f"⚡ **NEUROTRADE {sinyal}**\n\n"
                mesaj += f"💎 **Coin:** #{coin.split('/')[0]} (KuCoin)\n"
                mesaj += f"🛠️ **Setup:** {setup}\n"
                if ek_notlar: mesaj += f"🕯️ **Mum/Formasyon:** {ek_notlar}\n"
                mesaj += f"⏳ **Ana Trend (4H):** {ana_trend}\n\n"
                mesaj += f"💵 **Giriş:** ${fiyat:.4f}\n"
                mesaj += f"🛑 **Teknik Stop:** ${sl:.4f} (%{sl_yuzde:.2f})\n"
                mesaj += f"🎯 **Hedef:** ${tp:.4f} (%{tp_yuzde:.2f})\n\n"
                mesaj += f"⚠️ *Not: Stop noktası en yakın destek/direnç arkasıdır.*"

                print(f"📸 Sinyal: {coin} - {setup}")
                grafik_buffer = grafik_olustur(df, coin, sinyal, fiyat, sl, tp)
                if grafik_buffer: telegram_foto_gonder(mesaj, grafik_buffer)
                else: telegram_gonder(mesaj)
                
                hafiza[f"{coin}_{sinyal}"] = {
                    "sinyal": sinyal, "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "giris": fiyat, "kilitlendi": False 
                }
                hafiza_degisti = True
            
            # Eğer riskli olduğu için sinyal dönmediyse loga yaz
            elif setup and "RİSKLİ" in setup:
                print(f"🚫 {coin} - {setup} - Setup var ama Stop çok uzak.")

            time.sleep(0.5) 
        except: continue
    
    if hafiza_degisti: hafiza_kaydet(hafiza)

if __name__ == "__main__":
    calistir()
