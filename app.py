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
    rows = []
    for name, t in WATCH.items():
        s = d[t].dropna()
        if len(s) >= 2:
            rows.append({"Symbol": name, "LTP": round(s.iloc[-1], 2),
                         "Chg %": round((s.iloc[-1] / s.iloc[-2] - 1) * 100, 2)})
    return pd.DataFrame(rows)


def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def heikin(df):
    ha = df.copy()
    ha["Close"] = (df.Open + df.High + df.Low + df.Close) / 4
    o = [(df.Open.iloc[0] + df.Close.iloc[0]) / 2]
    for i in range(1, len(df)):
        o.append((o[-1] + ha.Close.iloc[i - 1]) / 2)
    ha["Open"] = o
    ha["High"] = pd.concat([df.High, ha.Open, ha.Close], axis=1).max(axis=1)
    ha["Low"] = pd.concat([df.Low, ha.Open, ha.Close], axis=1).min(axis=1)
    return ha


# ---------- controls ----------
st.title("Chart Desk Live")
c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
pick = c1.selectbox("Symbol", list(WATCH))
custom = c2.text_input("Or type a symbol", placeholder="e.g. TATAMOTORS")
interval = c3.selectbox("Timeframe", list(PERIODS), index=1)
ctype = c4.selectbox("Chart", ["Candles", "Heikin-Ashi", "Line"])
ind = st.multiselect("Indicators", ["SMA 20", "SMA 50", "EMA 21", "Bollinger", "VWAP", "Volume", "RSI", "MACD"],
                     default=["SMA 20", "SMA 50", "Volume", "RSI"])
c5, c6 = st.columns([1, 3])
live = c5.toggle("Auto-refresh (30s)", value=True)
levels = c6.text_input("Price levels (comma separated)", placeholder="e.g. 24500, 24800")

sym = WATCH[pick]
if custom.strip():
    s = custom.strip().upper()
    sym = s if (s.startswith("^") or "." in s) else s + ".NS"


@st.fragment(run_every=30 if live else None)
def chart():
    df = load(sym, interval)
    if df.empty:
        st.error(f"No data for {sym}. Check the symbol (NSE stocks need .NS, added automatically).")
        return
    days = df.index.normalize()
    today = df[days == days[-1]]
    before = df.Close[days < days[-1]]
    last = df.Close.iloc[-1]
    prev = before.iloc[-1] if len(before) else df.Open.iloc[0]
    chg = (last / prev - 1) * 100
    col = "green" if chg >= 0 else "red"
    st.markdown(f"### {last:,.2f} :{col}[{chg:+.2f}%]")
    st.caption(f"Day H {today.High.max():,.2f} · L {today.Low.min():,.2f} · Updated {df.index[-1].strftime('%d %b %H:%M')}")

    c = df.Close
    show_rsi, show_macd = "RSI" in ind, "MACD" in ind
    rows = 1 + show_rsi + show_macd
    heights = [0.6] + [0.2] * (rows - 1)
    specs = [[{"secondary_y": True}]] + [[{}] for _ in range(rows - 1)]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=heights, specs=specs)

    src = heikin(df) if ctype == "Heikin-Ashi" else df
    if ctype == "Line":
        fig.add_scatter(x=df.index, y=c, name="Close", line=dict(color="#2f5bea", width=2), row=1, col=1)
    else:
        fig.add_candlestick(x=src.index, open=src.Open, high=src.High, low=src.Low, close=src.Close,
                            name="Price", increasing_line_color="#12915f", decreasing_line_color="#d23f3f",
                            row=1, col=1)
    if "SMA 20" in ind:
        fig.add_scatter(x=df.index, y=c.rolling(20).mean(), name="SMA 20", line=dict(color="#f2a900", width=1), row=1, col=1)
    if "SMA 50" in ind:
        fig.add_scatter(x=df.index, y=c.rolling(50).mean(), name="SMA 50", line=dict(color="#a259ff", width=1), row=1, col=1)
    if "EMA 21" in ind:
        fig.add_scatter(x=df.index, y=c.ewm(span=21, adjust=False).mean(), name="EMA 21", line=dict(color="#19a7ce", width=1), row=1, col=1)
    if "Bollinger" in ind:
        m, sd = c.rolling(20).mean(), c.rolling(20).std()
        for k, n in ((2, "BB upper"), (-2, "BB lower")):
            fig.add_scatter(x=df.index, y=m + k * sd, name=n, line=dict(color="#7a8aa0", width=1, dash="dot"), row=1, col=1)
    if "VWAP" in ind and interval not in ("1d", "1wk"):
        tp = (df.High + df.Low + df.Close) / 3
        day = df.index.date
        vw = (tp * df.Volume).groupby(day).cumsum() / df.Volume.groupby(day).cumsum().replace(0, np.nan)
        fig.add_scatter(x=df.index, y=vw, name="VWAP", line=dict(color="#e8590c", width=1.5), row=1, col=1)
    if "Volume" in ind:
        col = np.where(df.Close >= df.Open, "rgba(18,145,95,.35)", "rgba(210,63,63,.35)")
        fig.add_bar(x=df.index, y=df.Volume, name="Volume", marker_color=col, showlegend=False,
                    row=1, col=1, secondary_y=True)
        fig.update_yaxes(range=[0, df.Volume.max() * 5], visible=False, showgrid=False,
                         secondary_y=True, row=1, col=1)
    for v in [x for x in levels.replace(" ", "").split(",") if x]:
        try:
            fig.add_hline(y=float(v), line_dash="dash", line_color="#2f5bea", row=1, col=1)
        except ValueError:
            pass
    r = 2
    if show_rsi:
        fig.add_scatter(x=df.index, y=rsi(c), name="RSI 14", line=dict(color="#a259ff"), row=r, col=1)
        for lvl in (70, 30):
            fig.add_hline(y=lvl, line_dash="dot", line_color="#7a8aa0", row=r, col=1)
        fig.update_yaxes(range=[0, 100], row=r, col=1)
        r += 1
    if show_macd:
        macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
        sig = macd.ewm(span=9, adjust=False).mean()
        hist = macd - sig
        fig.add_bar(x=df.index, y=hist, name="Hist",
                    marker_color=np.where(hist >= 0, "rgba(18,145,95,.6)", "rgba(210,63,63,.6)"), row=r, col=1)
        fig.add_scatter(x=df.index, y=macd, name="MACD", line=dict(color="#2f5bea", width=1.5), row=r, col=1)
        fig.add_scatter(x=df.index, y=sig, name="Signal", line=dict(color="#f2a900", width=1), row=r, col=1)

    breaks = [dict(bounds=["sat", "mon"])]
    if interval in ("1m", "5m", "15m", "1h"):
        breaks.append(dict(bounds=[15.5, 9.25], pattern="hour"))
    fig.update_xaxes(rangebreaks=breaks, rangeslider_visible=False)
    fig.update_layout(height=560 if rows > 1 else 460, margin=dict(l=8, r=8, t=10, b=8),
                      legend=dict(orientation="h", y=1.0, yanchor="bottom", font=dict(size=10)), hovermode="x unified", dragmode="pan")
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": False})
    st.caption("Data: Yahoo Finance via yfinance, delayed up to ~15 min for NSE. Not investment advice.")


chart()

with st.expander("Watchlist"):
    st.dataframe(watchlist(), hide_index=True, use_container_width=True)
