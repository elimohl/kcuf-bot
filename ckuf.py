#!/usr/bin/env python3
import logging
import argparse
from getpass import getpass
from datetime import datetime
from random import getrandbits
import os

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Integer, Text, Column, Boolean
from sqlalchemy.sql.expression import func

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout


def generate_reply(msg):
    return ">{}\nNo.".format(msg)


def get_ready_reply():
    not_sent = session.query(Entry).filter(
        Entry.sent == False).order_by(  # NOQA
        func.random()).first()

    not_sent.sent = True
    session.commit()
    return not_sent.text


db = declarative_base()


class Entry(db):
    __tablename__ = 'entries'

    rowid = Column(Integer, primary_key=True)
    text = Column(Text)
    sent = Column(Boolean)

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return 'id={} "{}" sent={}'.format(self.rowid, self.text, self.sent)


class EchoBot(ClientXMPP):

    def __init__(self, jid, password, log_dir, room, nick, my_nicks):
        super().__init__(jid, password)
        self.log_dir = log_dir
        self.room = room
        self.nick = nick
        self.my_nicks = my_nicks
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
            # msg.reply("Thanks for sending\n%(body)s" % msg).send()
            # self.save_msg(msg, mine=True)

    def should_reply(self, msg):
        if msg['mucnick'] == self.nick:
            return False
        if self.nick in msg['body']:
            return True
        for nick in self.my_nicks:
            if nick in msg['body']:
                return True
        return False

    def reply(self, msg):
        if getrandbits(1):
            return generate_reply(msg)
        else:
            return get_ready_reply()

    def muc_message(self, msg):
        self.save_msg(msg)
        if self.should_reply(msg):
            self.send_message(mto=msg['from'].bare,
                              mbody=self.reply(msg['body']),
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
            log_file.write(datetime.now().strftime('(%d.%m.%Y %X) '))
            if nick != '':
                log_file.write('{}: '.format(nick))
            log_file.write('{}\n\n'.format(msg['body']))


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
    try:
        with open('my_nicks') as my_nicks_file:
            my_nicks = my_nicks_file.read().splitlines()
    except OSError:
        my_nicks = []
    engine = create_engine('sqlite:///ready_replies.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    logging.info("Bot's nicks: {}".format(my_nicks))
    xmpp = EchoBot(args.jid, args.password, log_dir, args.room, args.nick, my_nicks)
    xmpp.register_plugin('xep_0045')
    if xmpp.connect():
        xmpp.process(block=True)
        print("Done")
    else:
        print("Unable to connect")
