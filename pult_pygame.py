#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket #библиотека для связи через udp
import pickle #библиотека для "упаковывания данных"
import pygame #работа с периферией, экран программы и визуализация
import threading #потоки
import crc16 #вычисление контрольных сумм для проверки целостности данных


keys = [] #список всех нажатых клавиш
#IP = "127.0.0.1"
IP = "192.168.8.167" # IP сервера, куда мы посылаем данные о нажатиях клавиатуры
PORT = 8000 # порт, по которому мы отсылаем данные

servo = [0, 0, 0, 0] #положения сервоприводов

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #создаем udp клиент

pygame.init() #инициализируем pygame
pygame.mixer.quit() #отключаем проблемную часть pygame, загружающую ЦП
screen = pygame.display.set_mode((640, 480)) #создаем экран для вывода информации
clock = pygame.time.Clock() #часы, ограничивающие количество иттераций (кадров) в секунду

FPS = 20 #количество иттераций главного цикла (кадров) в секунду

old_crc = None #контрольная сумма последнего отправленного пакета

def sendCommand(data):
    """отправляем данные на сервер и высчитываем контрольную сумму для
    проверки целостности данных"""
    global old_crc
    global running
    
    if not running:#если программа пульта остановлена, то отправляем на робота соответствующую команду
        data[3] = "EXIT"
    data = pickle.dumps(data)#запаковываем данные
    crc = get_crc(data)#вычисляем контрольную сумму пакета
    msg = pickle.dumps((data, crc))#прикрепляем вычисленную контрольную сумму к пакету данных
    if crc != old_crc:#если есть изменения параметров, то отправляем на робота
        client.sendto(msg, (IP, PORT))
        old_crc = crc
        print(keys, direction, power, cmd, servo)
    
def get_crc(data):
    """вычисляем контрольную сумму пакета данных"""
    return crc16.crc16xmodem(data)
    
def recv_reply():
    """в отдельном потоке принимаем ответы от робота"""
    global reply
    reply = client.recvfrom(1024) #принимаем ответ от сервера
    print("ответ робота - ", reply) #выводим сообщение
    
def close():
    """закрытие программы"""
    client.close() #закрываем udp клиент
    print("End program")
    pygame.quit()

recvReply = threading.Thread(target = recv_reply)
recvReply.start()

running = True#переменная, отвечающая за работу главного цикла
direction = None #направление движения робота
power = 80 # мощность (в процентах, не больше 100)
cmd = [] #команда, которую мы отправляем роботу

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
        """
        if "'q'" in keys and servo[0] < 125:
            servo[0] += 5
        if "'e'" in keys and servo[0] > 0:
            servo[0] -= 5
        if "'r'" in keys and servo[1] < 125:
            servo[1] += 5
        if "'f'" in keys and servo[1] > 0:
            servo[1] -= 5
        if "'1'" in keys and servo[2] < 125:
            servo[2] += 5
        if "'2'" in keys and servo[2] > 0:
            servo[2] -= 5 """
    else:
        direction = None
    sendCommand((direction, power, cmd, servo)) #отправляем на робота данные
    clock.tick(FPS)#таймер, ограничивающий количество иттераций (кадров) в секунду
close()

