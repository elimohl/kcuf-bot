import logging
import argparse
from getpass import getpass

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout


class EchoBot(ClientXMPP):

    def __init__(self, jid, password):
        ClientXMPP.__init__(self, jid, password)

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)

        # If you wanted more functionality, here's how to register plugins:
        # self.register_plugin('xep_0030') # Service Discovery
        # self.register_plugin('xep_0199') # XMPP Ping

        # Here's how to access plugins once you've registered them:
        # self['xep_0030'].add_feature('echo_demo')

        # If you are working with an OpenFire server, you will
        # need to use a different SSL version:
        # import ssl
        # self.ssl_version = ssl.PROTOCOL_SSLv3

    def session_start(self, event):
        self.send_presence()
        self.get_roster()

        # Most get_*/set_* methods from plugins use Iq stanzas, which
        # can generate IqError and IqTimeout exceptions
        #
        # try:
        #     self.get_roster()
        # except IqError as err:
        #     logging.error('There was an error getting the roster')
        #     logging.error(err.iq['error']['condition'])
        #     self.disconnect()
        # except IqTimeout:
        #     logging.error('Server is taking too long to respond')
        #     self.disconnect()

    def message(self, msg):
        if msg['type'] in ('chat', 'normal'):
            msg.reply("Thanks for sending\n%(body)s" % msg).send()


class PasswordAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string):
        password = getpass()
        setattr(namespace, self.dest, password)


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(
        description="kcuf bot")
    argparser.add_argument("jid", help="JID")
    argparser.add_argument("password", action=PasswordAction, nargs=0, help="password")
    argparser.add_argument("--loglevel", default="DEBUG",
        choices=['critical', 'info', 'warning', 'notset', 'debug', 'error', 'warn'],
        help="log level (default: debug)")
    args = argparser.parse_args()
    level = args.loglevel.upper()

    logging.basicConfig(level=level,
                        format='%(levelname)-8s %(message)s')

    xmpp = EchoBot(args.jid, args.password)
    xmpp.connect()
    xmpp.process(block=True)
