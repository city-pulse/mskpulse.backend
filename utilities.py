#!/usr/bin/python
# -*- coding: utf-8 -*-
# MSK PULSE backend
# Number of separate utilities without common import

def drange(start, stop, step):
	"""
	Same as range(), but for floats. Fucntion creates iterator.

	Args:
		start (float)
		stop (float)
		step(float)
	"""
	r = start
	while r <= stop+step:
		yield r
		r += step

def escape_md(txt):
	txt = txt.replace('_', '\_')
	txt = txt.replace('*', '\*')
	txt = txt.replace('`', '\`')
	txt = txt.replace('[', '\[')
	txt = txt.replace('(', '\(')
	return txt

def get_circles_centers(bbox, radius=5000, polygons=None):
	"""
	Function calculates centers for circles, that would cover all the bounding box, or area inside polygons. 
	Used to create points for collectors, where radius small enough to matter (Instagram, VKontakte).

	Args:
		bbox (List[float]): long-lat corners for bounding box, that should be covered.
		radius (int): radius of circles, that will cover bounding box, in meters.
		polygons (shapely.geometry.polygon): geo polygon to describe monitoring area more precisely, and exclude some surplus centers.
	"""
	from math import radians, cos
	from itertools import product
	lat = radians(max([abs(bbox[1]), abs(bbox[3])]))
	# Calculate the length of a degree of latitude and longitude in meters
	latlen = 111132.92 - (559.82 * cos(2 * lat)) + (1.175 * cos(4 * lat)) + (-0.0023 * cos(6 * lat))
	longlen = (111412.84 * cos(lat)) - (93.5 * cos(3 * lat)) + (0.118 * cos(5 * lat))
	radius_x = radius/longlen
	radius_y = radius/latlen
	x_marks = [x for x in drange(bbox[0], bbox[2], radius_x)]
	y_marks = [y for y in drange(bbox[1], bbox[3], radius_y)]
	centers = [x for x in product(x_marks[0::2], y_marks[0::2])] + [x for x in product(x_marks[1::2], y_marks[1::2])]
	if polygons:
		cleaned_centers = []
		from shapely.geometry import Point
		from shapely.affinity import scale
		for center in centers:
			circle = scale(Point(center[0], center[1]).buffer(1), xfact=radius_x, yfact=radius_y)
			if polygons.intersects(circle):
				cleaned_centers.append(center)
		centers = cleaned_centers
	return centers

def get_locations(bfile = None, bbox = None, filter_centers = True):
	"""
	Function creates constants for localities for different networks/collectors.
	Called in the settings.py file. Either bfile, or bbox have to be specified.

	Args:
		bfile (str): name of .geojson file with polygons, that cover monitoring area.
		bbox (List[float]): long-lat corners for bounding box (instead of bfile).
		filter_centers (bool): whether to filter surplus centers, based on bounds polygons.
	"""
	if not bfile and not bbox:
		raise BaseException('Neither bounds geojson file, nor bounding box are specified.')
	if bfile:
		from json import load
		from shapely.geometry import shape
		with open(bfile, 'rb') as f:
			BOUNDS = shape(load(f))
		BBOX = list(BOUNDS.bounds)
	else:
		from shapely.geometry import Polygon
		BBOX = bbox
		BOUNDS = Polygon([(BBOX[0], BBOX[1]), (BBOX[0], BBOX[3]), (BBOX[2], BBOX[3]), (BBOX[2], BBOX[1]), (BBOX[0], BBOX[1])])
	if filter_centers:
		polys = BOUNDS
	else:
		polys = None
	TW_LOCATIONS = ','.join([str(x) for x in BBOX])
	VK_LOCATIONS = get_circles_centers(BBOX, radius=4000, polygons=polys)
	IG_LOCATIONS = get_circles_centers(BBOX, radius=5000, polygons=polys)
	return BOUNDS, BBOX, TW_LOCATIONS, VK_LOCATIONS, IG_LOCATIONS

def exec_mysql(cmd, connection):
	"""
	Unified function for MySQL interaction from multiple sources and threads.

	Args:
		cmd (str): command, to be executed.
		connection (PySQLPool.PySQLConnection): connection to the database object.
	"""
	from PySQLPool import getNewQuery
	from MySQLdb import OperationalError
	from logging import error
	query = getNewQuery(connection, commitOnEnd=True)
	try:
		result = query.Query(cmd)
	except OperationalError as e:
		error(e)
	else:
		return query.record, result

def get_mysql_con():
	"""
	Function for creating PySQLPool.PySQLConnection object from settings parameters.
	Additionaly sets up names, and connection charset to utf8mb4.
	"""
	from PySQLPool import getNewPool, getNewConnection
	from settings import MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DB
	getNewPool().maxActiveConnections = 1
	mysql_db = getNewConnection(username=MYSQL_USER, password=MYSQL_PASSWORD, host=MYSQL_HOST, db=MYSQL_DB)
	mysql_db = refresh_mysql_con(mysql_db)
	return mysql_db

def refresh_mysql_con(mysql_db):
	from PySQLPool import getNewQuery
	query = getNewQuery(mysql_db, commitOnEnd=True)
	query.Query('SET NAMES utf8mb4;')
	query.Query('SET CHARACTER SET utf8mb4;')
	query.Query('SET character_set_connection=utf8mb4;')
	query.Query('SET innodb_lock_wait_timeout = 300;')
	return mysql_db

def create_mysql_tables():
	"""
	Function for creating empty MySQL tables, used by Collector and Detector.
	Created tables: 
		tweets (raw messages data);
		media (links to media files in the messages);
		events (table for events, computed by Detector, and archieved);
		event_msgs (foreign key storage for links between messages and events);
		event_trainer (table, containing training set for event classifier);
	"""
	con = get_mysql_con()
	tabs = [
		"""CREATE TABLE `tweets` (`id` varchar(40) NOT NULL DEFAULT '', `text` text, `lat` float DEFAULT NULL, `lng` float DEFAULT NULL, `tstamp` datetime DEFAULT NULL, `user` bigint(40) DEFAULT NULL, `network` tinyint(4) DEFAULT NULL, `iscopy` tinyint(1) DEFAULT NULL, PRIMARY KEY (`id`), KEY `net` (`network`), KEY `latitude` (`lat`), KEY `longitude` (`lng`), KEY `time` (`tstamp`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
		"""CREATE TABLE `media` (`id` int(11) unsigned NOT NULL AUTO_INCREMENT, `tweet_id` varchar(40) DEFAULT NULL, `url` varchar(250) DEFAULT NULL, PRIMARY KEY (`id`), KEY `tweet_id` (`tweet_id`)) ENGINE=InnoDB AUTO_INCREMENT=2128971 DEFAULT CHARSET=utf8mb4;""",
		"""CREATE TABLE `events` (`id` varchar(40) CHARACTER SET utf8mb4 NOT NULL DEFAULT '', `start` datetime DEFAULT NULL, `end` datetime DEFAULT NULL, `msgs` int(11) DEFAULT NULL, `description` text, `dumps` longblob, `verification` tinyint(1) DEFAULT NULL, `validity` tinyint(1) DEFAULT NULL, PRIMARY KEY (`id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
		"""CREATE TABLE `event_msgs` (`id` int(11) NOT NULL AUTO_INCREMENT, `msg_id` varchar(40) DEFAULT NULL, `event_id` varchar(40) DEFAULT NULL, PRIMARY KEY (`id`), UNIQUE KEY `msg_id` (`msg_id`,`event_id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
		"""CREATE TABLE `event_trainer` (`id` int(11) unsigned NOT NULL AUTO_INCREMENT, `verification` tinyint(1) DEFAULT NULL, `dump` longblob, PRIMARY KEY (`id`)) ENGINE=InnoDB AUTO_INCREMENT=1531 DEFAULT CHARSET=utf8mb4;""",
		"""CREATE TABLE `ref_data` (`lat` float DEFAULT NULL, `lng` float DEFAULT NULL, `network` tinyint(4) DEFAULT NULL, `tstamp` date DEFAULT NULL, `second` mediumint(9) DEFAULT NULL, KEY `second` (`second`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
	]
	for tab in tabs:
		exec_mysql(tab, con)

def build_event_classifier(classifier_type="tree", balanced=False, classifier_params={}):
	"""
	Function for creating event classifier, which determines, whether event is real or not.

	Args:
		classifier_type (str): "tree" stands for decision tree, and "adaboost" for AdaBoost Classifier.
		balanced (bool): whether to balance number of true and false samples in training set, or not.
		classifier_params (dict): additional parameters, that would be passed to the classifier object on initialization.
	"""
	from event import Event
	from redis import StrictRedis
	from settings import REDIS_HOST, REDIS_PORT, REDIS_DB
	from random import shuffle
	from datetime import datetime
	from nltk.tokenize import TreebankWordTokenizer
	from pymorphy2 import MorphAnalyzer

	if classifier_type == 'tree':
		from sklearn.tree import DecisionTreeClassifier
		classifier = DecisionTreeClassifier(**classifier_params)
	elif classifier_type == 'adaboost':
		from sklearn.ensemble import AdaBoostClassifier
		classifier = AdaBoostClassifier(**classifier_params)

	mysql_con = get_mysql_con()
	redis_con = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
	morph = MorphAnalyzer()
	tokenizer = TreebankWordTokenizer()

	real_events = []
	fake_events = []

	e_ids = exec_mysql('SELECT id, dumps FROM events WHERE verification IS NOT NULL;', mysql_con)[0]
	for e_id in e_ids:
		event = Event(mysql_con, redis_con, tokenizer, morph)
		event.unpack(e_id['dumps'])
		row = event.classifier_row()
		if event.verification:
			real_events.append(row)
		else:
			fake_events.append(row)
	if min([len(real_events), len(fake_events)]) < 1000:
		e_dumps = exec_mysql('SELECT dump FROM event_trainer;', mysql_con)[0]
		for dump in e_dumps:
			event = Event(mysql_con, redis_con, tokenizer, morph)
			event.unpack(dump['dump'], complete=True)
			row = event.classifier_row()
			if event.verification:
				real_events.append(row)
			else:
				fake_events.append(row)
	if balanced:
		from random import sample
		n = min([len(real_events), len(fake_events)])
		real_events = sample(real_events, n)
		fake_events = sample(fake_events, n)
	events = real_events + fake_events
	result = [1]*len(real_events) + [0]*len(fake_events)
	events = zip(events, result)
	shuffle(events)
	result = [x[1] for x in events]
	events = [x[0] for x in events]
	classifier.fit(events, result)

def migrate_event_dumps():
	from redis import StrictRedis
	from settings import REDIS_HOST, REDIS_PORT, REDIS_DB
	from event import Event
	mysql = get_mysql_con()
	redis = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
	classifier = build_event_classifier(classifier_type="tree", balanced=False)
	for event in exec_mysql('SELECT id FROM events;', mysql)[0]:
		e = Event(mysql, redis, classifier)
		try:
			e.restore(event['id'], new_serializer=False)
		except:
			continue
		else:
			e.backup()

def bot_track(uid, message, name='Message'):
	from json import dumps
	from requests import post
	from settings import TELEGRAM_ANALYTICS_TOKEN
	TRACK_URL = 'https://api.botan.io/track'
	try:
		r = post(
			TRACK_URL,
			params={"token": TELEGRAM_ANALYTICS_TOKEN, "uid": uid, "name": name},
			data=dumps(message),
			headers={'Content-type': 'application/json'},
		)
		return r.json()
	except:
		return False

def bot_shorten_url(url, user_id):
	from settings import TELEGRAM_ANALYTICS_TOKEN
	from requests import get
	SHORTENER_URL = 'https://api.botan.io/s/'
	try:
		return get(SHORTENER_URL, params={
			'token': TELEGRAM_ANALYTICS_TOKEN,
			'url': url,
			'user_ids': str(user_id),
		}).text
	except:
		return url