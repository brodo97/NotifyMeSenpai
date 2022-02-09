#! /usr/bin/python3
import sqlite3

import json
import traceback

import requests
from bs4 import BeautifulSoup
import re
import os
import time
from datetime import datetime
from urllib.parse import urlparse
from Config import ALLOWED_CATEGORIES, DATABASE_PATH


class Database:
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

    # TODO: get_users_uploads
    def get_users_uploads(self, user_id):  # get_nhentai
        result, data = DATABASE.execute(f'SELECT * FROM Data WHERE ChatID == {user_id} ORDER BY ID ASC;')
        if result is False:
            return False, data
        sub_data = {}
        for nhentai_entry in data[0]:
            category = nhentai_entry[2].split('/')[3].title()
            entry_dict = {key: val for key, val in zip(data[1], nhentai_entry)}
            if category in sub_data:
                sub_data[category].append(entry_dict)
            else:
                sub_data[category] = [entry_dict]
        return True, sub_data

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

        link = link.lower()           # Convert lowercase
        parsed_link = urlparse(link)  # urlparse the link

        # If the site is not nhentai.net or the link doesn't contain any of the ALLOWED_CATEGORIES, return error
        if parsed_link.netloc != 'nhentai.net' or \
                not any([category in parsed_link.path for category in ALLOWED_CATEGORIES]):
            return 0, f'*{link}* is not a valid link!'

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

        :return: A Tuple containing status as Integer {-1:Unexpected Error, 0:Error, 1:OK} and some data as String
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
