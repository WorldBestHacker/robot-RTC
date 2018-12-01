#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pynput import keyboard #импорт бибиотеки для работы с клавиатурой
import socket #библиотека для связи через udp
import pickle #библиотека для "упаковывания данных"
import time 
import threading

IP = "192.168.0.102" # IP сервера, куда мы посылаем данные о нажатиях клавиатуры
PORT = 8000 # порт, по которому мы отсылаем данные
keys = [] # список нажатых кнопок на клавиатуре

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #создаем udp клиент

def OnPress(key):
    """обработка событитя нажатия кнопки"""
    global case
    key = str(key)
    if key not in keys:
        keys.append(key)
    #sendCommand(key)
    
def OnRelease(key):
    """обработка событитя отпускания кнопки"""
    global keys
    if str(key) in keys:
        keys.remove(str(key))
    if key == keyboard.Key.esc:
        sendCommand(key)
        return False
        
def sendCommand(cmd):
    msg = pickle.dumps(cmd)
    client.sendto(msg, (IP, PORT))
    print(cmd)

def Listener():
    global running
    listener = keyboard.Listener(on_press = OnPress, on_release = OnRelease)
    listener.start()
    listener.join()
    running = False
    
#"прослушиваем" кнопки в отдельном потоке
keyListenerThread = threading.Thread(target = Listener)
keyListenerThread.start()    

running = True
direction = None
power = 80

while running:
    if keys: #если список нажатых кнопок не пуст, то проверяем его на наличие знакомых комбинаций
        if "'w'" in keys and "'d'" in keys:
            direction = "forward and right"
        elif "'w'" in keys and "'a'" in keys:
            direction = "forward and left"
        elif "'s'" in keys and "'a'" in keys:
            direction = "backward and right"
        elif "'s'" in keys and "'d'" in keys:
            direction = "backward and left"
        elif "'w'" in keys:
            direction = "forward"
        elif "'s'" in keys:
            direction = "backward"
        elif "'d'" in keys:
            direction = "right"
        elif "'a'" in keys:
            direction = "left"
        else:
            direction = None
    
        if power > 0 and "'-'" in keys:
            power -= 10
        if power < 100 and"'+'" in keys:
            power += 10
    else:
        direction = None
    """data = []
    data.append(direction)
    data.append(power)"""
    sendCommand((direction, power))
    time.sleep(0.1)
client.close()
print("stop")

