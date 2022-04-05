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
        self.available_settings_dictionary = {}
        self.update_settings()

    def check_link_validity(self, link: str):
        return re.match(self.regex, link) is not None

    def update_settings(self):
        """
        Initialize/update settings dictionary
        :return: Nothing
        """

        # Get settings list and other informations
        results = self.conn.execute(
            f'SELECT Setting, SettingName, SetValues, ValuesNames '
            f'FROM Settings'
        )

        # For every setting (row) in results (list of rows)
        for result in results:
            setting, name, values, values_names = result  # Unpack query result into separate variables
            values = values.split(',')                    # Split into separate values on ,
            values_names = values_names.split(',')        # Split into separate names on ,

            # Create a dict with the association Setting's parameter name: Setting's parameter value
            setting_options_nv = {
                name: value
                for name, value in zip(values_names, values)
            }
            # Create a dict with the association Setting's parameter value: Setting's parameter name
            setting_options_vn = {
                value: name
                for name, value in zip(values_names, values)
            }

            # Update dict with association Setting's name: Setting's options
            self.available_settings_dictionary.update({
                setting: {
                    'Name': name,
                    'NameValue': setting_options_nv,
                    'ValueName': setting_options_vn
                }
            })

    def insert_user(self, user_id: int):
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

        # Get settings list and other informations
        results = self.conn.execute(
            f'SELECT Setting '
            f'FROM Settings'
        )

        settings_to_insert = []

        # For every setting (row) in results (list of rows)
        for result in results:
            setting = result[0]
            # Init every setting for the user
            settings_to_insert.append(
                f'({user_id}, \'{setting}\')'
            )

        settings_to_insert = ', '.join(settings_to_insert)  # Join values on ', '

        # Insert settings
        self.conn.execute(f'INSERT INTO UserSettings (ChatID, Setting) VALUES {settings_to_insert};')

        self.conn.commit()  # Commit changes

        # Get the amount of links the user can follow
        limit = self.conn.execute(
            f'SELECT LinksLimit FROM Users WHERE ID == {user_id};'
        ).fetchone()

        return int(limit[0])

    def get_users_uploads(self, user_id: int):
        """
        Function called to get the list of links that user_id follows

        :param user_id: Telegram User's ID

        :return: User's links data parsed as Dict
        """

        # Get every row containing user_id
        results = self.conn.execute(
            f'SELECT L.ID, L.Name, L.Category, L.Link '
            f'FROM Links as L INNER JOIN Follows as F on L.ID = F.LinkID '
            f'WHERE F.ChatID == {user_id} ORDER BY L.Category ASC;'
        )

        following_list = {}

        # For every result (row of the database) in results (list of rows)
        for result in results:
            link_id, name, category, link = result  # Unpack query result into separate variables

            parsed_link = urlparse(link)  # urlparse the link
            path_args = parsed_link.path.split('/')  # Split path into a list

            # If category is in list, update existing following_list[category] dict with a new entry
            if category in following_list:
                following_list[category].update({
                    link_id: {
                        'Name': name,
                        'Category': category,
                        'Link': link
                    }
                })
            else:  # Else, update following_list dict with a new category and entry
                following_list.update({
                    category: {
                        link_id: {
                            'Name': name,
                            'Category': category,
                            'Link': link
                        }
                    }
                })

        return following_list

    def add_users_upload(self, user_id: int, link: str):  # add_nhentai
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

        category = category.title()

        # Get the amount of links the user can follow
        limit = self.insert_user(user_id)

        # Get the amount of links the user is following
        amount = self.conn.execute(
            f'SELECT COUNT(*) FROM Follows WHERE ChatID == {user_id};'
        ).fetchone()[0]

        # If the user reached the max amount of followable links, return error
        if amount >= limit:
            return 0, f'You\'re following too much links'

        # Get existing row data, if link exists
        exists = self.conn.execute(
            f'SELECT ID, Name FROM Links WHERE Link LIKE \'%{link}%\' LIMIT 1;'
        ).fetchone()

        # If the link exists in the database, add it
        if exists is None:
            # Creating requests' Session
            with requests.Session() as SESSION:
                response = SESSION.get(link)  # Do a request to the link using current session

                # If the response's status code is 404, return an error
                if response.status_code == 404:
                    return 0, f'{link} not found'

                # If the response's status code differ from 200, return an error
                if response.status_code != 200:
                    return -1, f'Error while parsing {link}\'s data'

                soup = BeautifulSoup(response.content, 'html.parser')  # Pass response's content to BeautifulSoup

                try:
                    name = soup.find('span', 'name').text   # Artist/Group/Character/etc...'s name

                    last_divs = soup.find_all('div', 'gallery')                   # First page uploads
                    known_uploads = [div.find('a')['href'] for div in last_divs]  # First page uploads' links

                    # Updating LastCheck to current datetime and update relative row
                    last_check = datetime.now().strftime('%Y/%m/%d %H:%M:%S')

                    # New link database insertion
                    cursor = self.conn.cursor()  # Use cursor to later get INSERT's lastrowid
                    cursor.execute(
                        f'INSERT INTO Links (Link, Category, Name, LastCheck) '
                        f'VALUES (\'{link}\', \'{category}\', \'{name}\', \'{last_check}\');'
                    )

                    # Insert new follow rule: UserID <-> LinkID
                    cursor.execute(
                        f'INSERT INTO Follows (ChatID, LinkID) '
                        f'VALUES ({user_id}, {cursor.lastrowid});'
                    )

                    # Insert all known uploads for future duplication avoidance
                    known_uploads_query = 'INSERT INTO KnownUploads (LinkID, Upload) VALUES '  # Prepare query
                    # Prepare values
                    known_uploads = [
                        f'({cursor.lastrowid}, \'{upload}\')' for upload in known_uploads
                    ]
                    known_uploads_query += ', '.join(known_uploads)  # Join query + values

                    cursor.execute(known_uploads_query)  # Execute query

                    self.conn.commit()  # Commit changes and inform the user

                    return 1, f'You\'re now following [{name}]({link})'
                except:
                    traceback.print_exc()
                    return -1, f'Error while parsing {link}\'s data'

        # If the link exists in the database
        else:
            link_id = exists[0]                        # Link's unique ID in the table
            category = parsed_link.path.split('/')[1]  # Link category
            name = exists[1]                           # Artist/Group/Character/etc...'s name

            # Check if user_id is already following this link
            following = self.conn.execute(
                f'SELECT * FROM Follows WHERE ChatID == {user_id} AND LinkID == {link_id} LIMIT 1;'
            ).fetchone() is not None

            # If the user is following the link, return error. Else, insert it
            if following is True:
                return 0, f'You\'re already following {category}: *{name}*'
            else:
                # Update row cell
                self.conn.execute(
                    f'INSERT INTO Follows (ChatID, LinkID) VALUES ({user_id}, {link_id})'
                )

                self.conn.commit()  # Commit changes

                return 1, f'You\'re now following [{name}]({link})'

    def remove_users_upload(self, user_id: int, link_id: int):  # remove_nhentai
        """
        Function called when a user wants to unfollow a link.

        :param user_id: Telegram User's ID
        :param link_id: Link's Unique ID

        :return: A Tuple containing status as Integer {0:Error, 1:OK} and some data as String
        """

        # Get existing row data, if link_id exists and user_id is following it
        exists = self.conn.execute(
            f'SELECT L.Name '
            f'FROM Links as L INNER JOIN Follows as F on L.ID = F.LinkID '
            f'WHERE F.ChatID == {user_id} AND L.ID == {link_id};'
        ).fetchone()

        # If it doesn't exist or user is not following it, return error
        if exists is None:
            return 0, 'Not found'

        # Delete follow rule
        self.conn.execute(
            f'DELETE FROM Follows WHERE ChatID == {user_id} AND LinkID == {link_id};'
        )

        self.conn.commit()  # Commit changes

        # Unpack query result
        name = exists[0]

        return 1, f'You unfollowed *{name}*'

    def get_users_settings(self, user_id: int):
        """
        Function called to get the list of user's available settings

        :param user_id: Telegram User's ID

        :return: User's settings data parsed as Dict
        """

        # Get every setting's row containing user_id
        results = self.conn.execute(
            f'SELECT ID, Setting, Value '
            f'FROM UserSettings WHERE ChatID == {user_id};'
        )

        settings_list = {}

        # For every result (row of the database) in results (list of rows)
        for result in results:
            setting_id, setting, value = result
            settings_list.update({
                setting_id: {
                    'Setting': setting,
                    'Value': value,
                    'Options': self.available_settings_dictionary[setting]
                }
            })

        return settings_list

    def update_users_setting(self, user_id: int, setting_id: int, value: str):
        """
        Function called to update user's settings

        :param user_id: Not necessary since setting_id is unique and associated to a single user_id
        :param setting_id: User's Setting ID
        :param value: Setting's value

        :return: A Tuple containing status as Integer {0:Error, 1:OK} and some data as String
        """

        # Get existing row data, should exist
        result = self.conn.execute(
            f'SELECT Setting, Value FROM UserSettings WHERE ID == {setting_id} AND ChatID == {user_id} LIMIT 1;'
        ).fetchone()

        setting, values = result    # Unpack values

        # if values is empty, init values = [] to avoid [''] (Empty string in the list)
        if values == '' or values is None:
            values = []
        else:
            values = values.split(',')  # Split different values, if something is present, on ','

        # Get corresponding setting's option name
        setting_name = self.available_settings_dictionary[setting]['ValueName'][value]

        text = f'Setting *{setting_name}* '

        # If value is present, remove it
        if value in values:
            values.remove(value)
            text += 'disabled'
        # Otherwise, add it
        else:
            values.append(value)
            text += 'enabled'

        values = ','.join(values)  # Pack different values

        # Update row cell
        self.conn.execute(
            f'UPDATE UserSettings SET Value = \'{values}\' WHERE ID == {setting_id} AND ChatID == {user_id};'
        )

        self.conn.commit()

        return 1, text

    def get_not_sent_messages(self):
        """
        Function called to collect the list of users messages that has to be sent

        :return: All the messages that has to be sent, parsed as Dict {ID: [ChatID, Message]}
        """

        # Get every not sent message
        results = self.conn.execute(
            f'SELECT ID, ChatID, Content '
            f'FROM Messages WHERE Sent == 0;'
        )

        messages = {}

        # For every result (row of the database) in results (list of rows)
        for result in results:
            message_id, user_id, message = result
            messages.update({
                message_id: [
                    user_id,
                    message
                ]
            })

        return messages

    def message_set_sent(self, message_id: int):
        """
        Set message as sent

        :param message_id: Message's id to be set as sent

        :return: Nothing
        """

        # Update row cell
        self.conn.execute(
            f'UPDATE Messages SET Sent = 1 WHERE ID == {message_id};'
        )

        self.conn.commit()

        return


class View:
    """
    Functions to build Telegram's messages
    """

    def __init__(self):
        self.database = Database()

    def start(self, user_id: int):
        """
        Build the body of the /start message
        It contains a starting "guide" for the user on how to use the bot

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
               f'\n\nUse /settings to change some notification\'s parameter' \
               f'\n\nYou can follow up to *{amount}* links' \
               f'\n\nIf you really like this bot, you can buy me a cup of coffee! https://www.paypal.me/notifymesenpai'

        return text

    def status(self, user_id: int):
        """
        Build the body of the /status message
        It contains the list of links the user is following

        :param user_id: Telegram User's ID

        :return: The message to be sent
        """

        # Get user's data
        data = self.database.get_users_uploads(user_id)

        text = ''

        # If the user is following some links, build the message
        if data:
            # For every category: Artist/Group/Character/etc...
            for category, category_list in data.items():
                # Init the list's header in the message
                text += f'Category: *{category.title()}*\n'

                # For every link in the category
                for x, link_id in enumerate(category_list.keys()):
                    # Get the corresponding link's data
                    link_data = category_list[link_id]
                    name = link_data['Name']
                    link = link_data['Link']

                    # Append data to the message. The x represent an incremental ID in the list. Not sure if the user
                    # really need that cause is not fixed. But can help to keep track on how much links the user is
                    # following
                    text += f'*{x + 1}*) [{name}]({link})\n'

                text += '\n'
        else:
            text = '*Nothing to show*\n\nUse /add *LINK* to follow something'

        return text.strip()

    def add(self, user_id: int, text: str):
        """
        Build the body of the "/add *link*" message
        It contains the list of links the user is following

        :param user_id: Telegram User's ID
        :param text: Telegram message's content

        :return: A Tuple containing status as Integer {-1:Unexpected Error, 0:Error, 1:OK} and the message as String
        """

        # Separate message arguments
        args = text.split(' ')

        # Clean erroneous multiple spaces
        while '' in args:
            args.remove('')

        # If args contain a number of parameter != 2, return error.
        # May consider a multiple link insertion
        if len(args) != 2:
            return 0, f'Use /add *LINK* to follow something'

        # args[0] = '/add'
        link = args[1]

        return self.database.add_users_upload(user_id, link)

    def remove(self, user_id: int, link_id: int = None):
        """
        Build the body of the /remove message
        It contains the list of links the user is following

        :param user_id: Telegram User's ID
        :param link_id: Link's ID to be removed, if None: return list of available links

        :return: A Tuple containing status as Integer {-1:Unexpected Error, 0:Error, 1:OK} and the messages as:
                 String if return status in [-1, 0] or link_id is not None
                 Dict if return status = 1 and link_id is None/not used
        """

        # If link_id is not None: try to remove the link from the user's following list
        if link_id is not None:
            return self.database.remove_users_upload(user_id, link_id)

        # If link_id is not present: get user's data
        data = self.database.get_users_uploads(user_id)

        # remove_data will contain buttons' data
        remove_data = {}

        # If the user is following some links, build the message
        if data:
            # For every category: Artist/Group/Character/etc...
            for category_list in data.values():
                # For every link in the category
                for link_id in category_list.keys():
                    # Get the corresponding link's data
                    link_data = category_list[link_id]
                    name = link_data['Name']
                    category = link_data['Category']
                    button_text = f'{category}: {name}'

                    remove_data[link_id] = button_text
        else:
            # Otherwise, return a message
            return 0, '*Nothing to show*\n\nUse /add *LINK* to follow something'

        return 1, remove_data

    def settings(self, user_id: int, setting: str = None, setting_id: int = None, value: str = None):
        """
        Build the body of the /remove message
        It contains the list of links the user is following

        :param user_id: Telegram User's ID
        :param setting: Setting's name to get corresponding options
        :param setting_id: Setting's ID to be changed
        :param value: Setting's value

        :return: A Tuple containing status as Integer {-1:Unexpected Error, 0:Error, 1:OK} and the messages as:
                 String
                 Dict
        """

        # If setting_id is not None: try to change the setting
        if value is not None:
            return self.database.update_users_setting(user_id, setting_id, value)

        # If setting_id is not present: get user's data
        data = self.database.get_users_settings(user_id)

        if setting is not None:
            options = {
                name: value
                for name, value in self.database.available_settings_dictionary[setting]['NameValue'].items()
            }
            return 1, options

        # settings_data will contain buttons' data
        settings_data = {}

        # If the user is following some links, build the message
        if data:
            # For every setting
            for setting_id, setting_data in data.items():
                # Get the corresponding setting's data, maybe this should/can be simplified
                setting = setting_data['Setting']
                setting_name = self.database.available_settings_dictionary[setting]['Name']

                current_setting = 'Nothing set'  # Current setting's value

                # If the setting has values, change the text of current_setting
                if setting_data['Value'] != '' and setting_data['Value'] is not None:
                    values = setting_data['Value'].split(',')

                    # Set values names list
                    value_names = [
                        self.database.available_settings_dictionary[setting]['ValueName'][value]
                        for value in values
                    ]
                    value_names = ', '.join(value_names)  # Join with ', '

                    current_setting = f'{value_names}'

                # Updating settings dict
                settings_data.update({
                    setting_id: {
                        'Setting': setting,
                        'SettingName': setting_name,
                        'CurrentSettings': current_setting
                    }
                })
        else:
            # Otherwise, return a message
            return 0, '*Nothing to show*'

        return 1, settings_data

    def get_messages(self):
        """
        Call to self.database.get_not_sent_messages()
        """
        return self.database.get_not_sent_messages()

    def message_set_sent(self, message_id: int):
        """
        Call to self.database.message_set_sent(message_id)
        """
        return self.database.message_set_sent(message_id)