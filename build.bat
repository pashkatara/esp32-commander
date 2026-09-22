@echo off
title Сборка ESP32 Commander
echo [1/3] Проверка зависимостей...
pip install -r requirements.txt pyinstaller

echo.
echo [2/3] Сборка исполняемого файла EXE...
pyinstaller --onefile --windowed --name "ESP32_Commander" --icon "esp32.ico" --hidden-import serial --hidden-import serial.tools --hidden-import serial.tools.list_ports --hidden-import esptool --collect-all esptool --collect-all customtkinter esp32_commander.py

echo.
echo [3/3] Копирование готового файла...
copy dist\ESP32_Commander.exe ESP32_Commander.exe /Y

echo.
echo ===================================================
echo Сборка успешно завершена! Файл: ESP32_Commander.exe
echo ===================================================
pause
