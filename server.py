# api_server.py
import json, os
from flask import Flask, request, jsonify
from flask_cors import CORS
from Utilities import storage
import re

app = Flask(__name__)
CORS(app)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def save_config(data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Could not save config.json: {e}")

@app.route('/toggle-on', methods=['GET'])
def toggle_on():
    print("Toggled on/off")
    storage.config["on"] = 0 if storage.config["on"] else 1
    save_config(storage.config)
    return storage.config, 200

@app.route('/toggle-bidding', methods=['GET'])
def toggle_bidding():
    print("Toggle Bidding")
    storage.config["bidding"] = 0 if storage.config["bidding"] else 1
    save_config(storage.config)
    return {"status": "ok", "on": storage.config["bidding"]}, 200

@app.route('/status', methods=['GET'])
def status():
    return {"on": storage.config["on"], "bidding": storage.config["bidding"]}, 200

@app.route('/reload-rules', methods=['GET'])
def reload_rules():
    print("reloading rules")
    storage.load_data()
    return {"status": "rules reloaded"}, 200

# ---------- NEW: schedule endpoints ----------
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_VALID_DAYS = {"Mon","Tue","Wed","Thu","Fri","Sat","Sun"}

@app.get('/schedule')
def get_schedule():
    return jsonify(storage.config.get("schedule", {})), 200

@app.put('/schedule')
def set_schedule():
    data = request.get_json(force=True) or {}
    enabled = bool(data.get("enabled", False))
    tz = (data.get("timezone") or "America/Chicago").strip()
    days = data.get("days") or []
    start = (data.get("start") or "08:00").strip()
    end = (data.get("end") or "17:00").strip()

    # validate
    days = [d.strip() for d in days if d and d.strip() in _VALID_DAYS]
    if not _TIME_RE.match(start): return {"error":"invalid start (HH:MM 24h)"}, 400
    if not _TIME_RE.match(end):   return {"error":"invalid end (HH:MM 24h)"}, 400

    storage.config["schedule"] = {
        "enabled": enabled,
        "timezone": tz,
        "days": days,
        "start": start,
        "end": end,
    }
    save_config(storage.config)
    return jsonify(storage.config), 200

@app.get('/prometheus-port')
def get_prometheus_port():
    return jsonify(storage.config.get("prometheus_port", {})), 200

@app.put('/prometheus-port/<port>')
def set_prometheus_port(port):
    storage.config['prometheus_port'] = int(port)
    save_config(storage.config)
    return jsonify(storage.config), 200

def start_api_server(host="0.0.0.0", port=8001):
    # IMPORTANT: disable reloader so the server doesn't spawn twice in a thread
    app.run(host=host, port=port, debug=False, use_reloader=False)


