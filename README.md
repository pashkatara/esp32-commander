# ⚡ ESP32 Commander

<p align="center">
  <img src="esp32.ico" width="128" height="128" alt="ESP32 Commander Logo">
</p>

<p align="center">
  <b>Универсальная графическая утилита для полного управления flash-памятью и прошивкой устройств на базе ESP32 / ESP8266</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/esptool-v5.4%2B-orange" alt="esptool">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Release-v1.2.0-cyan" alt="Release">
</p>

---

## 🌟 Возможности

- 🗑 **Полная очистка (Erase Flash):** Стирание всей flash-памяти микроконтроллера в 1 клик с встроенным подтверждением операции.
- 📋 **Информация о плате:** Мгновенное определение модели процессора, MAC-адреса, размера flash, частоты кварца и производителя памяти (Winbond, GigaDevice, XMC и др.).
- 💾 **Резервное копирование (Dump Flash):** Считывание прошивки с платы и сохранение в `.bin` файл любого размера (1MB, 2MB, 4MB, 8MB, 16MB).
- ⚡ **Загрузка прошивки (Flash .bin):** Прошивка бинарных файлов по произвольным адресам памяти (`0x0000`, `0x1000`, `0x8000`, `0x10000` и др.) с выбором скорости до 921600 baud.
- 🖥 **Монитор порта (Serial Terminal):** Встроенный терминал в стиле High-Tech с поддержкой отправки команд на устройство в реальном времени.
- 🎨 **Современный интерфейс:** Дизайн в стиле Windows 11 с поддержкой переключения **Светлой ☀** и **Тёмной 🌙** темы.
- 🚀 **Постоянная строка состояния:** Никаких скачущих баннеров — статус операций плавно отображается в нижней строке программы.

---

## 🔌 Поддерживаемые контроллеры

| Семейство | Поддерживаемые модели |
| :--- | :--- |
| **ESP32** | ESP32-D0WD, ESP32-D0WDQ6, ESP32-WROOM, ESP32-WROVER, ESP32-PICO |
| **ESP32-S** | ESP32-S2, ESP32-S3 |
| **ESP32-C** | ESP32-C2, ESP32-C3, ESP32-C6 |
| **ESP8266** | ESP-01, ESP-07, ESP-12E, ESP-12F, NodeMCU, Wemos D1 Mini |

---

## 📥 Скачать готовую версию (.exe)

Готовый исполняемый файл доступен во вкладке [**Releases**](../../releases):
- Скачайте `ESP32_Commander.exe`
- Установка не требуется — запускается сразу (Python на компьютере не нужен).

---

## 🛠 Запуск из исходного кода

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/onepashka/esp32-commander.git
   cd esp32-commander
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Запустите программу:
   ```bash
   python esp32_commander.py
   ```

---

## 📦 Сборка своего EXE файла

Для сборки в один файл `.exe` запустите скрипт `build.bat` или выполните команду:

```bash
pyinstaller --onefile --windowed --name "ESP32_Commander" --icon "esp32.ico" --hidden-import serial --hidden-import serial.tools --hidden-import serial.tools.list_ports --hidden-import esptool --collect-all esptool --collect-all customtkinter esp32_commander.py
```

Готовый файл появится в корневой папке.

---

## 👤 Автор и контакты

- **Автор:** `pashka_tara`
- **Email:** `onepashka25@gmail.com`
- **Год выпуска:** 2026

## 📄 Лицензия

Проект распространяется под свободной лицензией **MIT**. Подробнее см. в файле [LICENSE](LICENSE).
