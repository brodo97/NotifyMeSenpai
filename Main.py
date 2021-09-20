import app
from Config import Telegram_Token, DCID, This_Folder
import uuid
import time
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from crontab import CronTab
import os

# Telegram Init
MD = telegram.ParseMode.MARKDOWN

# Users Init
result, data = Model.get_users()
if result is False:
    print("Failed to obtain users")
    exit()
users = data


def gettime(sec):
    return time.strftime('%Hh:%Mm:%Ss', time.gmtime(sec))


def send_error_ucd(update, context, error, user):
    identificativo = uuid.uuid4()
    if user != DCID and "returned status code" not in error:
        update.message.reply_text(f"Errore! Contattare l'amministratore\nCodice errore `{identificativo}`", parse_mode=MD)
    context.bot.send_message(chat_id=DCID, text=f"Errore da: {context.bot.first_name}\n\nID: {identificativo}\nErrore: {error}")
    return


def send_error_b(sub_bot, user, error):
    identificativo = uuid.uuid4()
    if user != DCID:
        sub_bot.send_message(chat_id=user, text=f"Errore! Contattare l'amministratore\nCodice errore `{identificativo}`", parse_mode=MD)
    sub_bot.send_message(chat_id=DCID, text=f"Errore da: {bot.first_name}\n\nID: {identificativo}\nErrore: {error}", parse_mode=MD)
    return


def start(update, context):
    user = update.message.from_user.id
    if user not in users:
        return
    update.message.reply_text(f"Ciao *{users[user]['name']}*\nUsa i comandi:\n/timeout per impostare il tempo di controllo\n/status per avere alcuni dati\n/add per aggiungere un artista da seguire\n/remove per rimuovere un artista che segui", parse_mode=MD)


def timeout(update, context):
    user = update.message.from_user.id
    if user not in users:
        return

    result, data = Model.get_upd_time(user)
    if result is False:
        send_error_ucd(update, context, data, user)
        return

    CheckTime = data
    text = update.message.text

    if len(text.split(" ")) > 1:
        minuti = text.split(" ")[1]
        if minuti.isdigit():
            minuti = int(minuti)
            if 10 <= minuti <= 59 or user == DCID:
                result, data = Model.update_upd_time(user, minuti)
                if result is False:
                    send_error_ucd(update, context, data, user)
                    return
                CheckTime = data
                cron = CronTab(user="root")
                for job in cron:
                    if str(user) in str(job):
                        cron.remove(job)
                        break
                new = cron.new(command=f"{This_Folder}/venv/bin/python {This_Folder}/Update.py {user} &> /dev/null", comment=f"User: {users[user]['name']}")
                new.minute.every(minuti)
                cron.write()
            else:
                update.message.reply_text(f"*{minuti}m* non è un valore valido! Minimo *10* minuti - Massimo *59* minuti", parse_mode=MD)
        else:
            update.message.reply_text(f"*{minuti}* non riconosciuto come valore numerico", parse_mode=MD)
    else:
        update.message.reply_text(f"Usa /timeout *TEMPO* per impostare ogni quanti minuti effettuare il controllo", parse_mode=MD)
    update.message.reply_text(f"Tempo impostato: *{gettime(CheckTime)}*", parse_mode=MD)


def status(update, context):
    user = update.message.from_user.id
    if user not in users:
        return

    result, data = Model.get_upd_time(user)
    if result is False:
        send_error_ucd(update, context, data, user)
        return
    CheckTime = data

    result, data = Model.get_nhentai(user)
    if result is False:
        send_error_ucd(update, context, data, user)
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

    # result, data = Model.get_hentainexus_artists(user)
    # if result is False:
    #     send_error_ucd(update, context, data, user)
    #     return
    # hentainexus = ""
    # if data:
    #     for x, artist in enumerate(data):
    #         hentainexus += f"*{x + 1}*) [{artist['Name']}]({artist['Link']})\n"
    # else:
    #     hentainexus = "*NESSUNO*"

    result, data = Model.get_any_hentai_chapter(user)
    if result is False:
        send_error_ucd(update, context, data, user)
        return
    anyhentai = ""
    if data:
        for x, chapter in enumerate(data):
            anyhentai += f"*{x + 1}*) [{chapter['Name']}]({chapter['Link']}) (Cap. *{chapter['LastChapter'] + 1}*)\n"
    else:
        anyhentai = "*NESSUNO*"

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
            if user != DCID:
                send_error_ucd(update, context, data, user)
            else:
                context.bot.send_message(chat_id=DCID, text=f"Errore da: {context.bot.first_name}\n\nErrore: {error}")
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
        send_error_ucd(update, context, data, user)
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
            send_error_ucd(update, context, data, user)
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
            send_error_ucd(update, context, data, user)
            return
        new_text = data
    elif action == "remHentaiNexus":
        result, data = Model.remove_hentainexus_artist(id)
        if result == -1:
            send_error_ucd(update, context, data, user)
            return
        new_text = data

    if new_btns is None:
        context.bot.edit_message_text(new_text, chat_id=user, message_id=msg_id, parse_mode=MD)
        return
    context.bot.edit_message_text(new_text, chat_id=user, message_id=msg_id, reply_markup=new_btns, parse_mode=MD)


def error(update, context):
    context.bot.send_message(chat_id=DCID, text=f"Errore da: {context.bot.first_name}\n\nErrore: {context.error}")


def ping(update, context):
    user = update.message.from_user.id
    if user not in users or user != DCID:
        return
    update.message.reply_text("pong")


def main():
    print("BOT STARTED")
    updater = Updater(Telegram_Token, use_context=True)

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
        bot.send_message(chat_id=DCID, text=f"Errore da: {bot.first_name}\n\nErrore nell'acquisizione delle impostazioni", parse_mode=MD)
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
                bot.send_message(chat_id=DCID, text=f"Errore da: {bot.first_name}\n\nErrore: {str(e)}", parse_mode=MD)
                os.system(f"rm {This_Folder}/socket.lock")
    except (KeyboardInterrupt, SystemExit) as e:
        print(f"INTERRUPT: {e}")
        updater.stop()
        exit()
    except Exception as e:
        bot.send_message(chat_id=DCID, text=f"Errore da: {bot.first_name}\n\nErrore: {str(e)}", parse_mode=MD)
