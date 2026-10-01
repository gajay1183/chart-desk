import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

st.set_page_config(page_title="Chart Desk Live", layout="wide", initial_sidebar_state="collapsed")

WATCH = {
    "NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK", "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS", "HDFCBANK": "HDFCBANK.NS", "INFY": "INFY.NS",
    "ICICIBANK": "ICICIBANK.NS", "ITC": "ITC.NS", "SBIN": "SBIN.NS",
}
PERIODS = {"1m": "5d", "5m": "1mo", "15m": "1mo", "1h": "6mo", "1d": "2y", "1wk": "5y"}


@st.cache_data(ttl=30, show_spinner=False)
def load(sym, interval):
    df = yf.download(sym, period=PERIODS[interval], interval=interval,
                     auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    if df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
    return df


@st.cache_data(ttl=60, show_spinner=False)
def watchlist():
    d = yf.download(list(WATCH.values()), period="5d", interval="1d", progress=False)["Close"]
