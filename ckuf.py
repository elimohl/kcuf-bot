#!/usr/bin/env python3
import logging
import argparse
from getpass import getpass
from datetime import datetime, timedelta
import os
import re

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Integer, Text, Column, Boolean
from sqlalchemy.sql.expression import func

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout

from generator import generate_reply
from config import you_words, my_nicks  # , reply_nicks
from keras.models import model_from_json


model = model_from_json(open('model_architecture.json').read())
model.load_weights('model_weights.h5')
db = declarative_base()


def get_ready_reply():
    logging.info("Retrieving reply from db")
    not_sent = session.query(Entry).filter(
        Entry.sent == False).order_by(  # NOQA
        func.random()).first()

    if not_sent is None:
        logging.error(
            "There is no entry in db that has not been sent already")
        return ''
    not_sent.sent = True
    session.commit()
    return not_sent.text


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
        self.my_nicks = set(my_nicks + [nick, self.username])
        self.silent_since = datetime.now()
        self.mine = False
        self.after_mine = False
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

    def is_to_me(self, msg):
        if msg['mucnick'] == self.nick:
            return False
        for nick in self.my_nicks:
            if nick in msg['body']:
                return True
        '''
        if msg['mucnick'].lower() not in reply_nicks:
            return False
        '''
        if not self.after_mine:
            return False
        words = msg['body'].lower().split()
        for yword in you_words:
            for word in words:
                if re.match(word, yword + '$'):
                    return True
        return False

    def reply(self, msg):
        if self.is_to_me(msg):
            ans = generate_reply(model, msg)
            if not ans:
                ans = get_ready_reply()
            return ans

        if datetime.now() - self.silent_since > timedelta(hours=5) and\
                12 < datetime.now().hour < 3:
            return get_ready_reply()
        else:
            return None

    def muc_message(self, msg):
        self.after_mine = self.mine
        self.mine = msg['mucnick'] == self.nick
        self.save_msg(msg)
        reply = self.reply(msg)
        if reply:
            self.send_message(mto=msg['from'].bare,
                              mbody=reply,
                              mtype='groupchat')
        self.silent_since = datetime.now()

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
    argparser.add_argument("password", action=PasswordAction,
                           nargs=0, help="password")
    argparser.add_argument("--path", default="logs", help="path/to/logs")
    argparser.add_argument("--room", default=None, help="room to join")
    argparser.add_argument("--nick", default="kcuf", help="nick")
    argparser.add_argument(
        "--loglevel", default="DEBUG",
        choices=['critical', 'info', 'warning',
                 'notset', 'debug', 'error', 'warn'],
        help="log level (default: debug)")
    args = argparser.parse_args()
    level = args.loglevel.upper()
    logging.basicConfig(level=level,
                        format='%(levelname)-8s %(message)s')
    log_dir = os.path.join(os.path.expanduser(args.path), args.jid)
    os.makedirs(log_dir, exist_ok=True)
    engine = create_engine('sqlite:///ready_replies.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    logging.info("Bot's nicks: {}".format(my_nicks))
    xmpp = EchoBot(args.jid, args.password, log_dir,
                   args.room, args.nick, my_nicks)
    xmpp.register_plugin('xep_0045')
    if xmpp.connect():
        xmpp.process(block=True)
        print("Done")
    else:
        print("Unable to connect")
