import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src.app import create_app
from src.config import Config

app = create_app()
PORT = Config.PORT

if __name__ == '__main__':
    try:
        from waitress import serve
        print(f"LabManager running on http://0.0.0.0:{PORT} (waitress)")
        serve(app, host='0.0.0.0', port=PORT, threads=4,
              max_request_body_size=5368709120,  # 5GB
              channel_timeout=600,               # 10min for large uploads
              send_bytes=1048576,
              recv_bytes=1048576)
    except ImportError:
        print("waitress not found, using Flask dev server")
        debug = '--debug' in sys.argv
        app.run(host='0.0.0.0', port=PORT, debug=debug)
