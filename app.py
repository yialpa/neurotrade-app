import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import feedparser
from textblob import TextBlob
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="NeuroTrade Pro V3", layout="wide", page_icon="🧠")

# --- CSS İLE MAKYAJ ---
st.markdown("""
<style>
    .metric-card {background-color: #121212; border: 1px solid #333; padding: 15px; border-radius: 10px;}
    .stAlert {background-color: #1E1E1E; border: 1px solid #444;}
</style>
""", unsafe_allow_html=True)

# --- YAN MENÜ ---
st.sidebar.title("🧠 NeuroTrade V3.0")
st.sidebar.info("Yapay Zeka & Teknik Analiz")
secilen_coin = st.sidebar.selectbox("Parite Seçin", ('BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'XRP/USDT'))
zaman_dilimi = st.sidebar.selectbox("Zaman Dilimi", ('4h', '1h', '15m', '1d'))

if st.sidebar.button("Yenile 🔄"):
    st.rerun()

# --- 1. HABER MODÜLÜ ---
def haberleri_analiz_et():
    try:
        rss_url = "https://cointelegraph.com/rss"
        feed = feedparser.parse(rss_url)
        haberler = []
        toplam_puan = 0
        
        # Son 5 haberi çek
        for entry in feed.entries[:5]:
            analiz = TextBlob(entry.title)
            puan = analiz.sentiment.polarity
            toplam_puan += puan
            
            ikon = "⚪"
            if puan > 0.1: ikon = "🟢 (İyi)"
            elif puan < -0.1: ikon = "🔴 (Kötü)"
            
            haberler.append(f"**{ikon}** {entry.title}")
            
        genel_hava = "YATAY/NÖTR"
        renk = "gray"
        if toplam_puan > 0.2: 
            genel_hava = "POZİTİF (BOĞA)"
            renk = "green"
        elif toplam_puan < -0.2: 
            genel_hava = "NEGATİF (AYI)"
            renk = "red"
            
        return genel_hava, renk, haberler
    except:
        return "Veri Yok", "gray", ["Haberler çekilemedi."]

# --- 2. VERİ VE TEKNİK ANALİZ MODÜLÜ ---
def veri_getir(sembol, periyot):
    exchange = ccxt.binanceus({'enableRateLimit': True})
    try:
        bars = exchange.fetch_ohlcv(sembol, timeframe=periyot, limit=200)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # --- GÖSTERGELERİ HESAPLA ---
        # 1. RSI
        df['RSI'] = df.ta.rsi(length=14)
        
        # 2. Hareketli Ortalamalar (EMA)
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        
        # 3. Bollinger Bantları
        bb = df.ta.bbands(length=20, std=2)
        df = pd.concat([df, bb], axis=1) # BBL, BBM, BBU sütunları gelir
        
        # 4. Destek / Direnç
        df['Destek'] = df['low'].rolling(window=50).min()
        df['Direnc'] = df['high'].rolling(window=50).max()
        
        return df
    except Exception as e:
        st.error(f"Veri Hatası: {e}")
        return pd.DataFrame()

# --- EKRAN DÜZENİ ---
st.title(f"📊 {secilen_coin} Profesyonel Analiz")

# Veriyi Çek
df = veri_getir(secilen_coin, zaman_dilimi)

if not df.empty:
    son = df.iloc[-1]
    
    # --- ÜST BİLGİ KUTULARI ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fiyat", f"${son['close']:.2f}")
    
    rsi_durum = "Nötr"
    if son['RSI'] > 70: rsi_durum = "Aşırı Alım 🔴"
    elif son['RSI'] < 30: rsi_durum = "Aşırı Satım 🟢"
    col2.metric("RSI", f"{son['RSI']:.2f}", rsi_durum)
    
    col3.metric("Destek", f"${son['Destek']:.2f}")
    col4.metric("Direnç", f"${son['Direnc']:.2f}")
    
    # --- ANA GRAFİK (Full Özellik) ---
    c_grafik, c_haber = st.columns([3, 1])
    
    with c_grafik:
        st.subheader("Teknik Grafik (EMA + Bollinger)")
        fig = go.Figure()
        
        # Mumlar
        fig.add_trace(go.Candlestick(x=df['timestamp'],
                    open=df['open'], high=df['high'],
                    low=df['low'], close=df['close'], name='Fiyat'))
        
        # EMA Çizgileri
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='orange', width=2), name='EMA 50'))
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='purple', width=2), name='EMA 200'))
        
        # Bollinger Bantları (Bulut)
        # Sütun isimleri genelde BBU_20_2.0 (Üst) ve BBL_20_2.0 (Alt) olur
        # pandas_ta sütun isimlerini kontrol etmek gerekebilir ama genelde standarttır.
        try:
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['BBU_20_2.0'], line=dict(color='blue', width=1, dash='dot'), name='BB Üst'))
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['BBL_20_2.0'], line=dict(color='blue', width=1, dash='dot'), name='BB Alt'))
        except:
            pass # Eğer isimler farklıysa hata vermesin

        fig.update_layout(height=600, template="plotly_dark", title=f"{secilen_coin} Detaylı Grafik")
        st.plotly_chart(fig, use_container_width=True)
        
        # Sinyal Kutusu
        st.info(f"💡 **İpucu:** Turuncu çizgi (EMA 50), Mor çizgiyi (EMA 200) yukarı keserse 'Golden Cross' (Büyük Yükseliş) sinyalidir.")

    # --- SAĞ TARAF: HABERLER ---
    with c_haber:
        st.subheader("🌍 Haberler & Duygu")
        hava, renk, haber_listesi = haberleri_analiz_et()
        
        st.markdown(f"<h3 style='color:{renk}; text-align:center;'>{hava}</h3>", unsafe_allow_html=True)
        st.divider()
        
        for h in haber_listesi:
            st.markdown(h)
            st.markdown("---")

else:

    st.warning("Veri yükleniyor...")
