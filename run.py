import sys, os

# exe 打包（PyInstaller）时从临时目录加载 src 包
if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.dirname(__file__))

from src.app import create_app
from src.config import Config

app = create_app()
PORT = Config.PORT

if __name__ == '__main__':
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=PORT, threads=8,
              max_request_body_size=5368709120,
              channel_timeout=600,
              send_bytes=1048576,
              recv_bytes=1048576)
    except ImportError:
        debug = '--debug' in sys.argv
        app.run(host='0.0.0.0', port=PORT, debug=debug)
