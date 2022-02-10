#! /usr/bin/python3
import sqlite3
import traceback
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
from Config import ALLOWED_CATEGORIES, DATABASE_PATH


class Database:
    """
    Functions to access and manage the database
    """
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    def __init__(self, db_path=DATABASE_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)

    def check_link_validity(self, link):
        return re.match(self.regex, link) is not None

    def insert_user(self, user_id):
        """
        Function called to insert a new user into the database. Can also be used to get the amount of link the user can
        follow

        :param user_id: Telegram User's ID

        :return: The amount of link the user can follow
        """

        # Get the amount of links the user can follow, if it exists
        limit = self.conn.execute(
            f'SELECT LinksLimit FROM Users WHERE ID == {user_id};'
        ).fetchone()

        # If limit is None, user exists.
        if limit is not None:
            return int(limit[0])

        # Insert user into the database
        self.conn.execute(
            f'INSERT INTO Users (ID) VALUES ({user_id});'
        )

        self.conn.commit()  # Commit changes

        # Get the amount of links the user can follow
        limit = self.conn.execute(
            f'SELECT LinksLimit FROM Users WHERE ID == {user_id};'
        ).fetchone()

        return int(limit[0])

    def get_users_uploads(self, user_id):
        """
        Function called to get the list of links that user_id follows

        :param user_id: Telegram User's ID

        :return: User's links data parsed as Dict
        """

        # Get every ChatIDs' row containing user_id
        results = self.conn.execute(
            f'SELECT ID, Name, Link FROM Data WHERE ChatIDs LIKE \'%{user_id}%\' ORDER BY ID ASC;'
        )

        following_list = {}

        # For every result (row of the database) in results (list of rows)
        for result in results:
            link_id, name, link = result # Unpack query result into separate variables

            parsed_link = urlparse(link)  # urlparse the link
            path_args = parsed_link.path.split('/')  # Split path into a list

            # Since path should be (for example) /artist/name/ path_args should be ['', 'artist', 'name', '']
            category = path_args[1]  # path_args[1] should be (for example) 'artist'

            # If category is in list, update existing following_list[category] dict with a new entry
            if category in following_list:
                following_list[category].update({
                    link_id: {
                        'Name': name,
                        'Link': link
                    }
                })
            else:  # Else, update following_list dict with a new category and entry
                following_list.update({
                    category: {
                        link_id: {
                            'Name': name,
                            'Link': link
                        }
                    }
                })

        return following_list

    def add_users_upload(self, user_id, link):  # add_nhentai
        """
        Function called when a user wants to follow a new link.

        :param user_id: Telegram User's ID
        :param link: Link to follow

        :return: A Tuple containing status as Integer {-1:Unexpected Error, 0:Error, 1:OK} and some data as String
        """

        # If the link is not valid, return error
        if self.check_link_validity(link) is False:
            return 0, f'*{link}* is not a valid link!'

        link = link.lower()                      # Convert lowercase
        parsed_link = urlparse(link)             # urlparse the link
        path_args = parsed_link.path.split('/')  # Split path into a list

        if len(path_args) < 2:
            return 0, f'*{link}* is not a valid link!'

        # Since path should be (for example) /artist/name/ path_args should be ['', 'artist', 'name', '']
        category = path_args[1]  # path_args[1] should be (for example) 'artist'

        # If the site is not nhentai.net or the link doesn't contain any of the ALLOWED_CATEGORIES, return error
        if parsed_link.netloc != 'nhentai.net' or \
                not any([cat == category for cat in ALLOWED_CATEGORIES]):
            return 0, f'*{link}* is not a valid link!'

        # Get the amount of links the user can follow
        limit = self.insert_user(user_id)

        # Get the amount of links the user is following
        amount = self.conn.execute(
            f'SELECT COUNT(*) FROM Data WHERE ChatIDs LIKE \'%{user_id}%\';'
        ).fetchone()[0]

        # If the user reached the max amount of followable links, return error
        if limit <= amount:
            return 0, f'You\'re following too much links'

        # Get existing row data, if link exists
        exists = self.conn.execute(
            f'SELECT * FROM Data WHERE Link LIKE \'%{link}%\' LIMIT 1;'
        ).fetchone()

        # If the link exists in the database, add it
        if exists is None:
            # Creating requests' Session
            with requests.Session() as SESSION:
                response = SESSION.get(link)  # Do a request to the link using current session

                # If the response's status code differ from 200, return an error
                if response.status_code != 200:
                    return -1, f'Error while parsing *{link}*\'s data'

                soup = BeautifulSoup(response.content, 'html.parser')  # Pass response's content to BeautifulSoup

                try:
                    name = soup.find('span', 'name').text          # Artist/Group/Character/etc...'s name
                    last_div = soup.find_all('div', 'gallery')[0]  # Latest upload
                    last_upload_link = last_div.find('a')['href']  # Latest upload's link

                    # Updating LastCheck to current datetime and update relative row
                    last_check = datetime.now().strftime('%Y/%m/%d %H:%M:%S')

                    # New link database insertion
                    self.conn.execute(
                        f'INSERT INTO Data (ChatIDs, Link, Name, KnownUploads, LastCheck) '
                        f'VALUES ({user_id}, \'{link}\', \'{name}\', \'{last_upload_link}\', \'{last_check}\');'
                    )
                    self.conn.commit()  # Commit changes and inform the user

                    return 1, f'You\'re now following [{name}]({link})'
                except:
                    traceback.print_exc()
                    return -1, f'Error while parsing *{link}*\'s data'

        # If the link exists in the database
        else:
            link_id = exists[0]                        # Link's unique ID in the table
            category = parsed_link.path.split('/')[1]  # Link category
            name = exists[3]                           # Artist/Group/Character/etc...'s name

            # Check if user_id is already following this link
            following = self.conn.execute(
                f'SELECT * FROM Data WHERE ID == {link_id} AND ChatIDs LIKE \'%{user_id}%\' LIMIT 1;'
            ).fetchone() is not None

            # If the user is following the link, return error. Else, add user_id in link's ChatIDs list
            if following is True:
                return 0, f'You\'re already following {category}: *{name}*'
            else:
                # Update row cell
                self.conn.execute(
                    f'UPDATE Data SET ChatIDs = ChatIDs || \',\' || {user_id} '
                    f'WHERE ID == {link_id};'
                )

                self.conn.commit()  # Commit changes

                return 1, f'You\'re now following [{name}]({link})'

    def remove_users_upload(self, user_id, link_id):  # remove_nhentai
        """
        Function called when a user wants to unfollow a link.

        :param user_id: Telegram User's ID
        :param link_id: Link's Unique ID

        :return: A Tuple containing status as Integer {0:Error, 1:OK} and some data as String
        """

        # Get existing row data, if link_id exists and user_id is in ChatIDs
        exists = self.conn.execute(
            f'SELECT Name, ChatIDs FROM Data WHERE ID == {link_id} AND ChatIDs LIKE \'%{user_id}%\';'
        ).fetchone()

        # If it doesn't exist or user is not following it, return error
        if exists is None:
            return 0, 'Not found'

        # Unpack query result into separate variables
        name, chat_ids = exists

        chat_ids = chat_ids.split(',')  # Splitting string to list
        user_id = str(user_id)          # Converting user_id from any to string
        chat_ids.remove(user_id)        # Removing user_id from chat_ids
        chat_ids = ','.join(chat_ids)   # Joining new chat_ids string

        # Update row cell
        self.conn.execute(
            f'UPDATE Data SET ChatIDs = \'{chat_ids}\' WHERE ID == {link_id};'
        )
        self.conn.commit()  # Commit changes

        return 1, f'You unfollowed *{name}*'


class View:
    """
    Functions to build Telegram's messages
    """

    def __init__(self):
        self.database = Database()

    def start(self, user_id):
        """
        Build the body of the /start message

        :param user_id: Telegram User's ID

        :return: The message to be sent
        """

        # Run user insertion
        amount = self.database.insert_user(user_id)

        text = f'*Hi!*' \
               f'\nThis bot will help you staying up to date with your favourite nhentai artist, character, ' \
               f'parodies and more!' \
               f'\n\nUse the following commands:' \
               f'\n/add to follow a link' \
               f'\n/remove to remove it' \
               f'\n\nYou can follow up to *{amount}* links'

        return text

    def status(self, user_id):
        """
        Build the body of the /status message

        :param user_id: Telegram User's ID

        :return: The message to be sent
        """

        # Get user's data
        data = self.database.get_users_uploads(user_id)

        text = ''
        if data:
            for category, category_data in data.items():
                text += f"Category: *{category}*\n"
                for x, link_id in enumerate(category_data):
                    link_data = category_data[link_id]
                    text += f"*{x + 1}*) [{link_data['Name']}]({link_data['Link']})\n"
                text += "\n"
        else:
            text = '*None*\n\nUse /add to follow something'

        return text.strip()
