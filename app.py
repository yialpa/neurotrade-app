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
TARANACAK_COINLER = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
    'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'LINK/USDT', 'LTC/USDT', 'MATIC/USDT'
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
    # Binance US kullanıyoruz
    exchange = ccxt.binanceus({'enableRateLimit': True}) 
    try:
        bars = exchange.fetch_ohlcv(sembol, timeframe=periyot, limit
