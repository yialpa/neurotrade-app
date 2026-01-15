import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time

# --- AYARLAR (Buraları Kendi Bilgilerinle Doldur) ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc"  # BotFather'dan aldığın uzun kod
CHAT_ID = "-1003516806415"       # -100 ile başlayan numara

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

def analiz_et():
    # Binance US veya Kraken (Hız limiti yememek için)
    exchange = ccxt.kraken()
    
    rapor = "🤖 *NEUROTRADE OTOMATİK RAPOR*\n\n"
    firsat_var = False

    for coin in TARANACAK_COINLER:
        try:
            # Kraken sembol düzeltmesi (ETH/USDT -> ETH/USD gibi basit mapleme gerekebilir ama şimdilik direct deniyoruz)
            # Daha garanti olsun diye BinanceUS Rate Limitli kullanıyoruz
            exchange = ccxt.binanceus({'enableRateLimit': True})
            
            bars = exchange.fetch_ohlcv(coin, timeframe='4h', limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # RSI Hesapla
            rsi = df.ta.rsi(length=14).iloc[-1]
            fiyat = df['close'].iloc[-1]
            
            # Sinyal Kontrolü
            if rsi < 30:
                rapor += f"🟢 **{coin}**\nFiyat: ${fiyat}\nDurum: AŞIRI SATIM (RSI {rsi:.1f}) -> Dönüş Olabilir!\n\n"
                firsat_var = True
            elif rsi > 70:
                rapor += f"🔴 **{coin}**\nFiyat: ${fiyat}\nDurum: AŞIRI ALIM (RSI {rsi:.1f}) -> Düşebilir!\n\n"
                firsat_var = True
                
            time.sleep(1) # Kibar ol, sunucuyu yorma
            
        except Exception as e:
            continue

    if firsat_var:
        telegram_gonder(rapor + "⚠️ _Yatırım tavsiyesi değildir._")
    else:
        print("Fırsat bulunamadı, mesaj atılmıyor.")

if __name__ == "__main__":
    analiz_et()
