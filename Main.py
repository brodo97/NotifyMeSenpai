from Config import TELEGRAM_TOKEN, ADMIN_ID
import time
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from crontab import CronTab
import os

# Telegram Init
# Messages parser: Markdown
MD = telegram.ParseMode.MARKDOWN


# Send error using update and context
def send_error_uc(update, context, error, user):
    if user != ADMIN_ID:
        update.message.reply_text(text=f"*ERROR!*\nThe administrator has been notified", parse_mode=MD)
    context.bot.send_message(chat_id=ADMIN_ID, text=f"User {user} encountered an error\n\nError: {error}")
    return


def send_error_b(sub_bot, user, error):
    if user != ADMIN_ID:
        sub_bot.send_message(chat_id=user, text=f"*ERROR!*\nThe administrator has been notified", parse_mode=MD)
    sub_bot.send_message(chat_id=ADMIN_ID, text=f"User {user} encountered an error\n\nError: {error}")
    return


def start(update, context):
    user = update.message.from_user.id
    # TODO: USER INSERTION INTO DB
    update.message.reply_text(f"Hi!\nUse following commands:\n/add to follow something\n/remove to remove it")


def status(update, context):
    result, data = Model.get_nhentai(user)
    if result is False:
        send_error_uc(update, context, data, user)
        return
    nhentai = ""
    if data:
        for category, cat_data in data.items():
            nhentai += f"Categoria: *{category}*\n"
            for x, entry_data in enumerate(cat_data):
                nhentai += f"*{x + 1}*) [{entry_data['Name']}]({entry_data['Link']})\n"
            nhentai += "\n"
    else:
        nhentai = "*NESSUNO*"

    update.message.reply_text(f"""Controllo ogni *{gettime(CheckTime)}*\n\nLink nhentai che segui:\n{nhentai}\n\nNuovi capitoli che attendi:\n{anyhentai}""", parse_mode=MD, disable_web_page_preview=True)


def add(update, context):
    user = update.message.from_user.id
    if user not in users:
        return
    text = update.message.text
    if len(text.split(" ")) > 1:
        link = text.split(" ")[1]
        if "nhentai" in link:
            result, data = Model.add_nhentai(user, link)
        else:
            result, data = Model.add_hentainexus_artist(user, link)
        if result == -1:
            if user != ADMIN_ID:
                send_error_uc(update, context, data, user)
            else:
                context.bot.send_message(chat_id=ADMIN_ID, text=f"Errore da: {context.bot.first_name}\n\nErrore: {error}")
        else:
            update.message.reply_text(data, parse_mode=MD)
    else:
        update.message.reply_text(f"Usa /add *LINK* per aggiungere un link da seguire", parse_mode=MD)


def remove(update, context):
    user = update.message.from_user.id
    if user not in users:
        return

    choices = InlineKeyboardMarkup([[InlineKeyboardButton("nhentai", callback_data="remlist_nhentai")]])
    update.message.reply_text("Sito di riferimento?", reply_markup=choices)



def changelog(update, context):
    user = update.message.from_user.id
    if user not in users:
        return

    result, data = Model.get_version_changelog()
    if result is False:
        send_error_uc(update, context, data, user)
        return

    context.bot.sendDocument(chat_id=user, document=open(os.path.join(This_Folder, "data", data), 'rb'))


def button(update, context):
    event = update.callback_query
    user = event.from_user.id
    msg_id = event.message.message_id

    if user not in users:
        context.bot.edit_message_text(f"Non autorizzato", chat_id=user, message_id=msg_id)
        return

    new_text = ""
    new_btns = None
    action, id = event.data.split("_")
    if action == "remlist":
        if id == "nhentai":
            result, data = Model.get_nhentai(user)
        else:
            result, data = Model.get_hentainexus_artists(user)

        if result is False:
            send_error_uc(update, context, data, user)
            return

        entries = []
        for category, cat_data in data.items():
            for entry in cat_data:
                entries.append([InlineKeyboardButton(entry["Name"] + f" ({category})", callback_data=f"rem{id}_{entry['ID']}")])

        if len(entries) == 0:
            new_text = f"Non segui link {id}"
        else:
            new_text = f"Lista dei link *{id}* che segui"
            new_btns = InlineKeyboardMarkup(entries)
    elif action == "remnhentai":
        result, data = Model.remove_nhentai(id)
        if result == -1:
            send_error_uc(update, context, data, user)
            return
        new_text = data
    elif action == "remHentaiNexus":
        result, data = Model.remove_hentainexus_artist(id)
        if result == -1:
            send_error_uc(update, context, data, user)
            return
        new_text = data

    if new_btns is None:
        context.bot.edit_message_text(new_text, chat_id=user, message_id=msg_id, parse_mode=MD)
        return
    context.bot.edit_message_text(new_text, chat_id=user, message_id=msg_id, reply_markup=new_btns, parse_mode=MD)


def error(update, context):
    context.bot.send_message(chat_id=ADMIN_ID, text=f"Errore da: {context.bot.first_name}\n\nErrore: {context.error}")


def ping(update, context):
    user = update.message.from_user.id
    if user not in users or user != ADMIN_ID:
        return
    update.message.reply_text("pong")


def main():
    print("BOT STARTED")
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    # Dispatcher gestore degli eventi
    dp = updater.dispatcher

    # Comandi e Callback
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("timeout", timeout))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("add", add))
    dp.add_handler(CommandHandler("remove", remove))
    dp.add_handler(CommandHandler("changelog", changelog))
    dp.add_handler(CommandHandler("ping", ping))

    # Bottone premuto
    dp.add_handler(CallbackQueryHandler(button))

    # Errori
    dp.add_error_handler(error)

    updater.start_polling()
    return updater
    # updater.idle()


if __name__ == "__main__":
    if "Tantum.py" in os.listdir(This_Folder):
        os.system(f"{This_Folder}/venv/bin/python {This_Folder}/Tantum.py")
        os.system(f"rm {This_Folder}/Tantum.py")
        time.sleep(1)
        os.system("systemctl restart bot")

    updater = main()
    bot = updater.bot
    cron = CronTab(user="root")

    result, data = Model.get_settings()
    if result == -1:
        bot.send_message(chat_id=ADMIN_ID, text=f"Errore da: {bot.first_name}\n\nErrore nell'acquisizione delle impostazioni", parse_mode=MD)
        updater.stop()
        exit()

    for user in data:
        ID, minutes = user
        iter = cron.find_command(str(ID))
        for job in iter:
            if str(ID) in str(job):
                break
        else:
            new = cron.new(command=f"{This_Folder}/venv/bin/python {This_Folder}/Update.py {ID} &> /dev/null", comment=f"User: {users[ID]['name']}")
            new.minute.every(minutes)
            cron.write()


    try:
        while "RUNNING":
            try:
                time.sleep(60)
                if "socket" in os.listdir(This_Folder):
                    socket_size = os.stat("socket").st_size
                    if socket_size == 0:
                        continue
                    if "socket.lock" in os.listdir(This_Folder):
                        while "socket.lock" in os.listdir(This_Folder):
                            time.sleep(1)
                    os.system(f"touch {This_Folder}/socket.lock")
                    with open(f"{This_Folder}/socket", encoding="utf-8") as socket:
                        for line in socket:
                            if len(line.split("|")) != 3:
                                continue
                            result, user, data = line.strip().split("|")
                            result = bool(result)
                            if user.isdigit():
                                user = int(user)
                                if result is False:
                                    send_error_b(bot, user, data)
                                else:
                                    bot.send_message(chat_id=user, text=data, parse_mode=MD)
                            else:
                                for user in users:
                                    bot.send_message(chat_id=user, text=data.replace("§", "\n"), parse_mode=MD)
                    with open(f"{This_Folder}/socket", "w", encoding="utf-8") as flush:
                        pass
                    os.system(f"rm {This_Folder}/socket.lock")
            except Exception as e:
                bot.send_message(chat_id=ADMIN_ID, text=f"Errore da: {bot.first_name}\n\nErrore: {str(e)}", parse_mode=MD)
                os.system(f"rm {This_Folder}/socket.lock")
    except (KeyboardInterrupt, SystemExit) as e:
        print(f"INTERRUPT: {e}")
        updater.stop()
        exit()
    except Exception as e:
        bot.send_message(chat_id=ADMIN_ID, text=f"Errore da: {bot.first_name}\n\nErrore: {str(e)}", parse_mode=MD)
