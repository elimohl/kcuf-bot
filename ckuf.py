import logging
import argparse
from getpass import getpass
import os

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout


class EchoBot(ClientXMPP):

    def __init__(self, jid, password, log_dir, room, nick):
        super().__init__(jid, password)
        self.log_dir = log_dir
        self.room = room
        self.nick = nick
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)
        self.add_event_handler("groupchat_message", self.muc_message)

    def session_start(self, event):
        self.send_presence()
        try:
            self.get_roster()
        except IqError as err:
            logging.error('There was an error getting the roster')
            logging.error(err.iq['error']['condition'])
            self.disconnect()
        except IqTimeout:
            logging.error('Server is taking too long to respond')
            self.disconnect()
        if self.room is not None:
            self.plugin['xep_0045'].joinMUC(self.room, self.nick, wait=True)

    def message(self, msg):
        if msg['type'] in ('chat', 'normal'):
            self.save_msg(msg)
            msg.reply("Thanks for sending\n%(body)s" % msg).send()
            self.save_msg(msg, mine=True)

    def muc_message(self, msg):
        self.save_msg(msg)
        if msg['mucnick'] != self.nick and self.nick in msg['body']:
            self.send_message(mto=msg['from'].bare,
                              mbody="I heard that, %s." % msg['mucnick'],
                              mtype='groupchat')

    def save_msg(self, msg, mine=False):
        if mine:
            log_filename = os.path.join(self.log_dir, msg['to'].bare)
            nick = self.boundjid.user
        else:
            log_filename = os.path.join(self.log_dir, msg['from'].bare)
            if msg['type'] == 'groupchat':
                nick = msg['mucnick']
            else:
                nick = msg['from'].user
        with open(log_filename, 'a') as log_file:
            if nick != '':
                log_file.write(nick + ': ')
            log_file.write(msg['body'] + '\n\n')


class PasswordAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string):
        password = getpass()
        setattr(namespace, self.dest, password)


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(
        description="kcuf bot")
    argparser.add_argument("jid", help="JID")
    argparser.add_argument("password", action=PasswordAction, nargs=0, help="password")
    argparser.add_argument("--path", default="logs", help="path/to/logs")
    argparser.add_argument("--room", default=None, help="room to join")
    argparser.add_argument("--nick", default="kcuf", help="nick")
    argparser.add_argument(
        "--loglevel", default="DEBUG",
        choices=['critical', 'info', 'warning', 'notset', 'debug', 'error', 'warn'],
        help="log level (default: debug)")
    args = argparser.parse_args()
    level = args.loglevel.upper()
    logging.basicConfig(level=level,
                        format='%(levelname)-8s %(message)s')
    log_dir = os.path.join(os.path.expanduser(args.path), args.jid)
    os.makedirs(log_dir, exist_ok=True)

    xmpp = EchoBot(args.jid, args.password, log_dir, args.room, args.nick)
    xmpp.register_plugin('xep_0045')
    if xmpp.connect():
        xmpp.process(block=True)
        print("Done")
    else:
        print("Unable to connect")
