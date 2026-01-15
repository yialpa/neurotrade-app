import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
from textblob import TextBlob
import requests

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="NeuroTrade Ultimate", layout="wide", page_icon="💎")

# --- CSS MAKYAJI (Koyu Tema & Profesyonel Fontlar) ---
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    .metric-card {background-color: #1E1E1E; border: 1px solid #333; padding: 10px; border-radius: 5px;}
    h1, h2, h3 {font-family: 'Helvetica Neue', sans-serif;}
</style>
""", unsafe_allow_html=True)

# --- YAN MENÜ (AYARLAR) ---
st.sidebar.title("💎 NeuroTrade SMC")
st.sidebar.markdown("---")

# Coin & Zaman Seçimi
secilen_coin = st.sidebar.selectbox("Varlık Seçin", ('BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'XRP/USDT', 'DOGE/USDT'))
zaman_dilimi = st.sidebar.selectbox("Zaman Dilimi", ('4h', '1h', '15m', '1d'))

st.sidebar.markdown("---")

# Telegram Ayarları (Güvenlik için buradan giriyoruz)
st.sidebar.subheader("📡 Telegram Bağlantısı")
tg_token = st.sidebar.text_input("Bot Token", type="password", help="BotFather'dan alınan token")
tg_chat_id = st.sidebar.text_input("Chat ID", help="Kanal ID'si (-100 ile başlar)")

if st.sidebar.button("Yenile 🔄"):
    st.rerun()

# --- FONKSİYONLAR ---

def telegram_gonder(token, chat_id, mesaj):
    if not token or not chat_id:
        st.sidebar.error("Telegram bilgileri eksik!")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': mesaj, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload)
        st.sidebar.success("Sinyal Gönderildi! 🚀")
    except Exception as e:
        st.sidebar.error(f"Hata: {e}")

def haberleri_cek():
    try:
        rss_url = "https://cointelegraph.com/rss"
        feed = feedparser.parse(rss_url)
        haberler = []
        puanlar = []
        
        for entry in feed.entries[:6]:
            analiz = TextBlob(entry.title)
            score = analiz.sentiment.polarity
            puanlar.append(score)
            
            ikon = "⚪"
            if score > 0.1: ikon = "🟢"
            elif score < -0.1: ikon = "🔴"
            
            haberler.append(f"{ikon} [{entry.title}]({entry.link})")
            
        avg_score = sum(puanlar) / len(puanlar) if puanlar else 0
        return avg_score, haberler
    except:
        return 0, []

def veri_getir(sembol, periyot):
    # BINANCE US KULLANIYORUZ (Global 451 hatasını önlemek için)
    exchange = ccxt.binanceus({'enableRateLimit': True})
    try:
        bars = exchange.fetch_ohlcv(sembol, timeframe=periyot, limit=200)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # --- TEKNİK GÖSTERGELER ---
        df['RSI'] = df.ta.rsi(length=14)
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        
        # MACD
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        df = pd.concat([df, macd], axis=1)
        
        # Bollinger
        bb = df.ta.bbands(length=20, std=2)
        df = pd.concat([df, bb], axis=1)
        
        # Destek/Direnç (Basit)
        df['Destek'] = df['low'].rolling(window=50).min()
        df['Direnc'] = df['high'].rolling(window=50).max()
        
        return df
    except Exception as e:
        st.error(f"Veri Hatası: {e}")
        return pd.DataFrame()

# --- ANA EKRAN ---
st.title(f"📊 {secilen_coin} SMC Terminali")

df = veri_getir(secilen_coin, zaman_dilimi)

if not df.empty:
    son = df.iloc[-1]
    
    # 1. ÜST METRİKLER
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Fiyat", f"${son['close']:.2f}")
    k2.metric("RSI", f"{son['RSI']:.2f}", "Aşırı Şişik" if son['RSI']>70 else "Dipte" if son['RSI']<30 else "Nötr")
    
    macd_val = son['MACD_12_26_9']
    macd_sig = son['MACDs_12_26_9']
    k3.metric("MACD Momentum", f"{macd_val:.2f}", "Al Sinyali" if macd_val > macd_sig else "Sat Sinyali")
    
    # Haber Puanı
    avg_news, haber_listesi = haberleri_cek()
    news_label = "POZİTİF" if avg_news > 0.1 else "NEGATİF" if avg_news < -0.1 else "NÖTR"
    k4.metric("Piyasa Havası (AI)", news_label, delta_color="normal")

    # --- SEKME YAPISI (TABS) ---
    tab1, tab2, tab3 = st.tabs(["📈 Profesyonel Grafik", "📢 Sinyal Masası", "🌍 Haberler"])

    with tab1:
        # GRAFİK OLUŞTURMA (Subplots: Üstte Fiyat, Altta MACD)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # 1. Mum Grafiği
        fig.add_trace(go.Candlestick(x=df['timestamp'],
                    open=df['open'], high=df['high'],
                    low=df['low'], close=df['close'], name='Fiyat'), row=1, col=1)

        # 2. EMA'lar
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='orange', width=1), name='EMA 50'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='purple', width=1), name='EMA 200'), row=1, col=1)

        # 3. ICT / FVG KUTULARI (SON 30 MUM İÇİNDEKİLERİ ÇİZELİM)
        # FVG Mantığı: 1. mum ile 3. mum arasında boşluk kalması
        for i in range(len(df)-30, len(df)-2):
            # Bullish FVG (Yeşil Kutu)
            if df['high'].iloc[i] < df['low'].iloc[i+2]:
                fig.add_shape(type="rect",
                    x0=df['timestamp'].iloc[i], y0=df['high'].iloc[i],
                    x1=df['timestamp'].iloc[i+5], y1=df['low'].iloc[i+2], # Sağa doğru uzat
                    fillcolor="green", opacity=0.3, line_width=0, row=1, col=1)
            
            # Bearish FVG (Kırmızı Kutu)
            if df['low'].iloc[i] > df['high'].iloc[i+2]:
                fig.add_shape(type="rect",
                    x0=df['timestamp'].iloc[i], y0=df['low'].iloc[i],
                    x1=df['timestamp'].iloc[i+5], y1=df['high'].iloc[i+2],
                    fillcolor="red", opacity=0.3, line_width=0, row=1, col=1)

        # 4. MACD (Alt Panel)
        fig.add_trace(go.Bar(x=df['timestamp'], y=df['MACDh_12_26_9'], marker_color='gray', name='MACD Hist'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MACD_12_26_9'], line=dict(color='blue', width=1), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MACDs_12_26_9'], line=dict(color='orange', width=1), name='Sinyal'), row=2, col=1)

        fig.update_layout(height=700, template="plotly_dark", title=f"{secilen_coin} ICT & Smart Money Analizi")
        fig.update_xaxes(rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.info("💡 **Grafik Açıklaması:** Yeşil kutular 'Alım Boşluklarını' (FVG), Kırmızı kutular 'Satış Boşluklarını' gösterir. Fiyat genelde bu kutulara geri döner.")

    with tab2:
        st.subheader("🤖 Sinyal Oluştur & Gönder")
        
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            st.markdown("### Otomatik Analiz")
            sinyal_yonu = "BEKLE"
            if son['RSI'] < 35 and son['close'] > df['Destek'].iloc[-1]:
                sinyal_yonu = "LONG (YÜKSELİŞ) 🚀"
            elif son['RSI'] > 65 and son['close'] < df['Direnc'].iloc[-1]:
                sinyal_yonu = "SHORT (DÜŞÜŞ) 🔻"
            
            st.write(f"Sistem Önerisi: **{sinyal_yonu}**")
            
            # Manuel Sinyal Metni
            custom_msg = st.text_area("Sinyal Metni", value=f"""
🚨 **NEUROTRADE VIP SİNYAL** 🚨

💎 **Coin:** #{secilen_coin.replace('/','')}
🚀 **Yön:** {sinyal_yonu}
⏱ **Zaman:** {zaman_dilimi}

💰 **Giriş:** {son['close']:.4f}$
🎯 **Hedef:** {(son['close']*1.02):.4f}$
🛑 **Stop:** {(son['close']*0.99):.4f}$

📊 **Analiz:** RSI {son['RSI']:.1f} seviyesinde. FVG bölgesi tespit edildi.
⚠️ _Yatırım tavsiyesi değildir._
            """, height=250)
            
            if st.button("📢 TELEGRAM KANALINA GÖNDER"):
                telegram_gonder(tg_token, tg_chat_id, custom_msg)
        
        with col_s2:
            st.warning("⚠️ **Dikkat:** Sinyal göndermek için sol menüden Telegram Token ve Chat ID'nizi girmeniz gerekir.")
            st.write("Token ve ID'niz tarayıcı önbelleğinde saklanmaz, her yenilemede tekrar girilmelidir (Güvenlik gereği).")

    with tab3:
        st.subheader("🌍 Dünya Gündemi")
        for h in haber_listesi:
            st.markdown(h)
            st.markdown("---")
