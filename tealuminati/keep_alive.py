import logging
from threading import Thread

from flask import Flask

from tealuminati import config

log = logging.getLogger(__name__)

app = Flask("tealuminati")


@app.route("/")
def home():
    return "Bot running"


def start_keep_alive():
    thread = Thread(target=lambda: app.run(host="0.0.0.0", port=config.KEEP_ALIVE_PORT), daemon=True)
    thread.start()
    log.info("Keep-alive server on port %s", config.KEEP_ALIVE_PORT)
