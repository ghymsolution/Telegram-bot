import streamlit as st
import pandas as pd
import ccxt
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Scalping Velocity Scanner", layout="wide")
st.title("⚡ Scalping Velocity Scanner (1m/5m/15m)")

# ==========================================
# --- إعدادات القائمة الجانبية (Sidebar) ---
# ==========================================
st.sidebar.header("⚙️ إعدادات السكانر")

st.sidebar.markdown("### 🚨 شروط التنبيه (Alerts)")
alert_vel = st.sidebar.number_input("الحد الأدنى للـ Velocity (1m):", min_value=1.0, max_value=20.0, value=3.0, step=0.5)
alert_change = st.sidebar.number_input("الحد الأدنى لتغير 1 دقيقة (%):", min_value=0.1, max_value=10.0, value=0.5, step=0.1)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔊 تجربة الصوت")
sound_url = "https://upload.wikimedia.org/wikipedia/commons/0/05/Beep-09.ogg"

if st.sidebar.button("نجرب الصوت 🔔"):
    audio_html = f"""
        <audio autoplay style="display:none;">
            <source src="{sound_url}" type="audio/ogg">
        </audio>
    """
    st.sidebar.markdown(audio_html, unsafe_allow_html=True)
    st.sidebar.success("الصوت يخدم مريڤل! 🎧")
# ==========================================

# --- إعدادات بينانس ---
exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "future"}
})

persistent_alert_ph = st.empty() 
placeholder = st.empty()
error_ph = st.empty()
alert_ph = st.empty() 
audio_ph = st.empty() 

stable_coins = {"USDT", "USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI"}
excluded_coins = {"BTC", "ETH", "SOL", "PAXG", "XAU"} 

# --- دوال مساعدة ---
def color_change(val):
    if val is None or pd.isna(val): 
        return 'color: grey'
    if val > 0: return 'color: green'
    elif val < 0: return 'color: red'
    return 'color: grey'

@st.cache_resource(ttl=3600) # كاش لمدة ساعة باش ما يطلبش الأسواق كل ريفرش
def get_markets():
    return exchange.load_markets()

markets = get_markets()
symbols = [
    sym for sym, m in markets.items()
    if sym.endswith(":USDT") 
    and m.get("active") 
    and sym.split("/")[0] not in stable_coins
    and sym.split("/")[0] not in excluded_coins
]

def fetch_all_data(symbol, vol_24h, funding_rate):
    try:
        ohlcv_1m = exchange.fetch_ohlcv(symbol, timeframe="1m", limit=1)
        ohlcv_5m = exchange.fetch_ohlcv(symbol, timeframe="5m", limit=1)
        ohlcv_15m = exchange.fetch_ohlcv(symbol, timeframe="15m", limit=1)
        
        if not ohlcv_1m or not ohlcv_5m or not ohlcv_15m:
            return None

        open_1m, close_1m, vol_1m = ohlcv_1m[0][1], ohlcv_1m[0][4], ohlcv_1m[0][5]
        open_5m, close_5m, vol_5m = ohlcv_5m[0][1], ohlcv_5m[0][4], ohlcv_5m[0][5]
        open_15m, close_15m = ohlcv_15m[0][1], ohlcv_15m[0][4]

        est_vol_1m = vol_1m * close_1m
        est_vol_5m = vol_5m * close_5m

        change_1m = ((close_1m - open_1m) / open_1m) * 100 if open_1m else 0
        change_5m = ((close_5m - open_5m) / open_5m) * 100 if open_5m else 0
        change_15m = ((close_15m - open_15m) / open_15m) * 100 if open_15m else 0

        avg_1m_vol = vol_24h / (24 * 60) if vol_24h else 0
        velocity_ratio = (est_vol_1m / avg_1m_vol) if avg_1m_vol > 0 else 0

        imbalance = None
        if velocity_ratio > 2.0:
            try:
                ob = exchange.fetch_order_book(symbol, limit=10)
                bid_vol = sum(bid[1] for bid in ob['bids'][:10]) 
                ask_vol = sum(ask[1] for ask in ob['asks'][:10]) 
                if bid_vol + ask_vol > 0:
                    imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
            except:
                pass

        return {
            "Symbol": symbol.split("/")[0],
            "Price ($)": close_1m,
            "1M Est.Vol ($)": est_vol_1m,
            "1M Change %": change_1m,
            "5M Est.Vol ($)": est_vol_5m,
            "5M Change %": change_5m,
            "15M Change %": change_15m,
            "Vel. Ratio": velocity_ratio,
            "Funding Rate %": funding_rate,
            "Imbalance": imbalance
        }
    except Exception as e:
        return None

# --- جلب البيانات وعرضها ---
try:
    tickers = exchange.fetch_tickers()

    all_funding_rates = {}
    try:
        funding_data = exchange.fetch_funding_rates()
        for sym, info in funding_data.items():
            all_funding_rates[sym] = info.get('fundingRate', 0) * 100
    except Exception:
        pass 

    filtered = [
        (sym, info['quoteVolume'])
        for sym, info in tickers.items()
        if sym in symbols and info.get('quoteVolume')
    ]
    filtered.sort(key=lambda x: x[1], reverse=True)
    top_symbols = [x[0] for x in filtered[:40]]

    data = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                fetch_all_data, 
                sym, 
                next((v for s,v in filtered if s==sym), 0),
                all_funding_rates.get(sym, None)
            ): sym
            for sym in top_symbols
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                data.append(result)

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("Vel. Ratio", ascending=False).head(30)

        df["Chart"] = df["Symbol"].apply(lambda x: f"https://www.tradingview.com/chart/?symbol=BINANCE:{x}USDT.P")
        cols = ["Symbol", "Chart", "Price ($)", "1M Est.Vol ($)", "1M Change %", 
                "5M Est.Vol ($)", "5M Change %", "15M Change %", "Vel. Ratio", 
                "Funding Rate %", "Imbalance"]
        df = df[cols]

        format_dict = {
            "Price ($)": "{:,.4f}",
            "1M Est.Vol ($)": "{:,.0f}",
            "1M Change %": "{:.2f}%",
            "5M Est.Vol ($)": "{:,.0f}",
            "5M Change %": "{:.2f}%",
            "15M Change %": "{:.2f}%",
            "Vel. Ratio": "{:.2f}x",
            "Funding Rate %": "{:.4f}%",
            "Imbalance": "{:.2f}"
        }
        colored_cols = ["1M Change %", "5M Change %", "15M Change %", "Funding Rate %", "Imbalance"]

        styled_df = df.style.format(format_dict, na_rep="-") \
                            .map(color_change, subset=colored_cols)

        with placeholder.container():
            st.dataframe(
                styled_df, 
                use_container_width=True, 
                hide_index=True, 
                height=800,
                column_config={
                    "Chart": st.column_config.LinkColumn(
                        "Chart",
                        display_text="📈 View"
                    )
                }
            )

        # --- نظام التنبيهات ---
        alerts = df[(df["Vel. Ratio"] > alert_vel) & (df["1M Change %"] > alert_change)]
        
        if not alerts.empty:
            alert_audio = f"""
                <audio autoplay style="display:none;">
                    <source src="{sound_url}" type="audio/ogg">
                </audio>
            """
            audio_ph.markdown(alert_audio, unsafe_allow_html=True)
            
            current_time = datetime.now().strftime("%H:%M:%S")
            alert_msg = f"### 🚨 آخر تنبيه سكالبينج (الوقت: {current_time})\n"
            
            for _, row in alerts.iterrows():
                alert_ph.toast(
                    f'🚨 {row["Symbol"]} : Vel {row["Vel. Ratio"]:.1f}x | 1M: +{row["1M Change %"]:.2f}%',
                    icon="🔥"
                )
                alert_msg += f"- **{row['Symbol']}** ➡️ Vel: **{row['Vel. Ratio']:.1f}x** | 1M Change: **+{row['1M Change %']:.2f}%**\n"
            
            persistent_alert_ph.error(alert_msg)

except Exception as e:
    error_ph.error(f"Error encountered: {e}")

# --- إعادة التشغيل التلقائي (Auto-Refresh) ---
time.sleep(5)
st.rerun()
