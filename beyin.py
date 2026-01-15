import ccxt
import pandas as pd
import requests
import time

# --- AYARLAR (Buraları Doldur) ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

TARANACAK_COINLER = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
    'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT'
]

def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': mesaj, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload)
    except:
        pass

# --- PANDAS-TA YERİNE KENDİ MATEMATİĞİMİZ ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def analiz_et():
    # Hata almamak için Kraken (Daha esnek)
    exchange = ccxt.kraken()
    
    rapor = "🤖 *NEUROTRADE OTOMATİK RAPOR*\n\n"
    firsat_var = False

    for coin in TARANACAK_COINLER:
        try:
            # BinanceUS sembolleri için geçici çözüm
            if coin == 'BTC/USDT': coin_pair = 'BTC/USD' 
            else: coin_pair = coin.replace('USDT', 'USD') # Kraken genelde USD kullanır

            bars = exchange.fetch_ohlcv(coin_pair, timeframe='4h', limit=50)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # --- MANUEL HESAPLAMA ---
            # RSI Hesapla
            df['RSI'] = calculate_rsi(df['close'], 14)
            # EMA Hesapla (Pandas'ın içinde zaten var)
            df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
            
            rsi = df['RSI'].iloc[-1]
            fiyat = df['close'].iloc[-1]
            
            # Sinyal Kontrolü
            if rsi < 30:
                rapor += f"🟢 **{coin}**\nFiyat: ${fiyat:.2f}\nDurum: AŞIRI SATIM (RSI {rsi:.1f}) -> Dönüş Olabilir!\n\n"
                firsat_var = True
            elif rsi > 70:
                rapor += f"🔴 **{coin}**\nFiyat: ${fiyat:.2f}\nDurum: AŞIRI ALIM (RSI {rsi:.1f}) -> Düşebilir!\n\n"
                firsat_var = True
                
            time.sleep(1) 
            
        except Exception as e:
            # Hata olursa pas geç, loga yazma
            continue

    if firsat_var:
        telegram_gonder(rapor + "⚠️ _Yatırım tavsiyesi değildir._")
    else:
        print("Fırsat yok, sessiz mod.")

if __name__ == "__main__":
    analiz_et()
