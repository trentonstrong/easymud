#!/usr/bin/env python

import logging
try:
    from importlib import import_module
except ImportError:
    from simplemud.importlib import import_module
import tornado.auth
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import os.path
from tornado.options import define, options
import tornado.platform.twisted
tornado.platform.twisted.install()
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory, Protocol
from twisted.conch.telnet import StatefulTelnetProtocol

from commands import dispatch
from mud import World
from session import Session

define("port", default=8888, help="run websocket handler on the given port", type=int)
define("telnetport", default=4000, help="run telnet handler ont he given port", type=int)
define("world", default="world", help="path to world definition file", type=str)
define("debug", default=False, help="run server in debug mode with autoreloading", type=bool)
define("tick", default=60, help="tick interval in seconds", type=int)

"""
Woohoo!  A big giant global world object.  Don't worry, other modules aren't
aware of this global as we inject it as a dependency to all objects that need
a reference to it.
"""
world = None


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", RootHandler),
            (r"/socket", SocketHandler),
        ]
        settings = dict(
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            #login_url="/auth/login",
            debug=options.debug,
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "www"),
            xsrf_cookies=True,
            autoescape="xhtml_escape",
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class RootHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class SocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        logging.info("Connected: websocket")
        self.device = 'web'
        self.session = Session(self, world)
        self.session.start()

    def on_message(self, message):
        dispatch(self.session, message.strip())


class MudTelnetProtocol(StatefulTelnetProtocol):
    def connectionMade(self):
        logging.info("Connected: telnet")
        self.device = 'telnet'
        self.session = Session(self, world)
        self.session.start()

    def lineReceived(self, line):
        logging.debug("DEBUG: lineReceived called with %s" % line)
        dispatch(self.session, line.strip())

    def write_message(self, message):
        self.transport.write(str(message))
        self.clearLineBuffer()

    def connectionLost(self, reason):
        logging.debug("DEBUG: connectionLost called with: %s" % str(reason))


def main():
    global world
    tornado.options.parse_command_line()

    # configure logging
    log_level = logging.DEBUG if options.debug else logging.INFO
    logging.basicConfig(level=log_level)

    # init world singleton
    world_module = import_module(options.world)
    world = World(world_module.world)

    # configure the Telnet server
    factory = ServerFactory()
    factory.protocol = MudTelnetProtocol
    reactor.listenTCP(options.telnetport, factory)

    # configure tick interrupt
    ticker = tornado.ioloop.PeriodicCallback(world.tick, options.tick * 1000)
    ticker.start()

    # start the server!
    app = Application()
    app.listen(options.port)
    logging.info("Listening on port %d" % options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
