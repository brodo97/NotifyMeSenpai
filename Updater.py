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
def get_ignored_languages(chat_ids, previous_settings):
    # For every chat's ID following this Group/Artist/Category/Character
    for chat_id in chat_ids.split(','):
        # Check if it has been already checked/updated/inserted in the previous settings variable
        if chat_id in previous_settings:
            continue
        # Get ignore_languages from Settings table (if exists)
        languages = DATABASE.execute(
            f'SELECT SettingValue FROM UserSettings WHERE ChatID == {chat_id} AND Setting LIKE \'ignore_languages\''
        ).fetchone()

        # And if not exists then []
        languages = languages[0].split(',') if languages is not None else []

        # Update previous settings for later return
        previous_settings.update({chat_id: languages})
    return previous_settings


# Creating requests' Session
with requests.Session() as SESSION:
    while 1:
        Settings = {}
        SleepTime = CHECK_TIME_SECONDS
        for row in DATABASE.execute('SELECT * FROM Data'):
            ID, ChatIDs, Link, Name, KnownUploads, LastCheck = row
            LastCheck = datetime.strptime(LastCheck, '%Y/%m/%d %H:%M:%S')

            # Update Settings variable. (Every hour or so)
            NewSettings = get_ignored_languages(ChatIDs, Settings)
            Settings.update(NewSettings)

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
                    DATABASE.execute(f'UPDATE Data SET KnownUploads = KnownUploads || ",{UploadLink}" WHERE ID == {ID};')
                    PendingTransaction = True

                    # Current div category, es: Artist, Category, Group
                    category = Link.split('/')[3].title()

                    # Constructing message's content. Will be sent from Telegram to the users
                    text = f'New {category} upload: [{Name}](https://nhentai.net{UploadLink})'

                    # For every chat's ID following this Group/Artist/Category/Character
                    for ChatID in ChatIDs.split(','):
                        # Check if the user is avoiding a specific languages
                        if any([language in gallery_div['data-tags'] for language in Settings[ChatID]]):
                            continue
                        # Else, insert in the database a new message to send
                        DATABASE.execute(
                            f'INSERT INTO MESSAGES (ChatID, Content) VALUES ({ChatID}, \'{text}\');'
                        )
                    else:
                        break  # Breaking when finding a duplicate

                # Updating LastCheck to current datetime and update relative row
                LastCheck = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
                DATABASE.execute(f'UPDATE Data SET LastCheck = \'{LastCheck}\' WHERE ID == {ID};')

                DATABASE.commit()  # Commit changes
            except Exception:
                # If there were pending transaction, rollback. Maybe it will upload at next cycle
                if PendingTransaction is True:
                    DATABASE.execute('rollback')
                traceback.print_exc()

        time.sleep(SleepTime)
