#! /usr/bin/python3

from Config import DB_Filename
import sqlite3

class Database():
    def __init__(self, name=DB_Filename):
        self.name = name
        self.conn = sqlite3.connect(self.name, check_same_thread=False)

    #Basic DB Functions
    def change(self, query, commit):
        try:
            cursor = self.conn.execute(query)
            if commit is True:
                self.conn.commit()
            return True, cursor.rowcount
        except Exception as e:
            self.conn.rollback()
            return False, e

    def select(self, query):
        try:
            cursor = self.conn.execute(query)
            return True, [cursor.fetchall(), list(map(lambda x: x[0], cursor.description))]
        except Exception as e:
            return False, e

    def select_rows(self, query):
        try:
            cursor = self.conn.execute(query)
            return True, cursor.fetchall()
        except Exception as e:
            return False, e


    def select_one_row(self, query):
        try:
            cursor = self.conn.execute(query.replace(";", " LIMIT 1;"))
            return True, cursor.fetchone()
        except Exception as e:
            return False, e


    def add(self, query, commit=True):
        return self.change(query, commit)


    def remove(self, query, commit=True):
        return self.change(query, commit)


    def update(self, query, commit=True):
        return self.change(query, commit)


    def rb(self):
        self.conn.rollback()
        return

    def close(self):
        self.conn.close()

    #User Related
    def get_ids(self):
        result, data = self.select("SELECT ID FROM Users;")
        if result:
            return True, list(data[0])
        return False, None


    def get_user(self, ID):
        result, data = self.select(f"SELECT * FROM Users WHERE ID == {ID};")
        if result:
            if data[0]:
                parameters = {key:value for key, value in zip(data[1], data[0][0])}
                return True, User(**parameters)
            else:
                return True, None
        else:
            return False, data
