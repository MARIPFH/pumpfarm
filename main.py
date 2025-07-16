from flask import Flask, request, jsonify
import os
import requests
import time
import json
import logging

app = Flask(__name__)

# === CONFIGURATION ===
CONFIG_FILE = "config.json"
SECRET_KEY = os.environ.get("SECRET_KEY", "123456")
WUNDERTRADING_WEBHOOK_URL = os.environ.get("WUNDERTRADING_WEBHOOK_URL", "https://api.wundertrading.com/api/v1/...")

logging.basicConfig(level=logging.INFO)

# Load config
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

@app.route("/", methods=["GET"])
def index():
    return "✅ PumpFarm PRO Webhook is running"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        config = load_config()
        data = request.json

        # 1. Validate secret key
        if data.get("secret") != SECRET_KEY:
            logging.warning("⛔️ Invalid secret key")
            return jsonify({"status": "error", "message": "Invalid secret"}), 403

        # 2. Validate symbol
        symbol = data.get("symbol", "").upper()
        if symbol not in config["ALLOWED_SYMBOLS"]:
            logging.warning(f"⛔️ Symbol not allowed: {symbol}")
            return jsonify({"status": "ignored", "message": "Symbol not allowed"}), 200

        # 3. Check price change %
        price_change = float(data.get("price_change", 0))
        if price_change < config["MIN_PRICE_CHANGE_PERCENT"]:
            logging.info(f"🔁 Insufficient price change: {price_change}%")
            return jsonify({"status": "ignored", "message": "Pump too small"}), 200

        # 4. Check volume
        volume = float(data.get("volume_usdt", 0))
        if volume < config["MIN_VOLUME_USDT"]:
            logging.info(f"🔁 Volume too low: {volume}")
            return jsonify({"status": "ignored", "message": "Volume too low"}), 200

        # 5. Time filter
        hour = int(time.gmtime().tm_hour)
        if config["USE_TIME_FILTER"] and (hour < config["TRADE_START_HOUR"] or hour > config["TRADE_END_HOUR"]):
            logging.info("🕓 Outside trading hours")
            return jsonify({"status": "ignored", "message": "Outside trading hours"}), 200

        # ✅ Send signal to WunderTrading
        payload = {
            "pair": symbol,
            "side": "buy",
            "type": "market",
            "leverage": config["LEVERAGE"],
            "takeProfit": config["TAKE_PROFIT_PERCENT"],
            "stopLoss": config["STOP_LOSS_PERCENT"],
            "amount": config["AMOUNT"]
        }

        response = requests.post(WUNDERTRADING_WEBHOOK_URL, json=payload)
        logging.info(f"📤 Signal sent to WunderTrading: {response.status_code}")

        return jsonify({"status": "success", "message": "Signal forwarded"}), 200

    except KeyError as ke:
        logging.error(f"❌ Config key missing: {str(ke)}")
        return jsonify({"status": "error", "message": f"Missing config key: {str(ke)}"}), 500

    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
