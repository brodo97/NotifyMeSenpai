import sys
import Model
import os
from Config import This_Folder, DCID
import time

if len(sys.argv) != 2:
    exit()

waited = 0
bricked = False
chat_id = sys.argv[1]

if "socket.lock" in os.listdir(This_Folder):
    while "socket.lock" in os.listdir(This_Folder):
        time.sleep(1)
        waited += 1
        if waited > 120:
            bricked = True
            break

os.system(f"touch {This_Folder}/socket.lock")

with open(f"{This_Folder}/socket", "a+", encoding="utf-8") as socket:
    result, data = Model.check_nhentai(chat_id)
    if result is True:
        for msg in data:
            if msg[0] == 0:
                continue
            socket.write(f"{msg[0]}|{chat_id}|{msg[1]}\n")


os.system(f"rm {This_Folder}/socket.lock")
