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
import threading

#IP = "127.0.0.1"
IP = str(os.popen("hostname -I | cut -d\" \" -f1").readline().replace("\n",""))
USER_IP = ""
PORT = 8000
TIMEOUT = 120 #время ожидания приема сообщения

servo_limit = [[], [], [], []]
MAX_POWER = 210
KOOF = 0 

DEF_DIR = None
DEF_POW = 0
DEF_CMD = None #параметры, которые будут выставлены при запуске программы

SHUNT_OHMS = 0.01 #значение сопротивления шунта на плате EduBot
MAX_EXPECTED_AMPS = 2.0
old_data = None

first_cicle = True 

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

#все данные, которые должны быть выведены на экран (название и место для значения)
all_data = [["направление", "мощность", "команды", "напряжение", "ток"], [[], [], [], [], []]] 

def motorRun(leftSpeed, rightSpeed):
    """запускает моторы с заданной мощностью (от 255 до -255)"""
    robot.leftMotor.SetSpeed(leftSpeed)
    robot.rightMotor.SetSpeed(rightSpeed)
    
def recv_data():
    global running
    global old_data
    global USER_IP
    global first_cicle
    
    data = []
    try:
        data = server.recvfrom(1024) #пытаемся получить данные
        if first_cicle: #если первая иттерация, то записываем IP первого устройства, приславшего пакет с данными
            USER_IP = data[1][0]
            first_cicle = False
        if data != old_data and data[1][0] == USER_IP: #если пакет данных "устарел", то игнорируем
            old_data = data
            return data
        else:
            return None
    except socket.timeout: #если вышло время, то выходим из цикла
        running = False
        print("Time is out...")

def val_map(val, fromLow, fromHigh, toLow, toHigh):
    return int(toLow + (toHigh - toLow) * ((val - fromLow) / (fromHigh - fromLow)))

def Exit():
    """окончание работы"""
    global running
    print("exit")
    running = False
    motorRun(0, 0) #отсанавливаем двигатели
    #robot.Beep() #сигнализируем о том, что программа завершена
    robot.Release() #прекращаем работу с роботом
    server.close() #закрываем udp сервер
    
def update_current():
    """обновляем характеристики питании и записываем в список параметров"""
    global all_data
    all_data[1][3] = round(ina.voltage(), 2)
    all_data[1][4] = round(ina.current() / 1000, 3)
    
def print_data():
    """выводим на экран все важные данные из списка параметров"""
    global running
    global USER_IP
    while running:
        os.system('clear')#очищаем терминал
        if USER_IP:
            print("\nробот захвачен, IP - ", USER_IP)
        for i in range(len(all_data[0])):
            print(all_data[0][i], " : ", all_data[1][i]) #выводим все данные из all_data
        print("сервы - ", servo)
        time.sleep(0.1)
    #выводим характеристики питания
        
    send_reply(all_data)#отправляем параметры на пульт
    
def send_reply(data):
    """отправляем список параметров на пульт"""
    global USER_IP
    data = pickle.dumps(data)
    crc = crc16.crc16xmodem(data)
    msg = pickle.dumps((data, crc))
    server.sendto(msg, (USER_IP, PORT))
    
def servo_run(num, pos):
    robot.servo[num].SetPosition(pos)
    
def main():
    """основной цикл программы"""
    global direction
    global power
    global command
    global all_data
    global first_cicle
    global USER_IP
    global servo

    leftSpeed = 0 #скорость левого двигателя
    rightSpeed = 0 #скорость правого двигателя
    cmd = [] #список всех команд, отправляемых роботу
    data = recv_data()

    update_current()
    
    if data:
        cmd, crc = pickle.loads(data[0]) #распаковываем команду и значение контрольной суммы
        crc_new = crc16.crc16xmodem(cmd) #расчитываем контрольную сумму полученных данных
        if crc == crc_new: #сравниваем контрольные суммы и проверяем целостность данных
            cmd = pickle.loads(cmd) #распаковываем список команд
            direction, power, command, servo = cmd
            if servo[0]:
                servo_run(0, servo[0])
            if servo[1]:
                servo_run(1, servo[1])
            if servo[2]:
                servo_run(2, servo[2])
            if servo[3]:
                servo_run(3, servo[3])
            
            all_data[1][0] = direction
            all_data[1][1] = power
            all_data[1][2] = command
            #all_data[1][5] = servo
            if "BOOST" in command:
                power = 255
            else:
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
    
    if "BEEP" in command:
        robot.Beep()
    if "EXIT" in command:
        Exit()

data_monitor = threading.Thread(target = print_data)#создаем поток для данных отладки
#создаем обект для работы с INA219

running = True
direction = ""
power = 0
command = []
servo = []

data_monitor.start()#запускаем монитор для отладки
while running:
    try:
        main()
        time.sleep(0.1)
    except (KeyboardInterrupt, SystemExit):
        print("KeyboardInterrupt")
Exit()
print("End program")
