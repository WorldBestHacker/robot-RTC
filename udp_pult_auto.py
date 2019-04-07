#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import pygame
import os
#библиотеки для работы с сервером
import socket
import pickle
sys.path.append('/home/alexey/robot-RTC/RPicam-Streamer')
import time
import receiver
import threading
import crc16
from sh import ping
import detectLine as dl
import numpy as np
import cv2


IP_ROBOT = '192.168.0.101'
IP = str(os.popen("hostname -I | cut -d\" \" -f1").readline().replace("\n",""))
PORT = 8000
PORT_REPLY = 9000
RTP_PORT = 5000
FPS = 24
TIMEOUT = 120
CAM_SIZE = [320, 240]
SCREEN_SIZE = [CAM_SIZE[0] + 100, CAM_SIZE[1]]
FONTSIZE = 20
FONTCOLOR = (255,255,255)

def onFrameCallback(data, width, height):
    frame = pygame.image.frombuffer(data, (width, height), 'RGB')
    if autoMode and detectLineThread.isready():      
        rgbFrame = np.ndarray((height, width, 3), buffer = data, dtype = np.uint8)
        detectLineThread.setframe(rgbFrame)
        time.sleep(0.01)
        if detectLineThread.debugFrame is not None:

            debugFrame = pygame.surfarray.make_surface(detectLineThread.debugFrame)
            #debugFrame = pygame.transform.scale(debugFrame, (100, 100))
            screen.blit(debugFrame, (0,0))
    elif not autoMode:
        screen.blit(frame, (0,0))

        
    
def sendCommand(data):
    """отправляем данные на сервер и высчитываем контрольную сумму для
    проверки целостности данных"""
    global old_crc
    
    if not running:#если программа пульта остановлена, то отправляем на робота соответствующую команду
        data[2].append("EXIT")
    data = pickle.dumps(data)#запаковываем данные
    crc = crc16.crc16xmodem(data)#вычисляем контрольную сумму пакета
    msg = pickle.dumps((data, crc))#прикрепляем вычисленную контрольную сумму к пакету данных
    if crc != old_crc:#если есть изменения параметров, то отправляем на робота
        client.sendto(msg, (IP_ROBOT, PORT))
        old_crc = crc
        #print(keys, direction, power, cmd, autoMode)
    
def recv_reply():
    """обратная связь с роботом"""
    global running
    global reply
    print("start recieving")
    while running:
        try:
            reply = server.recvfrom(1024)
            reply  = pickle.loads(reply[0])
            print(reply) #выводим сообщение
            time.sleep(0.1)
        except socket.timeout:
            running = False
            print("Time is out...")
        
def Exit():
    """завершение проограммы, остановка всех потоков"""
    detectLineThread.stop()
    pygame.quit() #завершаем Pygame
    client.close() #закрываем udp клиент
    print("End program")
    recv.stop_pipeline()
    recv.null_pipeline()
    
    
def ping_robot():
    NUM = 10 #количество попыток
    ping_res = 0 
    try:
        for i in range(NUM):
            """запрашиваем пинг и находим в пришедшей строчке время ответа"""
            res = str(ping("-c", 1, IP_ROBOT))
            word = ""
            words = []
            for i in range(len(res)):
                if res[i] != " ":
                    word += res[i]
                elif res[i] == " ":
                    words.append(word)
                    word = ""
            for i in range(len(words)):
                if "time" in words[i]:
                    break
            ping_res += float(words[i][5:])
        ping_res /= NUM
    except:
        print("\npinging error, 100% lost\n")
    return str(round(ping_res, 2))

def ping_update():
    global ping_res
    while running:
        ping_res = ping_robot()
        time.sleep(0.5)

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #создаем сервер
server.bind((IP, PORT_REPLY)) #запускаем сервер
server.settimeout(TIMEOUT) #указываем серверу время ожидания приема сообщения

pygame.init() #инициализация Pygame
pygame.mixer.quit()

screen = pygame.display.set_mode(SCREEN_SIZE) #создаем окно программы
pygame.display.set_caption("robot-RTC") #устанавливаем заголовок в pygame
clock = pygame.time.Clock() #для осуществления задержки
myFont = pygame.font.SysFont("None", FONTSIZE) 
pygame.joystick.init() #инициализация библиотеки джойстика

recv = receiver.StreamReceiver(receiver.VIDEO_MJPEG, onFrameCallback)
recv.setHost(IP_ROBOT)
recv.setPort(RTP_PORT)
recv.play_pipeline()

detectLineThread = dl.cv_thread()
detectLineThread.start()

keys = []
power = 100
servo = []
running = True
old_crc = None
command = []
direction = [0,0]
cmd = []
autoMode = None
reply = []
ping_res = ""
ping_update = threading.Thread(target = ping_update)
ping_update.start()
reply_thread = threading.Thread(target = recv_reply)
reply_thread.start()

"""
try:
    joy = pygame.joystick.Joystick(0) # создаем объект джойстик
    joy.init() # инициализируем джойстик
    print('Enabled joystick: ' + joy.get_name())
except pygame.error:
    print('no joystick found.')"""

while running:
    for event in pygame.event.get():#пробегаемся по всем событиям pygame
        if event.type == pygame.QUIT:#если пользователь завкрывает окно pygame останавливаем программу 
            running = False
        if event.type == pygame.KEYDOWN:#нажатие на клавиши
            if event.key == pygame.K_w and "w" not in keys:
                keys.append("w")
            if event.key == pygame.K_s and "s" not in keys:
                keys.append("s")
            if event.key == pygame.K_a and "a" not in keys:
                keys.append("a")
            if event.key == pygame.K_d and "d" not in keys:
                keys.append("d")
            if (event.key == pygame.K_EQUALS or event.key == pygame.K_KP_PLUS) and power < 100:
                power += 10
            if (event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS) and power > 0:
                power -= 10
            if event.key == pygame.K_SPACE and "BOOST" not in cmd:
                cmd.append("BOOST")
            if event.key == pygame.K_x and "BEEP" not in cmd:
                cmd.append("BEEP")
            """включение и отключение различных редимов автономной езды
                при нажатии на кнопки 1-3 включается один из режимов,
                при повторном нажатии - выключается"""
            if event.key == pygame.K_1:
                if autoMode == 1:
                    autoMode = None
                else:
                    autoMode = 1
            if event.key == pygame.K_2:
                if autoMode == 2:
                    autoMode = None
                else:
                    autoMode = 2 
            if event.key == pygame.K_3:
                if autoMode == 3:
                    autoMode = None
                else:
                    autoMode = 3 
           
        if event.type == pygame.KEYUP:#отпускание клавиш
            if event.key == pygame.K_w:
                keys.remove("w")
            if event.key == pygame.K_s:
                keys.remove("s")
            if event.key == pygame.K_a:
                keys.remove("a")
            if event.key == pygame.K_d:
                keys.remove("d")
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_SPACE:
                cmd.remove("BOOST")
            if event.key == pygame.K_x:
                cmd.remove("BEEP")
    if keys: #если список нажатых кнопок не пуст, то проверяем его на наличие знакомых комбинаций
        if "w" in keys and "d" in keys:
            direction = "forward and right"
        elif "w" in keys and "a" in keys:
            direction = "forward and left"
        elif "s" in keys and "a" in keys:
            direction = "backward and right"
        elif "s" in keys and "d" in keys:
            direction = "backward and left"
        elif "w" in keys:
            direction = "forward"
        elif "s" in keys:
            direction = "backward"
        elif "d" in keys:
            direction = "right"
        elif "a" in keys:
            direction = "left"
        else:
            direction = None
    else:
        direction = None
        
    sendCommand((direction, power, cmd, autoMode))
    pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(CAM_SIZE[0], 0, SCREEN_SIZE[0], SCREEN_SIZE[1]))
        
    try:
        ping_img = myFont.render(ping_res, 0, (FONTCOLOR))
        #print(reply[2][0])
        voltage_img = myFont.render(str(reply[2][0]), 0, (FONTCOLOR))
        screen.blit(ping_img,(CAM_SIZE[0] + 10, 10))
        screen.blit(volage_img,(CAM_SIZE[0] + 10, 30))
    except:
        pass
    
    pygame.display.update()
    clock.tick(FPS) #задержка обеспечивающая 30 кадров в секунду
    
Exit()
