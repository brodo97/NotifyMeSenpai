import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import time
import traceback
from Config import CHECK_TIME_SECONDS
from Classes import Database

DATABASE = Database()
DB_CONN = DATABASE.conn
DB_CUR = DATABASE.cur


# Get users' filters
def get_ignored_languages(chat_id: int):
    # Get ignore_languages from Settings table (if exists)
    DB_CUR.execute(
        f'SELECT Value FROM UserSettings WHERE ChatID = {chat_id} AND Setting LIKE \'skip_languages\''
    )
    languages = DB_CUR.fetchone()

    # And if not exists then []
    languages = [] if languages is None or languages[0] is None else languages[0]

    return languages


# Creating requests' Session
with requests.Session() as SESSION:
    while 1:
        Settings = {}
        SleepTime = CHECK_TIME_SECONDS

        # Update Settings variable
        DB_CUR.execute('SELECT ID FROM Users')
        Users_IDs = DB_CUR.fetchall()
        for row in Users_IDs:
            chat_id = row[0]
            Settings.update({
                chat_id: get_ignored_languages(chat_id)
            })

        DB_CUR.execute('SELECT * FROM Links')
        Links_Data = DB_CUR.fetchall()
        for row in Links_Data:
            ID, Link, Category, Name, LastCheck = row

            # Get every ChatID that is following the link
            DB_CUR.execute(
                f'SELECT ChatID FROM Follows WHERE LinkID = %s;',
                (ID,)
            )
            ChatIDs = DB_CUR.fetchall()

            # If no one is following the link, delete it. And delete all known upload links
            if len(ChatIDs) == 0:
                DB_CUR.execute(
                    f'DELETE FROM Links WHERE ID = %s;',
                    (ID,)
                )
                DB_CUR.execute(
                    f'DELETE FROM KnownUploads WHERE LinkID = %s;',
                    (ID,)
                )

                DB_CONN.commit()  # Commit changes

                continue

            # Init to arbitrary datetime
            if LastCheck is None:
                LastCheck = datetime(2020, 1, 1)

            # If it was checked less than an hour ago, skip
            LastCheckSeconds = (datetime.now() - LastCheck).total_seconds()
            if LastCheckSeconds < CHECK_TIME_SECONDS:
                # Calculate sleep till next check cycle
                if CHECK_TIME_SECONDS - LastCheckSeconds < SleepTime:
                    SleepTime = CHECK_TIME_SECONDS - LastCheckSeconds

                    # Check if SleepTime > 0. Don't want negative sleep
                    SleepTime = 0 if SleepTime < 0 else SleepTime
                continue

            time.sleep(4)  # Sleep 2 seconds for spam prevention

            RESPONSE = SESSION.get(Link)  # Do a request to the link using current session

            # If the response's status code differ from 200, continue
            if RESPONSE.status_code != 200:
                print(f'ERROR: {Link} returned status code = {RESPONSE.status_code}')
                continue

            SOUP = BeautifulSoup(RESPONSE.content, 'html.parser')  # Pass response's content to BeautifulSoup

            # If response's content is malformed, continue
            if SOUP is None:
                print(f'ERROR: BeautifulSoup error')
                continue

            # Get the list of known uploads links
            KnownUploads = []
            # For every link in the database
            DB_CUR.execute(
                f'SELECT Upload FROM KnownUploads WHERE LinkID = %s;',
                (ID,)
            )
            KnownRows = DB_CUR.fetchall()
            for known_row in KnownRows:
                KnownUploads.append(known_row[0])  # Append it to the list

            PendingTransaction = False  # Using this for rollback in case of an exception
            try:
                # For every upload panel/div
                for gallery_div in SOUP.find_all('div', 'gallery'):
                    # Current div link, es: /g/000000
                    UploadLink = gallery_div.find('a')['href']

                    # If is known, continue
                    if UploadLink in KnownUploads:
                        continue

                    KnownUploads.append(UploadLink)

                    # Upload's link insertion in the database for duplication avoidance
                    DB_CUR.execute(
                        f'INSERT INTO KnownUploads (LinkID, Upload) VALUES (%s, %s);',
                        (ID, UploadLink)
                    )
                    PendingTransaction = True

                    # Constructing message's content. Will be sent from Telegram to the users
                    text = f'New {Category} upload: [{Name}](https://nhentai.net{UploadLink})'

                    # For every chat's ID following this Group/Artist/Category/Character
                    for result in ChatIDs:
                        chat_id = result[0]
                        # Check if the user is avoiding a specific languages
                        if any([language in gallery_div['data-tags'] for language in Settings[chat_id]]):
                            continue
                        # Else, insert in the database a new message to send
                        DB_CUR.execute(
                            f'INSERT INTO MESSAGES (ChatID, Content) VALUES (%s, %s);',
                            (chat_id, text)
                        )

                # Updating LastCheck to current datetime and update relative row
                DB_CUR.execute(
                    f'UPDATE Links SET LastCheck = %s WHERE ID = %s;',
                    (datetime.now(), ID)
                )

                DB_CONN.commit()  # Commit changes
            except Exception:
                # If there were pending transaction, rollback. Maybe it will upload at next cycle
                if PendingTransaction is True:
                    DB_CONN.rollback()
                traceback.print_exc()

        time.sleep(SleepTime)
