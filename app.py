import threading
import webview
from backend import create_app


def start_flask_server():
    app = create_app()
    app.run(port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()

    window = webview.create_window(
        'Spending Tracker',
        'http://127.0.0.1:5000',
        width=1100,
        height=760,
        background_color='#0f172a',
    )
    webview.start()
