#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ina219 import INA219
from ina219 import DeviceRangeError

import socket
import pickle 
import os
import sys
import time
import crc16
sys.path.append("EduBot/EduBotLibrary")
import edubot

#IP = "127.0.0.1"
IP = str(os.popen("hostname -I | cut -d\" \" -f1").readline().replace("\n",""))
PORT = 8000
TIMEOUT = 120 #время ожидания приема сообщения

MAX_POWER = 255
KOOF = 0 

DEF_DIR = None
DEF_POW = 0
DEF_CMD = None #параметры, которые будут выставлены при запуске программы

SHUNT_OHMS = 0.01 #значение сопротивления шунта на плате EduBot
MAX_EXPECTED_AMPS = 2.0
old_data = None

#все данные, которые должны быть выведены на экран (название и место для значения)
all_data = [["направление", "мощность", "команды"], [[], [], []]] 

    
def motorRun(leftSpeed, rightSpeed):
    """запускает моторы с заданной мощностью (от 255 до -255)"""
    robot.leftMotor.SetSpeed(leftSpeed)
    robot.rightMotor.SetSpeed(rightSpeed)
    
def recv_data():
    global running
    global old_data
    global adrs
    data = []
    try:
        data = server.recvfrom(1024) #пытаемся получить данные
        adrs = data[1]
        #print(adrs[0])
        if data != old_data:
            old_data = data
            return data
        else:
            return None
    except socket.timeout: #если вышло время, то выходим из цикла
        running = False
        print("Time is out...")

def val_map(val, fromLow, fromHigh, toLow, toHigh):
    return int(toLow + (toHigh - toLow) * ((val - fromLow) / (fromHigh - fromLow)))

def main():
    """основной цикл программы"""
    global direction
    global power
    global command
    global all_data 
    leftSpeed = 0 #скорость левого двигателя
    rightSpeed = 0 #скорость правого двигателя
    cmd = [] #список всех команд, отправляемых роботу
    data = []
    data = recv_data()

    if data:
        cmd, crc = pickle.loads(data[0]) #распаковываем команду и значение контрольной суммы
        crc_new = crc16.crc16xmodem(cmd) #расчитываем контрольную сумму полученных данных
        if crc == crc_new: #сравниваем контрольные суммы и проверяем целостность данных
            cmd = pickle.loads(cmd) #распаковываем список команд
            direction, power, command = cmd
            all_data[1][0] = direction
            all_data[1][1] = power
            all_data[1][2] = command
            power = val_map(power, 0, 100, 0, MAX_POWER) 
        
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
    
    if command == "beep":
        robot.Beep()
    if command == "EXIT":
        Exit()
        
    print_data()
    """
    msg = "data recieved"
    server.sendto(msg.encode("utf-8"), (adrs, PORT)) #отправляем ответ (msg)
    print("reply transmitted IP - ", (adrs, PORT))
    """
def Exit():
    """окончание работы"""
    global running
    print("exit")
    running = False
    motorRun(0, 0) #отсанавливаем двигатели
    robot.Beep() #сигнализируем о том, что программа завершена
    robot.Release() #прекращаем работу с роботом
    server.close() #закрываем udp сервер
    print("End program")
     
def print_data():
    """выводим на экран все важные данные
    (направление, мощность, команды, а также характеристики тока)"""
    os.system('clear')#очищаем терминал
    for i in range(len(all_data[0])):
        print(all_data[0][i], " : ", all_data[1][i]) #выводим все данные из all_data
        
    print("\nBus Voltage: %.3f V" % ina.voltage())
    print("Bus Current: %.3f mA" % ina.current())
    print("Power: %.3f mW" % ina.power())
    #выводим характеристики питания
    
#создаем обект для работы с INA219
ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS) 
ina.configure(ina.RANGE_16V)

robot = edubot.EduBot(1)#объявляем робота
assert robot.Check(), 'EduBot not found!!!' #проверяем, подключена ли плата EduBot
robot.Start() #обязательная процедура, запуск потока отправляющего на контроллер EduBot онлайн сообщений
print ('EduBot started!!!')

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #создаем сервер
server.bind((IP, PORT)) #запускаем сервер
print("Listening %s on port %d..." % (IP, PORT))
server.settimeout(TIMEOUT) #указываем серверу время ожидания приема сообщения
    
running = True
direction = DEF_DIR
power = DEF_POW
command = DEF_CMD

while running:
    main()
    time.sleep(0.1)
    