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
import cv2
import numpy as np
import psutil
import rpicam

#IP = "127.0.0.1"
IP = str(os.popen("hostname -I | cut -d\" \" -f1").readline().replace("\n",""))
USER_IP = ""
PORT = 8000
RTP_PORT = 5000 #порт отправки RTP видео
TIMEOUT = 120 #время ожидания приема сообщения

FORMAT = rpicam.VIDEO_MJPEG #поток MJPEG
WIDTH, HEIGHT = 640, 360
RESOLUTION = (WIDTH, HEIGHT)
FRAMERATE = 30

MAX_POWER = 255
KOOF = 0 

DEF_DIR = None
DEF_POW = 0
DEF_CMD = None #параметры, которые будут выставлены при запуске программы

SHUNT_OHMS = 0.01 #значение сопротивления шунта на плате EduBot
MAX_EXPECTED_AMPS = 2.0
old_data = None

first_cicle = True 

#все данные, которые должны быть выведены на экран (название и место для значения)
all_data = [["направление", "мощность", "команды", "напряжение", "ток", "серва  1"],[[], [], [], [], [], []]] 

#======================================================
#=================отправка видео=======================
#======================================================

class FrameHandlerThread(threading.Thread):
    def __init__(self, stream):
        super(FrameHandlerThread, self).__init__()
        self.daemon = True
        self.rpiCamStream = stream
        self._frame = None
        self._frameCount = 0
        self._stopped = threading.Event() #событие для остановки потока
        self._newFrameEvent = threading.Event() #событие для контроля поступления кадров
        
    def run(self):
        print('Frame handler started')
        while not self._stopped.is_set():
            if self.rpiCamStream.frameRequest(): #отправил запрос на новый кадр
                self._newFrameEvent.wait() #если запрос отправлен успешно, ждем появления нового кадра
                if not (self._frame is None): #если получен кадр
                
                    #--------------------------------------
                    time.sleep(2) #имитируем обработку кадра
                    imgFleName = 'frame%d.jpg' % self._frameCount
                    #cv2.imwrite(imgFleName, self._frame) #сохраняем полученный кадр в файл
                    print('Write image file: %s' % imgFleName)
                    self._frameCount += 1
                    #--------------------------------------
                    
                self._newFrameEvent.clear() #сбрасываем событие

        print('Frame handler stopped')

    def stop(self): #остановка потока
        self._stopped.set()
        if not self._newFrameEvent.is_set(): #если кадр не обрабатывается
            self._frame = None
            self._newFrameEvent.set() 
        self.join()

    def setFrame(self, frame): #задание нового кадра для обработки
        if not self._newFrameEvent.is_set(): #если обработчик готов принять новый кадр
            self._frame = frame
            self._newFrameEvent.set() #задали событие
            return True
        return False          
def onFrameCallback(frame): #обработчик события 'получен кадр'
    #print('New frame')
    frameHandlerThread.setFrame(frame) #задали новый кадр

#======================================================
#=================управление роботом===================
#======================================================

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
            print("робот захвачен ", USER_IP)
            first_cicle = False
        if data != old_data: #если пакет данных "устарел", то игнорируем
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
    
    #остановка трансляции c камеры
    frameHandlerThread.stop()
    rpiCamStreamer.stop()    
    rpiCamStreamer.close()
    #robot.Beep() #сигнализируем о том, что программа завершена
    robot.Release() #прекращаем работу с роботом
    server.close() #закрываем udp сервер
    
def update_current():
    """обновляем характеристики питания и записываем в список параметров"""
    global all_data
    all_data[1][3] = round(ina.voltage(), 2)
    all_data[1][4] = round(ina.current() / 1000, 3)
    
def print_data():
    """выводим на экран все важные данные из списка параметров"""
    global running
    update_current()
    while running:
        os.system('clear')#очищаем терминал
        for i in range(len(all_data[0])):
            print(all_data[0][i], " : ", all_data[1][i]) #выводим в терминал все данные из all_data
        time.sleep(0.1)
        
    #send_reply(all_data)#отправляем параметры на пульт
    
def send_reply(data):
    """отправляем список параметров на пульт"""
    global USER_IP
    data = pickle.dumps(data)
    crc = crc16.crc16xmodem(data)
    msg = pickle.dumps((data, crc))
    server.sendto(msg, (USER_IP, PORT))

def main():
    """основной цикл программы"""
    global direction
    global power
    global command
    global all_data
    global first_cicle
    global USER_IP
    global servo

    servo1 = 0
    leftSpeed = 0 #скорость левого двигателя
    rightSpeed = 0 #скорость правого двигателя
    cmd = [] #список всех команд, отправляемых роботу
    data = recv_data()

    if data:
        cmd, crc = pickle.loads(data[0]) #распаковываем команду и значение контрольной суммы
        crc_new = crc16.crc16xmodem(cmd) #расчитываем контрольную сумму полученных данных
        if crc == crc_new: #сравниваем контрольные суммы и проверяем целостность данных
            cmd = pickle.loads(cmd) #распаковываем список команд
            print(cmd, servo)
            direction, power, command, servo = cmd
            if servo:
                servo1 = servo[0]
            all_data[1][0] = direction
            all_data[1][1] = power
            all_data[1][2] = command
            all_data[1][5] = servo1
            
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
    
    #send_reply(all_data)

data_monitor = threading.Thread(target = print_data)#создаем поток для данных отладки
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


rpiCamStreamer = rpicam.RPiCamStreamer(FORMAT, RESOLUTION, FRAMERATE, (IP, RTP_PORT), onFrameCallback)
#robotCamStreamer.setFlip(False, True) #отражаем кадр (вертикальное отражение, горизонтальное отражение)
rpiCamStreamer.setRotation(180) #поворачиваем кадр на 180 град, доступные значения 90, 180, 270
rpiCamStreamer.start() #запускаем трансляцию
print("начало трансляции")
#поток обработки кадров    
#frameHandlerThread = FrameHandlerThread(rpiCamStreamer)
#frameHandlerThread.start() #запускаем обработку

running = True
direction = DEF_DIR
power = DEF_POW
command = DEF_CMD
servo = []

data_monitor.start()#запускаем монитор для отладки
while running:
    try:
        main()
        update_current()
        time.sleep(0.1)
    except (KeyboardInterrupt, SystemExit):
        Exit()
        print("KeyboardInterrupt")
print("End program")
