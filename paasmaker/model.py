#!/usr/bin/env python

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

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


def init_db(engine):
	Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
	init_db()
