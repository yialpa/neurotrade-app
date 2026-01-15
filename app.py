Bu hatanın sebebi çok net: Hız Limiti (Rate Limit).

Biz programa "Bütün coinleri 1 saniye içinde tara" dedik. Binance sunucusu da, "Hop! Sen bir robotsun, çok hızlı istek atıyorsun, seni engelliyorum" dedi. Bu yüzden sana boş veri döndü.

Bunu çözmek için bota "İnsani Davranış" ekleyeceğiz. Her coine baktıktan sonra 1 saniye dinlenecek.

Aşağıdaki V5.4 Kodu ile sorun çözülecek.

Yapman Gerekenler:
GitHub'da app.py dosyanı aç.

Hepsini sil.

Aşağıdaki kodu yapıştır. (Bu kodda tarama arasına time.sleep(1) koydum, yani 1 saniye bekleyip diğer coine geçecek).

✅ NEUROTRADE V5.4 (Hız Limiti Korumalı)
Python

import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
from textblob import TextBlob
import requests
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="NeuroTrade Scanner", layout="wide", page_icon="💎")

# --- CSS MAKYAJI ---
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    .metric-card {background-color: #1E1E1E; border: 1px solid #333; padding: 10px; border-radius: 5px;}
    h1, h2, h3 {font-family: 'Helvetica Neue', sans-serif;}
</style>
""", unsafe_allow_html=True)

# --- AYARLAR ---
# Listeyi biraz azalttık ki daha garanti çalışsın
TARANACAK_COINLER = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
    'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT'
]

# --- YAN MENÜ ---
st.sidebar.title("💎 NeuroTrade Pro")
st.sidebar.markdown("---")

mod = st.sidebar.radio("Çalışma Modu", ["📊 Tekli Analiz", "🔍 Market Tarayıcı"])

st.sidebar.markdown("---")
st.sidebar.subheader("📡 Telegram Ayarları")
tg_token = st.sidebar.text_input("Bot Token", type="password")
tg_chat_id = st.sidebar.text_input("Chat ID")

# --- FONKSİYONLAR ---

def telegram_gonder(token, chat_id, mesaj):
    if not token or not chat_id:
        st.error("Telegram bilgileri eksik!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': mesaj, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload)
        st.success("Mesaj İletildi! 🚀")
    except:
        st.error("Gönderim Hatası")

def veri_getir(sembol, periyot='4h', limit=100):
    # Kraken kullanıyoruz (Daha az blokluyor)
    try:
        # BinanceUS yerine Kraken deneyelim, bazen daha stabil
        exchange = ccxt.kraken() 
        # Kraken sembolleri bazen farklıdır, o yüzden BinanceUS'e geri dönüyoruz ama yavaşlatarak
        exchange = ccxt.binanceus({'enableRateLimit': True})
        
        bars = exchange.fetch_ohlcv(sembol, timeframe=periyot, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # İndikatörler
        df['RSI'] = df.ta.rsi(length=14)
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        
        # Destek/Direnç
        df['Destek'] = df['low'].rolling(window=50).min()
        df['Direnc'] = df['high'].rolling(window=50).max()
        
        return df
    except Exception as e:
        print(f"Hata ({sembol}): {e}") # Loglara hatayı yaz
        return pd.DataFrame()

# --- MOD 1: TEKLİ ANALİZ ---
if mod == "📊 Tekli Analiz":
    secilen_coin = st.sidebar.selectbox("Varlık Seçin", TARANACAK_COINLER)
    zaman_dilimi = st.sidebar.selectbox("Zaman Dilimi", ('4h', '1h', '15m'))
    
    st.title(f"📊 {secilen_coin} Detaylı Analiz")
    
    df = veri_getir(secilen_coin, zaman_dilimi, 200)
    
    if not df.empty:
        son = df.iloc[-1]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Fiyat", f"${son['close']:.2f}")
        c2.metric("RSI", f"{son['RSI']:.2f}", "Aşırı Alım" if son['RSI']>70 else "Aşırı Satım" if son['RSI']<30 else "Nötr")
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Fiyat'))
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='orange'), name='EMA 50'))
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='purple'), name='EMA 200'))
        
        for i in range(len(df)-50, len(df)-6):
             if df['high'].iloc[i] < df['low'].iloc[i+2]: 
                 fig.add_shape(type="rect", x0=df['timestamp'].iloc[i], y0=df['high'].iloc[i], x1=df['timestamp'].iloc[i+5], y1=df['low'].iloc[i+2], fillcolor="green", opacity=0.3, line_width=0)
             if df['low'].iloc[i] > df['high'].iloc[i+2]:
                 fig.add_shape(type="rect", x0=df['timestamp'].iloc[i], y0=df['low'].iloc[i], x1=df['timestamp'].iloc[i+5], y1=df['high'].iloc[i+2], fillcolor="red", opacity=0.3, line_width=0)
        
        fig.update_layout(height=600, template="plotly_dark", title="Teknik Görünüm")
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📢 Sinyal Paylaş")
        msg = st.text_area("Mesaj", value=f"🚀 **{secilen_coin}** Analizi\nFiyat: {son['close']}$ \nRSI: {son['RSI']:.2f}")
        if st.button("Gönder"):
            telegram_gonder(tg_token, tg_chat_id, msg)

# --- MOD 2: MARKET TARAYICI ---
elif mod == "🔍 Market Tarayıcı":
    st.title("🔍 Kripto Radar")
    st.info("Listedeki coinler taranıyor... Her coin için 1 saniye beklenir (Güvenlik gereği).")
    
    periyot_scan = st.selectbox("Tarama Periyodu", ["4h", "1h", "1d"])
    
    if st.button("🚀 TARAMAYI BAŞLAT"):
        bar = st.progress(0)
        firsatlar = []
        
        for i, coin in enumerate(TARANACAK_COINLER):
            # İlerleme mesajı
            st.write(f"⏳ {coin} taranıyor...")
            
            df = veri_getir(coin, periyot_scan, 100)
            if not df.empty:
                son = df.iloc[-1]
                rsi = son['RSI']
                ema50 = son['EMA_50']
                fiyat = son['close']
                
                durum = "NOTR"
                
                if rsi < 35: durum = "GUCLU AL"
                elif rsi > 70: durum = "GUCLU SAT"
                elif fiyat > ema50 and rsi > 55: durum = "TREND VAR"
                
                firsatlar.append({
                    "Coin": coin,
                    "Fiyat": f"${fiyat:.4f}",
                    "RSI": f"{rsi:.1f}",
                    "Sinyal": durum
                })
            else:
                st.write(f"❌ {coin} verisi alınamadı.")
            
            bar.progress((i + 1) / len(TARANACAK_COINLER))
            
            # BURASI ÇOK ÖNEMLİ: HIZ LİMİTİNE TAKILMAMAK İÇİN 1 SANİYE BEKLEME
            time.sleep(1.0)
            
        st.success("Tarama Tamamlandı!")
        
        if len(firsatlar) > 0:
            sonuc_df = pd.DataFrame(firsatlar)
            
            def renkli_tablo(val):
                color = 'white'
                if 'GUCLU AL' in str(val): color = '#90EE90'
                elif 'GUCLU SAT' in str(val): color = '#FFcccb'
                elif 'TREND' in str(val): color = '#ADD8E6'
                return f'background-color: {color}; color: black'

            try:
                try:
                    st.dataframe(sonuc_df.style.map(renkli_tablo, subset=['Sinyal']), use_container_width=True)
                except:
                    st.dataframe(sonuc_df.style.applymap(renkli_tablo, subset=['Sinyal']), use_container_width=True)
            except:
                st.dataframe(sonuc_df)
        else:
            st.warning("Veri çekilemedi. Sunucu çok yoğun olabilir.")
