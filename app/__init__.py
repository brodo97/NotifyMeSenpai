#! /usr/bin/python3

from Database import Database
import json
import requests
from bs4 import BeautifulSoup
import re
from Config import *
import os
import time

regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

DB = Database()


def check_link_validity(link):
    return re.match(regex, link) is not None


def get_nhentai(user_id):
    result, data = DB.select(f"SELECT * FROM nhentai WHERE ChatID == {user_id} ORDER BY ID ASC;")
    if result is False:
        return False, data
    sub_data = {}
    for nhentai_entry in data[0]:
        category = nhentai_entry[2].split("/")[3].title()
        entry_dict = {key: val for key, val in zip(data[1], nhentai_entry)}
        if category in sub_data:
            sub_data[category].append(entry_dict)
        else:
            sub_data[category] = [entry_dict]
    return True, sub_data


def get_upd_time(user_id):
    result, data = DB.select_one_row(f"SELECT CheckTime FROM Settings WHERE ChatID == {user_id};")
    if result:
        return True, data[0] * 60
    return False, data


def update_upd_time(user_id, upd_time):
    result, data = DB.update(f"UPDATE Settings SET CheckTime = {upd_time} WHERE ChatID == {user_id};")
    if result:
        return True, upd_time * 60
    return False, data


def add_nhentai(user_id, link):
    if "nhentai" in link and ("artist" in link or "group" in link or "parody" in link or "character" in link) and check_link_validity(link):
        result, data = DB.add(f"INSERT INTO nhentai (Link, ChatID) VALUES ('{link}', {user_id});", commit=False)
        if result is False:
            if "unique" in str(data).lower():
                return 0, "Segui già questo artista nhentai"
            DB.rb()
            return -1, data

        result, data = DB.select_one_row(f"SELECT ID FROM nhentai WHERE ChatID == {user_id} ORDER BY ID DESC;")
        if result is False:
            DB.rb()
            return -1, data
        ID = data[0]

        with requests.Session() as session:
            res = session.get(link)
            if res.status_code != 200:
                DB.rb()
                return 0, "Errore nell'acquisizione dei dati da nhentai"

            soup = BeautifulSoup(res.content, "html.parser")
            try:
                Name = soup.find("span", "name").text
                if Name is None:
                    DB.rb()
                    return 0, "Errore nell'acquisizione dei dati da nhentai"

                result, data = DB.update(f"UPDATE nhentai SET Name = '{Name}' WHERE ID == {ID};", commit=False)
                if result is False:
                    raise Exception(data)

                LastDiv = soup.find_all("div", "gallery")[0]
                if LastDiv is None:
                    DB.rb()
                    return 0, "Errore nell'acquisizione dei dati dell'artista nhentai"

                LastWork = LastDiv.find("a")["href"]
                if LastWork is None:
                    DB.rb()
                    return 0, "Errore nell'acquisizione dei dati dell'artista nhentai"

                result, data = DB.update(f"UPDATE nhentai SET LastWorks = '{LastWork}' WHERE ID == {ID};")
                if result is False:
                    raise Exception(data)
            except Exception as e:
                DB.rb()
                return -1, f"add_nhentai(): {e}"
            return 1, f"Ora segui *{Name}*"
    return 0, f"*{link}* non è un link nhentai valido!"


def remove_nhentai(id):
    result, data = DB.select_one_row(f"SELECT ID, Name FROM nhentai WHERE ID == {id};")

    if result is False:
        return -1, data
    if data is None:
        return 0, "Non trovato"

    ID, Name = data[0], data[1]
    result, data = DB.remove(f"DELETE FROM nhentai WHERE ID == {ID};")
    if result is False:
        return -1, data
    return 1, f"Non segui più *{Name}*"


def get_settings(user_id=None):
    if user_id:
        result, data = DB.select_one_row(f"SELECT * From Settings WHERE ChatID == {user_id};")
        if result is False:
            return -1, data
        return 1, data
    else:
        result, data = DB.select_rows(f"SELECT * From Settings;")
        if result is False:
            return -1, data
        return 1, data


# Bot Only
def get_users():
    result, data = DB.select_rows("SELECT ID, Name, Admin FROM Users;")
    if result:
        users = {}
        for row in data:
            users[row[0]] = {"name": row[1], "admin": bool(row[2])}
        return True, users
    return False, data


def check_nhentai(user_id):
    msg_list = []
    with requests.Session() as session:
        result, data = DB.select_rows(f"SELECT * FROM nhentai WHERE ChatID == {user_id};")
        if result is False:
            return False, data
        for row in data:
            ID, Name, Link, LastWorks, _ = row
            if ID != 95:
                continue
            time.sleep(2)
            res = session.get(Link)
            if res.status_code != 200:
                msg_list.append([0, f"check_nhentai(): {Link} returned status code = {res.status_code}"])
                continue
            soup = BeautifulSoup(res.content, "html.parser")
            if soup is None:
                msg_list.append([0, "Errore nell'acquisizione dei dati dell'artista nhentai"])
                continue
            try:
                for LastDiv in soup.find_all("div", "gallery"):
                    if LastDiv is None:
                        msg_list.append([0, "Errore nell'acquisizione dei dati dell'artista nhentai"])
                        continue

                    if any([lang in LastDiv["data-tags"] for lang in Skip_Language]):
                        continue

                    if LastDiv.find("a")["href"] not in LastWorks.split(","):
                        LastWork = LastDiv.find("a")["href"]
                        print("New", Name, LastWork)
                        DB.update(f"UPDATE nhentai SET LastWorks = LastWorks || ',{LastWork}' WHERE ID == {ID};")
                        category = Link.split("/")[3].title()
                        msg_list.append([1, f"Categoria: *{category}*. E' uscito un nuovo lavoro di [{Name}](https://nhentai.net{LastWork})"])
                    else:
                        print("Break", Name)
                        break
            except Exception as e:
                msg_list.append([0, f"check_nhentai(): {e}"])
    return True, msg_list