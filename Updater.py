import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import time
import traceback
from Config import CHECK_TIME_SECONDS
from Classes import Database

DATABASE = Database()
DATABASE = DATABASE.conn


# Get users' filters
def get_ignored_languages(chat_id: int):
    # Get ignore_languages from Settings table (if exists)
    languages = DATABASE.execute(
        f'SELECT Value FROM UserSettings WHERE ChatID == {chat_id} AND Setting LIKE \'skip_languages\''
    ).fetchone()

    # And if not exists then []
    languages = [] if languages[0] is None else languages[0].split(',')

    return languages


# Creating requests' Session
with requests.Session() as SESSION:
    while 1:
        Settings = {}
        SleepTime = CHECK_TIME_SECONDS

        # Update Settings variable
        for row in DATABASE.execute('SELECT ID FROM Users'):
            chat_id = row[0]
            Settings.update({
                chat_id: get_ignored_languages(chat_id)
            })

        for row in DATABASE.execute('SELECT * FROM Links'):
            ID, Link, Category, Name, KnownUploads, LastCheck = row

            # Get every ChatID that is following the link
            ChatIDs = DATABASE.execute(
                f'SELECT ChatID FROM Follows WHERE LinkID == {ID};'
            ).fetchall()

            # If no one is following the link, delete it
            if len(ChatIDs) == 0:
                DATABASE.execute(
                    f'DELETE FROM Links WHERE ID == {ID};'
                ).fetchall()

                DATABASE.commit()  # Commit changes

                continue

            # Init to arbitrary datetime
            if LastCheck is None:
                LastCheck = datetime(2020, 1, 1)
            else:
                LastCheck = datetime.strptime(LastCheck, '%Y/%m/%d %H:%M:%S')

            # If it was checked less than an hour ago, skip
            LastCheckSeconds = (datetime.now() - LastCheck).total_seconds()
            if LastCheckSeconds < CHECK_TIME_SECONDS:
                # Calculate sleep till next check cycle
                if CHECK_TIME_SECONDS - LastCheckSeconds < SleepTime:
                    SleepTime = CHECK_TIME_SECONDS - LastCheckSeconds

                    # Check if SleepTime > 0. Don't want negative sleep
                    SleepTime = 0 if SleepTime < 0 else SleepTime
                continue

            time.sleep(2)  # Sleep 2 seconds for spam prevention

            RESPONSE = SESSION.get(Link)  # Do a request to the link using current session

            # If the response's status code differ from 200, continue
            if RESPONSE.status_code != 200:
                print(f'ERROR - check_nhentai(): {Link} returned status code = {RESPONSE.status_code}')
                continue

            SOUP = BeautifulSoup(RESPONSE.content, 'html.parser')  # Pass response's content to BeautifulSoup

            # If response's content is malformed, continue
            if SOUP is None:
                print(f'ERROR - check_nhentai(): BeautifulSoup error')
                continue

            PendingTransaction = False  # Using this for rollback in case of an exception
            try:
                # For every upload panel/div
                for gallery_div in SOUP.find_all('div', 'gallery'):
                    # If is known, continue
                    if gallery_div.find('a')['href'] in KnownUploads:
                        continue

                    # Current div link, es: /g/000000
                    UploadLink = gallery_div.find('a')['href']

                    # Upload's link insertion in the database for duplication avoidance
                    DATABASE.execute(f'UPDATE Links SET KnownUploads = KnownUploads || \',{UploadLink}\' WHERE ID == {ID};')
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
                        DATABASE.execute(
                            f'INSERT INTO MESSAGES (ChatID, Content) VALUES ({chat_id}, \'{text}\');'
                        )

                # Updating LastCheck to current datetime and update relative row
                LastCheck = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
                DATABASE.execute(f'UPDATE Links SET LastCheck = \'{LastCheck}\' WHERE ID == {ID};')

                DATABASE.commit()  # Commit changes
            except Exception:
                # If there were pending transaction, rollback. Maybe it will upload at next cycle
                if PendingTransaction is True:
                    DATABASE.execute('rollback')
                traceback.print_exc()

        time.sleep(SleepTime)
