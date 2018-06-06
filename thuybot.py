import click
import configparser
import logging
import logging.config
import random
import socket
import sys
import time
from slackclient import SlackClient
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException

log = logging.getLogger('thuybot')


class ThuyBot:

    def __init__(self, config):
        self.config = config["DEFAULT"]
        self.slack_client = SlackClient(self.config.get("SLACK_TOKEN"))

    def connect(self):
        self.slack_client.rtm_connect()
        bot_id = self.slack_client.server.login_data["self"]["id"]
        self.config["bot_id"] = bot_id
        log.debug("Connected. Bot id: %s", bot_id)

    def start(self):
        if self.config.get("DAEMON"):  # pragma: no cover
            import daemon
            with daemon.DaemonContext():
                self._start()
        else:
            self._start()

    def _start(self):
        self.connect()
        while self.should_run():
            self.run()
            time.sleep(.1)

    def should_run(self):  # pragma: no cover
        return True

    def run(self):
        try:
            delay = 0
            for message in self.slack_client.rtm_read():
                if self.should_respond(message) and delay < 1:
                    self.process_message(message)
                    delay = 100
                delay = delay - 1
        except (WebSocketConnectionClosedException, WebSocketTimeoutException, socket.timeout) as e:
            log.debug(e)
            self.connect()
        except Exception as e:
            log.exception(e)

    def should_respond(self, message):
        if message.get("user") == self.config.get("bot_id"):
            return False
        watch_channels = [i.strip() for i in self.config.get("watch_channels").split(",")]
        if message.get("channel") in watch_channels:
            return True

    def get_response(self):
        responses = [i.strip() for i in self.config.get("emoji_responses").split(",")]
        return random.choice(responses)

    def process_message(self, message):
        if "user" not in message:
            log.warn("message: %s", message)
            return
        log.debug("responding to message: %s", message)
        resp = self.slack_client.api_call(
            "reactions.add",
            channel=message.get("channel"),
            name=self.get_response(),
            timestamp=message.get("ts")
        )
        if not resp.get('ok'):
            log.warn(resp)


def load_config(config_file, load_logging=True):
    configs = configparser.ConfigParser()
    configs.read(config_file)

    if configs.has_option("DEFAULT", "LOG_CONFIG") and load_logging:
        logging.config.fileConfig(configs.get("DEFAULT", "LOG_CONFIG"))
    else:  # pragma: no cover
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s: %(message)s",
            level=logging.DEBUG)
    log.debug("Config: %s", configs.defaults())
    return configs


@click.command()
@click.option("-c", "--config", default="./config.ini",
              help="Path to the config file.")
def run(config):
    configs = load_config(config)
    log.info("Starting up.")
    try:
        ThuyBot(configs).start()
    except KeyboardInterrupt:  # pragma: no cover
        sys.exit(0)
    except Exception:
        log.exception("Fatal exception")


if __name__ == '__main__':
    run()
