#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#библиотеки для работы с i2c монитором питания INA219
from ina219 import INA219
from ina219 import DeviceRangeError

#библиетека для работы с OLED дисплеем
import Adafruit_SSD1306

#библиотеки для работы с изображениями Python Image Library
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

import socket
import os
import pickle
import sys
import subprocess as sp

import time
import threading
import crc16

sys.path.append('EduBot/EduBotLibrary')
import edubot

import cv2
import numpy as np
import psutil

sys.path.append('/home/pi/RPicam-Streamer/')

import rpicam

#IP = "127.0.0.1"
IP = str(os.popen("hostname -I | cut -d\" \" -f1").readline().replace("\n",""))
PORT = 8000 #порт для управления роботом
USER_IP = '' #IP пульта (IP приемника видео)
RTP_PORT = 5000 #порт отправки RTP видео
TIMEOUT = 120 #время ожидания приема сообщения

FORMAT = rpicam.VIDEO_MJPEG #поток MJPEG
WIDTH, HEIGHT = 320, 240
RESOLUTION = (WIDTH, HEIGHT)
FRAMERATE = 30

MAX_POWER = 210 #максимальная мощность для обычного режима езды
KOOF = 0 #коэффициент для плавного поворота

DEF_DIR = None 
DEF_POW = 0
DEF_CMD = None #параметры, которые будут выставлены при запуске программы

old_data = None 

first_cicle = True

SHUNT_OHMS = 0.01 #значение сопротивления шунта на плате EduBot
MAX_EXPECTED_AMPS = 2.0
ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS) 
ina.configure(ina.RANGE_16V)

disp = Adafruit_SSD1306.SSD1306_128_64(rst = None) #создаем обект для работы c OLED дисплеем 128х64
disp.begin() #инициализируем дисплей
disp.clear() #очищаем дисплей
disp.display() #обновляем дисплей

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

class StateThread(threading.Thread):
    def __init__(self, robot, ina219, disp):
        super(StateThread, self).__init__()
        self.daemon = True
        self._stopped = threading.Event() #событие для остановки потока
        self._robot = robot
        self._ina = ina219
        self._disp = disp
        
    def run(self):
        image = Image.new('1', (self._disp.width, self._disp.height)) #создаем ч/б картинку для отрисовки на дисплее
        draw = ImageDraw.Draw(image) #создаем объект для рисования на картинке
        font = ImageFont.load_default() #создаем шрифт для отрисовки на дисплее
        print('State thread started')
        while not self._stopped.is_set():
            # Отрисовываем на картинке черный прямоугольник, тем самым её очищая
            draw.rectangle((0, 0, self._disp.width, self._disp.height), outline=0, fill=0)
            #Отрисовываем строчки текста с текущими значениями напряжения, сылы тока и мощности
            draw.text((0, 0), "Edubot project", font=font, fill=255)
            draw.text((0, 10), "Voltage: %.2fV" % self._ina.voltage(), font=font, fill=255)
            draw.text((0, 20), "Current: %.2fmA" % self._ina.current(), font=font, fill=255)
            draw.text((0, 30), "Power: %.2f" % self._ina.power(), font=font, fill=255)
            # Копируем картинку на дисплей
            self._disp.image(image)
            #Обновляем дисплей
            self._disp.display()
            time.sleep(1)
        print('State thread stopped')
    def stop(self): #остановка потока
        self._stopped.set()
        self.join()

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
            self.rpiCamStream.frameRequest() #отправил запрос на новый кадр
            self._newFrameEvent.wait() #ждем появления нового кадра
            '''
            if not (self._frame is None): #если кадр есть
                
                #--------------------------------------
                # тут у нас обрабока кадра self._frame средствами OpenCV
                time.sleep(0.1) #имитируем обработку кадра
                imgFleName = 'frame%d.jpg' % self._frameCount
                #cv2.imwrite(imgFleName, self._frame) #сохраняем полученный кадр в файл
                #print('Write image file: %s' % imgFleName)
                self._frameCount += 1
                #--------------------------------------
                '''
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
        return self._newFrameEvent.is_set()

def onFrameCallback(frame): #обработчик события 'получен кадр'
    #print('New frame')
    frameHandlerThread.setFrame(frame) #задали новый кадр

def transmit():
    global frameHandlerThread
    global USER_IP
    global RTP_PORT
    print('Start transmit...')
    #проверка наличия камеры в системе  
    assert rpicam.checkCamera(), 'Raspberry Pi camera not found'
    print('Raspberry Pi camera found')
    print('OpenCV version: %s' % cv2.__version__)

    FORMAT = rpicam.VIDEO_MJPEG #поток MJPEG
    WIDTH, HEIGHT = 320, 240
    RESOLUTION = (WIDTH, HEIGHT)
    FRAMERATE = 30

    rpiCamStreamer = rpicam.RPiCamStreamer(FORMAT, RESOLUTION, FRAMERATE)
    rpiCamStreamer.setPort(RTP_PORT)
    rpiCamStreamer.setHost(USER_IP)
    rpiCamStreamer.setRotation(180)
    rpiCamStreamer.start() #запускаем трансляцию
    
    #поток обработки кадров    
    frameHandlerThread = FrameHandlerThread(rpiCamStreamer)
    frameHandlerThread.start() #запускаем обработку
    
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
            print("робот захвачен", USER_IP)
            transmit()
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
    global frameHandlerThread
    global running
    global transmit
    running = False
    SetSpeed(0,0)
    robot.Release()
    server.close()
    #останавливаем обработку кадров
    frameHandlerThread.stop()
    #останов трансляции c камеры
    rpiCamStreamer.stop()    
    rpiCamStreamer.close()
    print('End program')

"""    
def print_data():
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
"""   
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
    global servo

    leftSpeed = 0 #скорость левого двигателя
    rightSpeed = 0 #скорость правого двигателя
    cmd = [] #список всех команд, отправляемых роботу
    data = recv_data()
    
    if data:
        cmd, crc = pickle.loads(data[0]) #распаковываем команду и значение контрольной суммы
        crc_new = crc16.crc16xmodem(cmd) #расчитываем контрольную сумму полученных данных
        if crc == crc_new: #сравниваем контрольные суммы и проверяем целостность данных
            cmd = pickle.loads(cmd) #распаковываем список команд
            direction, power, command, servo = cmd
            """
            if servo[0]:
                servo_run(0, servo[0])
            if servo[1]:
                servo_run(1, servo[1])
            if servo[2]:
                servo_run(2, servo[2])
            if servo[3]:
                servo_run(3, servo[3])
            """
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
    time.sleep(0.1)
running = True
direction = ""
power = 0
command = []
servo = []

while running:
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        Exit()
        print("KeyboardInterrupt")
print("End program")
