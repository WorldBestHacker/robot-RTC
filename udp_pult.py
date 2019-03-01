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

IP_ROBOT = '192.168.0.103'
IP = str(os.popen("hostname -I | cut -d\" \" -f1").readline().replace("\n",""))
PORT = 8000
PORT_REPLY = 9000
RTP_PORT = 5000
FPS = 24
TIMEOUT = 120
        
def onFrameCallback(data, width, height):
    frame = pygame.image.frombuffer(data, (width, height), 'RGB')
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
        #print(keys, direction, power, cmd, auto_mode)
    
def recv_reply():
    """обратная связь с роботом"""
    global running
    print("start recieving")
    while running:
        try:
            data = server.recvfrom(1024)
            reply, crc = pickle.loads(data[0])
            reply = pickle.loads(reply)
            print(reply) #выводим сообщение
            time.sleep(0.1)
        except socket.timeout:
            running = False
            print("Time is out...")
        
def Exit():
    """завершение проограммы, остановка всех потоков"""
    client.close() #закрываем udp клиент
    print("End program")
    recv.stop_pipeline()
    recv.null_pipeline()
    pygame.quit() #завершаем Pygame

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #создаем сервер
server.bind((IP, PORT_REPLY)) #запускаем сервер
server.settimeout(TIMEOUT) #указываем серверу время ожидания приема сообщения

pygame.init() #инициализация Pygame
pygame.mixer.quit()

screen = pygame.display.set_mode([640, 480]) #создаем окно программы
clock = pygame.time.Clock() #для осуществления задержки
pygame.joystick.init() #инициализация библиотеки джойстика

recv = receiver.StreamReceiver(receiver.VIDEO_MJPEG, onFrameCallback)
recv.setHost(IP_ROBOT)
recv.setPort(RTP_PORT)
recv.play_pipeline()


keys = []
power = 100
servo = []
running = True
old_crc = None
command = []
direction = [0,0]
cmd = []
auto_mode = None
reply = ""

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
                if auto_mode == 1:
                    auto_mode = None
                else:
                    auto_mode = 1
            if event.key == pygame.K_2:
                if auto_mode == 2:
                    auto_mode = None
                else:
                    auto_mode = 2 
            if event.key == pygame.K_3:
                if auto_mode == 3:
                    auto_mode = None
                else:
                    auto_mode = 3 
           
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
    sendCommand((direction, power, cmd, auto_mode))
    pygame.display.update()         
    clock.tick(FPS) #задержка обеспечивающая 30 кадров в секунду
    
Exit()
