import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

# جلب توكن البوت تلقائياً من المتغيرات البيئية في ريندر
TOKEN = os.getenv("TELEGRAM_TOKEN")

@app.post(f"/{TOKEN}")
async def telegram_webhook(request: Request):
    update = await request.json()
    
    # التحقق من استقبال رسالة نصية
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        # منطق الردود
        if text.startswith("/start"):
            reply = "أهلاً بك! أرسل 'volume' لرؤية حجم التداول أو أي رسالة أخرى للترحيب."
        elif "volume" in text.lower() or "ترتيب" in text:
            reply = "📊 **ترتيب حجم التداول (تجريبي):**\n\n1. Bitcoin (BTC)\n2. Ethereum (ETH)\n3. Solana (SOL)\n4. Binance Coin (BNB)"
        else:
            reply = "Hello!"

        # إرسال الرد إلى مستخدم تليغرام
        telegram_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(telegram_url, json=payload)

    return {"status": "ok"}

@app.get("/")
def home():
    return {"status": "Bot is running successfully!"}
  
