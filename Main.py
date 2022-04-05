import traceback

from Config import TELEGRAM_TOKEN, ADMIN_ID
import time
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import os
from Classes import View
import logging



# Telegram Init
# Messages parser: Markdown
MD = telegram.ParseMode.MARKDOWN
VIEW = View()


# Send error using update and context
def send_error_uc(update, context, error, user):
    if user != ADMIN_ID:
        update.message.reply_text(text=f'*ERROR!*\nThe administrator has been notified', parse_mode=MD)
    context.bot.send_message(chat_id=ADMIN_ID, text=f'User {user} encountered an error\n\nError: {error}')
    return


def send_error_b(sub_bot, user, error):
    if user != ADMIN_ID:
        sub_bot.send_message(chat_id=user, text=f'*ERROR!*\nThe administrator has been notified', parse_mode=MD)
    sub_bot.send_message(chat_id=ADMIN_ID, text=f'User {user} encountered an error\n\nError: {error}')
    return


# /start COMMAND
def start(update, context):
    user = update.message.from_user.id  # Telegram User's ID

    # Get message's body
    text = VIEW.start(user_id=user)

    update.message.reply_text(text, parse_mode=MD)


# /status COMMAND
def status(update, context):
    user = update.message.from_user.id  # Telegram User's ID

    # Get message's body
    text = VIEW.status(user_id=user)

    # The message will contain many links, so link preview is disabled
    update.message.reply_text(text, parse_mode=MD, disable_web_page_preview=True)


# /add *LINK* COMMAND
def add(update, context):
    user = update.message.from_user.id  # Telegram User's ID
    content = update.message.text       # Message's content

    result, text = VIEW.add(user_id=user, text=content)

    if result == -1:
        send_error_uc(update, context, text, user)
        return

    update.message.reply_text(text, parse_mode=MD)


# /remove COMMAND
def remove(update, context):
    user = update.message.from_user.id  # Telegram User's ID

    # Call VIEW's remove function
    result, data = VIEW.remove(user_id=user)

    # If Unexpected Error: notify ADMIN and user. data is String
    if result == -1:
        send_error_uc(update, context, data, user)
        return

    # If Error: notify user. data is String
    if result == 0:
        update.message.reply_text(data, parse_mode=MD)
        return

    # Else: Build the buttons layout. data is Dict
    buttons_layout = []

    # For every link's ID and name
    for link_id, link_name in data.items():
        # Example
        # Button = Name with callback_data = "rem|5". 5 is the link_id to be removed (if selected by the user)
        link_button = [
            InlineKeyboardButton(
                link_name,
                callback_data=f'rem|{link_id}'
            )
        ]
        buttons_layout.append(link_button)

    # Add an exit button
    buttons_layout.append([
        InlineKeyboardButton(
            'Exit',
            callback_data=f'exit|0'
        )
    ])

    # "Render" the button list
    update.message.reply_text('What do you want to unfollow?', reply_markup=InlineKeyboardMarkup(buttons_layout))


# /settings COMMAND
def settings(update, context):
    user = update.message.from_user.id  # Telegram User's ID

    # Call VIEW's settings function
    result, data = VIEW.settings(user_id=user)

    # If Unexpected Error: notify ADMIN and user. data is String
    if result == -1:
        send_error_uc(update, context, data, user)
        return

    # If Error: notify user. data is String
    if result == 0:
        update.message.reply_text(data, parse_mode=MD)
        return

    # Else: Build the buttons layout. data is Dict
    buttons_layout = []

    # For every link's ID and name
    for setting_id, setting_data in data.items():
        setting = setting_data['Setting']
        setting_name = setting_data['SettingName']
        current_setting = setting_data['CurrentSettings']

        # Example
        # Button = Name with callback_data = "show_setting|5/skip_language". 5 is the setting_id to be
        # changed (if selected by the user). skip_language is the setting's name in the database
        setting_button = [
            InlineKeyboardButton(
                f'{setting_name}: {current_setting}',
                callback_data=f'show_setting|{setting_id}/{setting_name}/{setting}'
            )
        ]

        buttons_layout.append(setting_button)

    # Add an exit button
    buttons_layout.append([
        InlineKeyboardButton(
            'Exit',
            callback_data=f'exit|0'
        )
    ])

    # "Render" the button list
    update.message.reply_text('What setting do you want to change?', reply_markup=InlineKeyboardMarkup(buttons_layout))


# Manage buttons
def button(update, context):
    event = update.callback_query          # Telegram's event
    user = event.from_user.id              # Telegram User's ID
    old_msg_id = event.message.message_id  # Old Telegram message's ID. Used to edit the previous message

    action, action_arguments = event.data.split('|')  # Split action from arguments on '_'

    # If the action is 'exit', delete the last message
    if action == 'exit':
        context.bot.delete_message(chat_id=user, message_id=old_msg_id)
        return

    text = ''

    # If action is 'rem', remove selected link' id
    if action == 'rem':
        result, text = VIEW.remove(user_id=user, link_id=action_arguments)

        # If VIEW.remove returns an error
        if result == -1:
            send_error_uc(update, context, text, user)
            return

    # If action is 'show_setting', build the next phase buttons
    if action == 'show_setting':
        setting_id, setting_name, setting = action_arguments.split('/')  # Split setting's id and option on '_'

        # Call the VIEW.settings function to get options
        _, data = VIEW.settings(user_id=user, setting=setting)

        buttons_layout = []

        # For every option
        for option_name, option_value in data.items():
            # Append the option to buttons_layout
            buttons_layout.append([
                InlineKeyboardButton(
                    f'{option_name}',
                    callback_data=f'set_setting|{setting_id}/{option_value}'
                )
            ])

        # Add an exit button
        buttons_layout.append([
            InlineKeyboardButton(
                'Exit',
                callback_data=f'exit|0'
            )
        ])

        # Edit the last message (old_msg_id)
        context.bot.edit_message_text(
            f'Enable/Disable *{setting_name}*',
            reply_markup=InlineKeyboardMarkup(buttons_layout),
            chat_id=user,
            message_id=old_msg_id,
            parse_mode=MD
        )

        return

    # If action is 'set_setting'
    if action == 'set_setting':
        setting_id, setting_value = action_arguments.split('/')  # Split setting's id and value on '_'

        # Call the VIEW.settings function to edit the value
        result, text = VIEW.settings(user_id=user, setting_id=setting_id, value=setting_value)

        # If VIEW.settings returns and error
        if result == -1:
            send_error_uc(update, context, text, user)
            return

    # Edit the last message with the corresponding text, if necessary
    context.bot.edit_message_text(text, chat_id=user, message_id=old_msg_id, parse_mode=MD)


def error(update, context):  # TODO
    context.bot.send_message(chat_id=ADMIN_ID, text=f"Errore da: {context.bot.first_name}\n\nErrore: {context.error}")


# Just a /ping command to know if the bot is running
def ping(update, context):
    user = update.message.from_user.id  # Telegram User's ID
    if user != ADMIN_ID:
        return
    update.message.reply_text("pong")


def main():  # TODO
    print("BOT STARTED")
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    # Dispatcher gestore degli eventi
    dp = updater.dispatcher

    # Comandi e Callback
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("add", add))
    dp.add_handler(CommandHandler("remove", remove))
    dp.add_handler(CommandHandler("settings", settings))
    dp.add_handler(CommandHandler("ping", ping))

    # Bottone premuto
    dp.add_handler(CallbackQueryHandler(button))

    # Errori
    # dp.add_error_handler(error)

    updater.start_polling()
    return updater
    # updater.idle()


if __name__ == "__main__":
    updater = main()
    bot = updater.bot

    try:
        while "RUNNING":
            data = VIEW.get_messages()
            for message_id, message_data in data.items():
                user_id, message = message_data
                try:
                    bot.send_message(chat_id=user_id, text=message, parse_mode=MD)
                    VIEW.message_set_sent(message_id)
                except:
                    send_error_b(bot, ADMIN_ID, f"Error while sending message: **{message_id}**")
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit) as e:
        print(f"INTERRUPT: {e}")
        updater.stop()
        exit()
    except Exception as e:
        send_error_b(bot, ADMIN_ID, traceback.format_exc())
