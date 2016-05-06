#!/usr/bin/python
# -*- coding: utf-8 -*-
# MSK.PULSE backend

from telegram import Emoji, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardHide
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from redis import StrictRedis
from settings import REDIS_HOST, REDIS_PORT, REDIS_DB, TELEGRAM_BOT_TOKEN
from utilities import exec_mysql, get_mysql_con
from random import sample
from event import EventLight
from utilities import bot_track
from MySQLdb import escape_string
from msgpack import packb, unpackb

import logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

CONTEXT = {}

TEXTS = {
'help.regular':"""Welcome to our bot-newsroom. Our media is fully controlled by bots. Journalists-bots scan social media, and look for newsbreaks. Editor-bot selects events, that you may be interested in. And I'm, the anchor-bot from Telegram, broadcasting news to you.

You can control me by sending these commands:

/now - Current event list
/trending - Top recent events""",

'help.admin':"""Welcome to our bot-newsroom. Our media is fully controlled by bots. Journalists-bots scan social media, and look for newsbreaks. Editor-bot selects events, that you may be interested in. And I'm, the anchor-bot from Telegram, broadcasting news to you.

You can control me by sending these commands:

/now - Current event list
/trending - Top recent events
/teach - Training Editor-bot to distinguish real events from white noise""",

'teach.start':"""That's great! Let's improve my skill of event detecting. I will show you random social media messages clusters, and you should answer, if it is a real newsbreak. Got tired? Press "Break".""",

'teach.placeholder':"""Wait, while we are loading an event...""",

'teach.nodata':"""Unfortunately, there is nothing to classify yet. Come back later.""",

'teach.finish':"""Ok. That's enough for now. Let's have a break.""",
}

updater = Updater(token=TELEGRAM_BOT_TOKEN)
dispatcher = updater.dispatcher
redis_con = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
mysql_con = get_mysql_con()

def role_dispatcher(role=None):
	def decorator(func):
		def wrapper(bot, update):
			users = {'admin':redis_con.smembers("admins"), 'tester':redis_con.smembers("testers")}
			if role and role in users.keys() and str(update.message.from_user.id) in users[role]:
				return func(bot, update)
			elif not role:
				if str(update.message.from_user.id) in users['admin']:
					return func(bot, update, role='admin')
				elif str(update.message.from_user.id) in users['tester']:
					return func(bot, update, role='tester')
				else:
					return func(bot, update, role='other')
		return wrapper
	return decorator

def send_stat(func):
	def wrapper(bot, update):
		if getattr(update, 'message', None):
			user = update.message.from_user
			event_dict = update.message.to_dict()
			action = update.message.text
		elif getattr(update, 'callback_query', None):
			user = update.callback_query.from_user
			event_dict = update.callback_query.to_dict()
			action = update.callback_query.data
		else:
			user = 'unknown'
			event_dict = {}
			action = 'unknown'
		bot_track(user, event_dict, action)
		return func(bot, update)
	return wrapper

@send_stat
@role_dispatcher()
def start_command(bot, update, role):
	if role == 'admin':
		bot.sendMessage(chat_id=update.message.chat_id, text=TEXTS['help.admin'])
	elif role == 'tester':
		bot.sendMessage(chat_id=update.message.chat_id, text=TEXTS['help.regular'])

@send_stat
@role_dispatcher()
def help_command(bot, update, role):
	if role=='admin':
		bot.sendMessage(chat_id=update.message.chat_id, text=TEXTS['help.admin'])
	else:
		bot.sendMessage(chat_id=update.message.chat_id, text=TEXTS['help.regular'])

@role_dispatcher("admin")
def teach_command(bot, update):
	global CONTEXT
	bot.sendMessage(chat_id=update.message.chat_id, text=TEXTS['teach.start'], reply_markup=ReplyKeyboardHide())
	msg = bot.sendMessage(chat_id=update.message.chat_id, text=TEXTS['teach.placeholder'])
	CONTEXT[str(update.message.from_user.id)] = {'chat':msg.chat_id, 'message':msg.message_id}
	publish_event(bot, str(update.message.from_user.id))

@send_stat
def confirm_value(bot, update):
	query = update.callback_query
	user = str(query.from_user.id)
	verific_dict = {'teach.real':1, 'teach.fake':0}
	global CONTEXT
	if user in CONTEXT.keys():
		q = 'SELECT dumps FROM events WHERE id = "{}";'.format(CONTEXT[user]['event'])
		data = unpackb(exec_mysql(q, mysql_con)[0][0]['dumps'])
		if query.data in ['teach.real', 'teach.fake']:
			data['verification'] = int(verific_dict[query.data])
			data = packb(data)
			q = b'''UPDATE events SET dumps = "{}", verification = {} WHERE id = "{}";'''.format(escape_string(data), verific_dict[query.data], CONTEXT[user]['event'])
			exec_mysql(q, mysql_con)
			bot.answerCallbackQuery(query.id, text="Ok!")
			publish_event(bot, user)
		elif query.data == 'teach.more_data':
			publish_event(bot, user, True)
		elif query.data == 'teach.finish':
			bot.sendMessage(text=TEXTS['teach.finish'], chat_id=CONTEXT[user]['chat'], reply_markup=ReplyKeyboardHide())
			del CONTEXT[user]
		else:
			bot.answerCallbackQuery(query.id, text="Strange answer...")
	else:
		bot.answerCallbackQuery(query.id, text="What we were talking about?")

def publish_event(bot, user, republish_full = False):
	global CONTEXT
	keyboard = InlineKeyboardMarkup(
		[[InlineKeyboardButton(Emoji.WHITE_HEAVY_CHECK_MARK.decode('utf-8')+' Real', callback_data='teach.real'),
		InlineKeyboardButton(Emoji.CROSS_MARK.decode('utf-8')+' Fake', callback_data='teach.fake'),
		InlineKeyboardButton(Emoji.BLACK_QUESTION_MARK_ORNAMENT.decode('utf-8')+' Add data', callback_data='teach.more_data'),
		InlineKeyboardButton(Emoji.BACK_WITH_LEFTWARDS_ARROW_ABOVE.decode('utf-8')+' Break', callback_data='teach.finish'),
		]])
	if not republish_full:
		try:
			event = get_random_event()
		except ValueError:
			bot.sendMessage(text=TEXTS['teach.nodata'], chat_id=CONTEXT[user]['chat'], reply_markup=ReplyKeyboardHide())
			del CONTEXT[user]
			return
		else:
			CONTEXT[user]['event'] = event.id
			CONTEXT[user]['event_dump'] = event
			txt = event.representation1()
	else:
		txt = CONTEXT[user]['event_dump'].representation1(full=True)
	txt = txt.decode('utf-8', errors='replace')
	bot.editMessageText(text=txt, chat_id=CONTEXT[user]['chat'], message_id=CONTEXT[user]['message'], reply_markup=keyboard, parse_mode="Markdown")

def get_random_event():
	q = 'SELECT * FROM events WHERE verification IS NULL AND description != "" ORDER BY end DESC LIMIT 5;'
	data = exec_mysql(q, mysql_con)[0]
	data = sample(data,1)[0]
	event = EventLight(start=data['start'], end=data['end'], validity=data['validity'], description=data['description'], dump=data['dumps'], mysql_con=mysql_con)
	return event

def error(bot, update, error):
	logging.warning('Update "%s" caused error "%s"' % (update, error))

dispatcher.addHandler(CommandHandler('start', start_command))
dispatcher.addHandler(CommandHandler('help', help_command))
dispatcher.addHandler(CommandHandler('teach', teach_command))
dispatcher.addHandler(CallbackQueryHandler(confirm_value))
dispatcher.addErrorHandler(error)

updater.start_polling()
updater.idle()