import ccxt
import pandas as pd
import requests
import time
import feedparser
from textblob import TextBlob

# --- AYARLAR ---
TELEGRAM_TOKEN = "8537277587:AAFxzrDMS0TEun8m7aQmck480iKD2HohtQc" 
CHAT_ID = "-1003516806415"

# Analiz Hassasiyeti (Ne kadar emin olsun?)
RSI_ALT = 33   # 30 civarı aşırı satım (LONG için)
RSI_UST = 67   # 70 civarı aşırı alım (SHORT için)

def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': mesaj, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try:
        requests.post(url, data=payload)
    except:
        pass

# --- MATEMATİKSEL HESAPLAMALAR ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def haberleri_analiz_et():
    # Cointelegraph RSS (Kripto Haberleri)
    url = "https://cointelegraph.com/rss"
    feed = feedparser.parse(url)
    onemli_haberler = ""
    
    cnt = 0
    for entry in feed.entries[:10]: # Son 10 habere bak
        analiz = TextBlob(entry.title)
        skor = analiz.sentiment.polarity # -1 (Çok Kötü) ile +1 (Çok İyi) arası
        
        # Nötr haberleri (0'a yakın) filtrele, sadece yönü belli olanları al
        if skor > 0.2:
            onemli_haberler += f"🟢 **OLUMLU GELİŞME:** [{entry.title}]({entry.link})\n"
            cnt += 1
        elif skor < -0.2:
            onemli_haberler += f"🔴 **OLUMSUZ HABER:** [{entry.title}]({entry.link})\n"
            cnt += 1
            
        if cnt >= 3: break # Çok fazla haber boğmasın, max 3 tane
    
    return onemli_haberler

def analiz_et():
    exchange = ccxt.kraken() # Veri çekmek için Kraken (Daha stabil)
    exchange_binance = ccxt.binance() # Top hacim listesi için
    
    print("Top 100 Coin Listesi Hazırlanıyor...")
    
    try:
        # Piyasada en çok hacmi olan ilk 50 çifti otomatik bul (USDT paritesi)
        tickers = exchange_binance.fetch_tickers()
        sorted_tickers = sorted(tickers.items(), key=lambda item: item[1]['quoteVolume'] if 'quoteVolume' in item[1] else 0, reverse=True)
        
        # İlk 50 USDT paritesini al (USDC, BUSD vb eledik)
        hedef_coinler = []
        for symbol, data in sorted_tickers:
            if '/USDT' in symbol and 'UP/' not in symbol and 'DOWN/' not in symbol: # Kaldıraçlı tokenları ele
                # Kraken formatına çevir (BTC/USDT -> BTC/USD) çünkü Kraken verisi daha temiz
                clean_symbol = symbol.replace('USDT', 'USD')
                hedef_coinler.append(clean_symbol)
            if len(hedef_coinler) >= 50: break # İlk 50 coin yeterli (GitHub süresi yetmeyebilir)
            
    except:
        # Eğer liste çekemezse yedek liste
        hedef_coinler = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'XRP/USD', 'AVAX/USD', 'DOGE/USD', 'BNB/USD', 'ADA/USD']

    rapor_listesi = []

    print(f"{len(hedef_coinler)} adet coin taranıyor...")

    for coin in hedef_coinler:
        try:
            # 4 Saatlik grafik (Daha güvenilir trend için)
            bars = exchange.fetch_ohlcv(coin, timeframe='4h', limit=50)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            fiyat = df['close'].iloc[-1]
            high = df['high']
            low = df['low']
            
            # --- TEKNİK GÖSTERGELER ---
            df['RSI'] = calculate_rsi(df['close'], 14)
            rsi = df['RSI'].iloc[-1]
            
            # Destek & Direnç (Son 50 mumun en düşüğü ve en yükseği)
            destek = low.min()
            direnc = high.max()
            
            # FVG (Fair Value Gap) Tespiti - ICT Konsepti
            # Bullish FVG: 1. Mumun tepesi, 3. Mumun dibinden aşağıdaysa arada boşluk vardır.
            fvg_bullish = False
            fvg_bearish = False
            
            # Son 3 muma bakıyoruz
            last_candle = df.iloc[-1]   # Şu anki mum
            prev_candle = df.iloc[-2]   # Bir önceki (Tamamlanmış)
            pre_prev    = df.iloc[-3]   # Ondan önceki
            ancient     = df.iloc[-4]   # FVG referansı
            
            # Basitleştirilmiş FVG Kontrolü (Son kapanan mumlarda boşluk var mı?)
            if ancient['high'] < prev_candle['low']: 
                fvg_bullish = True # Yükseliş Boşluğu
            if ancient['low'] > prev_candle['high']:
                fvg_bearish = True # Düşüş Boşluğu

            # --- SİNYAL OLUŞTURMA (Keskin Nişancı Mantığı) ---
            # Sadece RSI yetmez, Destek/Direnç veya FVG onayı lazım.
            
            sinyal = None
            
            # LONG STRATEJİSİ: RSI Dipte VE (Fiyat Desteğe Yakın VEYA Bullish FVG Var)
            if rsi < RSI_ALT:
                dist_to_support = (fiyat - destek) / fiyat
                if dist_to_support < 0.03 or fvg_bullish: # Desteğe %3 yakınsa veya FVG varsa
                    sinyal = "LONG 🟢"
                    sebep = f"RSI Dip ({rsi:.1f}) + {'Destek Bölgesi' if dist_to_support < 0.03 else 'Bullish FVG'}"

            # SHORT STRATEJİSİ: RSI Tepede VE (Fiyat Dirence Yakın VEYA Bearish FVG Var)
            elif rsi > RSI_UST:
                dist_to_resist = (direnc - fiyat) / fiyat
                if dist_to_resist < 0.03 or fvg_bearish:
                    sinyal = "SHORT 🔴"
                    sebep = f"RSI Tepe ({rsi:.1f}) + {'Direnç Bölgesi' if dist_to_resist < 0.03 else 'Bearish FVG'}"

            if sinyal:
                coin_adi = coin.replace('/USD', '')
                mesaj = f"🚨 **{sinyal} FIRSATI**\n\n"
                mesaj += f"💎 **Coin:** #{coin_adi}\n"
                mesaj += f"💰 **Fiyat:** ${fiyat:.4f}\n"
                mesaj += f"📊 **Sebep:** {sebep}\n"
                mesaj += f"🛡 **Destek:** ${destek:.4f} | 🧱 **Direnç:** ${direnc:.4f}\n"
                
                rapor_listesi.append(mesaj)
            
            time.sleep(0.5) # API ban yememek için bekleme

        except Exception as e:
            continue

    # --- TOPLU MESAJ GÖNDERİMİ ---
    final_mesaj = ""
    
    # Eğer sinyal varsa ekle
    if rapor_listesi:
        final_mesaj += "⚡ **NEUROTRADE VIP SİNYALLERİ** ⚡\n\n"
        final_mesaj += "\n------------------\n".join(rapor_listesi)
        final_mesaj += "\n\n"
    
    # Haberleri de ekle (Varsa)
    haberler = haberleri_analiz_et()
    if haberler:
        final_mesaj += "📰 **ÖNEMLİ PİYASA HABERLERİ**\n"
        final_mesaj += haberler

    # Eğer elde paylaşılacak bir şey varsa gönder
    if final_mesaj:
        telegram_gonder(final_mesaj)
    else:
        print("Sinyal veya önemli haber yok, sessiz mod.")

if __name__ == "__main__":
    analiz_et()
