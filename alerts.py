# save as stock_alerts_gnews.py
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
import os

# -------- CONFIG ----------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WATCHLIST = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
CHECK_INTERVAL = 300  # seconds (5 min)
PCT_DOWN_ALERT = -3.0
PCT_UP_ALERT = 3.0
VOL_5MIN_MULTIPLIER = 3.0
CUMULATIVE_DAILY_VOL_MULTIPLIER = 1.5

GNEWS_API_KEY = os.getenv("NEWS_API_KEY")   # get from https://gnews.io/
LAST_NEWS = {}  # to avoid duplicate alerts

# -------- helpers ----------
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print("Telegram send error:", e)

def is_market_open_india(now=None):
    if now is None:
        now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    if now.weekday() >= 5:
        return False
    start = datetime.combine(now.date(), dt_time(9,15), tzinfo=ZoneInfo("Asia/Kolkata"))
    end   = datetime.combine(now.date(), dt_time(15,30), tzinfo=ZoneInfo("Asia/Kolkata"))
    return start <= now <= end

def check_symbol(symbol):
    ticker_symbol = symbol if symbol.endswith(".NS") else symbol + ".NS"
    t = yf.Ticker(ticker_symbol)
    try:
        # Daily data
        daily = t.history(period="15d", interval="1d")
        if daily.empty:
            return
        prev_close = daily["Close"].iloc[-2] if len(daily) >= 2 else daily["Close"].iloc[-1]
        avg_daily_vol = daily["Volume"].iloc[:-1].tail(10).mean()

        # Intraday 5m
        intraday = t.history(period="1d", interval="5m")
        current_price, latest_5m_vol, avg_5m_vol, cum_today_vol = None, None, None, None
        if not intraday.empty:
            last_row = intraday.iloc[-1]
            current_price = last_row["Close"]
            latest_5m_vol = last_row["Volume"]
            avg_5m_vol = intraday["Volume"].mean()
            cum_today_vol = intraday["Volume"].sum()

        # % change alerts
        if current_price and prev_close:
            pchange = (current_price - prev_close) / prev_close * 100
            if pchange <= PCT_DOWN_ALERT:
                send_telegram_message(f"⚠️ {symbol} down {pchange:.2f}% (₹{current_price})")
            elif pchange >= PCT_UP_ALERT:
                send_telegram_message(f"🚀 {symbol} up {pchange:.2f}% (₹{current_price})")

        # volume spike alerts
        if latest_5m_vol and avg_5m_vol and latest_5m_vol >= VOL_5MIN_MULTIPLIER * avg_5m_vol:
            send_telegram_message(f"📈 {symbol} sudden 5-min volume spike! latest={int(latest_5m_vol)} avg5min={int(avg_5m_vol)}")

        if cum_today_vol and avg_daily_vol and cum_today_vol >= CUMULATIVE_DAILY_VOL_MULTIPLIER * avg_daily_vol:
            send_telegram_message(f"📊 {symbol} daily volume {int(cum_today_vol)} > {CUMULATIVE_DAILY_VOL_MULTIPLIER}× avg daily ({int(avg_daily_vol)})")

    except Exception as e:
        print(f"Error checking {symbol}:", repr(e))

def check_news():
    global LAST_NEWS
    for symbol in WATCHLIST:
        url = f"https://gnews.io/api/v4/search?q={symbol}&country=in&lang=en&token={GNEWS_API_KEY}&max=1"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if "articles" in data and len(data["articles"]) > 0:
                article = data["articles"][0]
                headline = article["title"]
                link = article["url"]

                if symbol not in LAST_NEWS or LAST_NEWS[symbol] != headline:
                    LAST_NEWS[symbol] = headline
                    msg = f"📰 {symbol} (India News)\n{headline}\n{link}"
                    send_telegram_message(msg)
        except Exception as e:
            print("News error:", e)

# -------- main loop ----------
if __name__ == "__main__":
    send_telegram_message("🔔 Stock Alert Bot (Price + Volume + India News) started. Watching: " + ", ".join(WATCHLIST))
    while True:
        now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
        if is_market_open_india(now):
            for s in WATCHLIST:
                check_symbol(s)
        check_news()
        time.sleep(CHECK_INTERVAL)
