from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Integer, DateTime, Text, String, Column

import argparse
import os
import sys


db = declarative_base()


class Entry(db):
    __tablename__ = 'entries'

    id = Column(Integer, primary_key=True)
    source = Column(String(400))
    datetime = Column(DateTime)
    content = Column(Text)

    def __init__(self, source, content):
        self.source = source
        self.content = content

    def __repr__(self):
        return self.content


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(
        description="parse a file and put entries in a database")
    argparser.add_argument("filename", help="source file")
    args = argparser.parse_args()
    filename = args.filename
    if not os.path.exists(filename):
        sys.exit('ERROR: File %s was not found!' % filename)

    name = filename.strip('/').split('/')[-1]
    engine = create_engine('sqlite:///{}.db'.format(name))
    Session = sessionmaker(bind=engine)
    session = Session()
    db.metadata.create_all(engine)
