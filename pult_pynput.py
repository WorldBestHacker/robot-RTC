#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pynput import keyboard #импорт бибиотеки для работы с клавиатурой
import socket #библиотека для связи через udp
import pickle #библиотека для "упаковывания данных"
import time 
import threading
import crc16

#IP = "127.0.0.1"
IP = "192.168.8.154" # IP сервера, куда мы посылаем данные о нажатиях клавиатуры
PORT = 8000 # порт, по которому мы отсылаем данные
keys = [] # список нажатых кнопок на клавиатуре

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #создаем udp клиент

def OnPress(key):
    """обработка событитя нажатия кнопки"""
    global keys
    global cmd
    if str(key) not in keys:
        keys.append(str(key))
    if key == keyboard.Key.esc:
        cmd = "EXIT"
    
def OnRelease(key):
    """обработка событитя отпускания кнопки"""
    global keys
    if key == keyboard.Key.esc:
        return False
    if str(key) in keys:
        keys.remove(str(key))
       
def sendCommand(cmd):
    """отправляем данные на сервер и высчитываем контрольную сумму для
    проверки целостности данных"""
    cmd = pickle.dumps(cmd)
    crc = crc16.crc16xmodem(cmd)
    msg = pickle.dumps((cmd, crc))
    client.sendto(msg, (IP, PORT))
    
        
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
direction = None #направление движения робота
power = 80 # мощность (в процентах, не больше 100)
cmd = None #команда, которую мы отправляем роботу

while running:
    print(keys)
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

        if "Key.space" in keys:
            cmd = "beep" 
    else:
        direction = None
    print(direction, power, cmd)
    sendCommand((direction, power, cmd)) #отправляем на робота данные
    cmd = None
    time.sleep(0.05)
"""
    reply = client.recvfrom(1024) #принимаем ответ от сервера
    print(reply) #выводим сообщение
"""
    
client.close() #закрываем udp клиент
print("End program")

