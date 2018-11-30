#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import pickle 
import os
import sys
import time
sys.path.append("EduBot/EduBotLibrary")
import edubot


#IP = "127.0.0.1"
IP = str(os.popen("hostname -I | cut -d\" \" -f1").readline().replace("\n",""))
PORT = 8000
TIMEOUT = 120 #время ожидания приема сообщения

MAX_POWER = 255
KOOF = 0.75

def motorRun(leftSpeed, rightSpeed):
    robot.leftMotor.SetSpeed(leftSpeed)
    robot.rightMotor.SetSpeed(rightSpeed)

def beep():
    print("Beep!!!")
    robot.Beep()
    
def Exit():
    print("exit")
    running = False
    
def val_map(val, fromLow, fromHigh, toLow, toHigh):
    return int(toLow + (toHigh - toLow) * ((val - fromLow) / (fromHigh - fromLow)))

robot = edubot.EduBot(1)
assert robot.Check(), 'EduBot not found!!!'
robot.Start() #обязательная процедура, запуск потока отправляющего на контроллер EduBot онлайн сообщений
print ('EduBot started!!!')

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #создаем сервер
server.bind((IP, PORT)) #запускаем сервер
print("Listening %s on port %d..." % (IP, PORT)) #выводим сообщение о запуске сервера
server.settimeout(TIMEOUT) #указываем серверу время ожидания приема сообщения

running = True
direction = None
power = 0
leftSpeed = 0
rightSpeed = 0

while running:
    try:
        data = server.recvfrom(1024) #пытаемся получить данные
    except socket.timeout: #если вышло время, то выходим из цикла
        print("Time is out...")
        break

    direction, power = pickle.loads(data[0])
    adrs = data[1]
    power = val_map(power, 0, 100, 0, MAX_POWER)
    print(direction, power)
    
    """
    if data:
        msg = "message recieved"
        server.sendto(msg.encode("utf-8"), adrs) #отправляем ответ (msg)
    """
    if direction == None:
        leftSpeed = 0
        rightSpeed = 0
    elif direction == "forward":
        leftSpeed = power
        rightSpeed = power
    elif direction == "backward":
        leftSpeed = -power
        rightSpeed = -power
    elif direction == "right":
        leftSpeed = power
        rightSpeed = -power
    elif direction == "left":
        leftSpeed = -power
        rightSpeed = power
    elif direction == "forward and right":
        leftSpeed = power
        rightSpeed = int(power * KOOF)
    elif direction == "forward and left":
        leftSpeed = int(power * KOOF)
        rightSpeed = power
    elif direction == "backward and right":
        leftSpeed = -int(power * KOOF)
        rightSpeed = -power
    elif direction == "backward and left":
        leftSpeed = -power
        rightSpeed = -int(power * KOOF)
        
    motorRun(leftSpeed, rightSpeed)
    
    """
    if(cmd == "beep"):
        beep()
    if cmd == "exit":
        Exit()
    else:
        print("Unknown command: %s" % cmd)
    """
    time.sleep(0.05)
    
motorRun(0, 0)
robot.Release()
server.close()
print("End program")
