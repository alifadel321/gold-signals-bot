import os
import asyncio
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

app = FastAPI()

# ─── CONFIG ───
TELEGRAM_TOKEN = "8516486092:AAG-AV55bXOJU6xBl5Y-cKClznO_yTTB9Us"
CHAT_ID = "1662349068"   # الـ ID اللي بعثته

bot = Bot(token=TELEGRAM_TOKEN)
application = Application.builder().token(TELEGRAM_TOKEN).build()

# ─── HANDLERS ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبا حياتي! 🌟\n"
        "أنا بوت إشارات الذهب XAUUSD\n"
        "اكتب /signal عشان أعطيك الإشارة الحالية إذا موجودة"
    )

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = get_gold_data()
    if df is None or len(df) < 50:
        await update.message.reply_text("مشكلة في جلب بيانات الذهب حاليًا 😔\nجرب بعد شوية")
        return

    last = df.iloc[-1]
    prev = df.iloc[-2]

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    price = last['Close']
    ema200 = last['EMA200']
    ema9 = last['EMA9']
    ema21 = last['EMA21']
    rsi = last['RSI']
    atr = last['ATR']

    msg = f"<b>إشارة الذهب</b> 🕒 {now_str}\n\n"
    msg += f"السعر الحالي: <b>{price:.2f}</b>\n"
    msg += f"EMA9: {ema9:.2f} | EMA21: {ema21:.2f}\n"
    msg += f"EMA200: {ema200:.2f} | RSI(14): {rsi:.1f}\n\n"

    if price > ema200:
        crossover = (prev['EMA9'] < prev['EMA21']) and (last['EMA9'] > last['EMA21'])
        rsi_ok = 52 < rsi < 70

        if crossover and rsi_ok:
            entry = price
            sl = entry - 1.8 * atr
            tp = entry + 3.0 * atr
            msg += "🟢 <b>إشارة BUY قوية!</b>\n"
            msg += f"دخول ≈ {entry:.2f}\n"
            msg += f"Stop Loss: {sl:.2f}\n"
            msg += f"Take Profit: {tp:.2f}\n"
            msg += "سبب: تقاطع EMA + RSI جيد"
        else:
            msg += "⚪ لا إشارة شراء قوية حاليًا\nانتظر تقاطع أقوى"
    else:
        msg += "🔴 السعر تحت EMA200 → الاتجاه هابط حاليًا\nتجنب الشراء الآن"

    await update.message.reply_text(msg, parse_mode='HTML')

# ─── جلب بيانات الذهب ───
def get_gold_data():
    try:
        df = yf.download('GC=F', period='30d', interval='1h', progress=False)
        if df.empty:
            return None

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df['EMA200'] = ta.ema(df['Close'], length=200)
        df['EMA21']  = ta.ema(df['Close'], length=21)
        df['EMA9']   = ta.ema(df['Close'], length=9)
        df['RSI']    = ta.rsi(df['Close'], length=14)
        df['ATR']    = ta.atr(df['High'], df['Low'], df['Close'], length=14)

        return df.dropna()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("signal", signal))

# ─── WEBHOOK ───
@app.post("/webhook")
async def webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, bot)
        if update:
            await application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error"}

# ─── Startup: set webhook ───
@app.on_event("startup")
async def startup_event():
    domain = os.environ.get('KOYEB_PUBLIC_DOMAIN')
    if not domain:
        domain = "your-app-name.koyeb.app"  # غيّره بعد الديبلوي
    webhook_url = f"https://{domain}/webhook"
    try:
        await bot.set_webhook(url=webhook_url)
        print(f"Webhook set: {webhook_url}")
    except Exception as e:
        print(f"Failed to set webhook: {e}")

@app.get("/")
async def root():
    return {"message": "Gold Signals Bot is running! Use /start or /signal"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
