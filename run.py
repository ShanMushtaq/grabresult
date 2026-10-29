"""GrabResult entry point: python run.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"GrabResult running at http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
