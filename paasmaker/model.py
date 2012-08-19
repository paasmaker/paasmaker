#!/usr/bin/env python

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:////tmp/test.db', convert_unicode=True, echo=True)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

class Node(Base):
	__tablename__ = 'node'

	id = Column(Integer, primary_key=True)
	name = Column(String)
	route = Column(String)

	def __init__(self, name, route):
		self.name = name
		self.route = route

	def __repr__(self):
		return "<Node('%s','%s')>" % (self.name, self.route)


def init_db():
	Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
	init_db()
