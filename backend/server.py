# server.py
import os
# import pandas as pd
# from pathlib import Path
from app import create_app

app = create_app()

if __name__ == "__main__":
    # p = Path.cwd() / "app" / "workout" / "exercises.json"

    # print(f"Loading exercises from {p}")
    # if not p.exists():
    #     raise FileNotFoundError(f"exercises.json not found at {p}")

    # d = pd.read_json(p)

    port = int(os.environ.get("PORT", 5000))  # <-- use $PORT if present
    app.run(host="0.0.0.0", port=port, debug=True)


