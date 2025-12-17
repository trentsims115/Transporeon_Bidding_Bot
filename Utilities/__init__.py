from prometheus_client import Gauge
from Utilities.db import start_prometheus_server
from Utilities.Storage import Storage
import os
import json
import sys

def load_config():
    # Determine the top-level directory (where main.py is run from)
    if getattr(sys, "frozen", False):  # support PyInstaller/frozen builds
        base_dir = os.path.dirname(sys.executable)
    else:
        # Get the absolute path of where main.py (the entry script) is located
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    config_path = os.path.join(base_dir, "config.json")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config
    except Exception as e:
        print(f"Could not open config file: {config_path} ({e})")
        return {"on": 0}

config = load_config()
print(config)
storage = Storage(load_config())
iteration_counter = start_prometheus_server(int(storage.config["prometheus_port"]))
