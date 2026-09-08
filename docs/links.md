# Полезные ссылки

## Лидар и робот
- Запчасть FM1828 на AliExpress: https://www.aliexpress.com/item/1005004340497539.html — «ToF Laser Sensor LDS Unit FM1828», DEEBOT N8 Pro / T9 / T8 Max / T9 Power / T9 AIVI
- iNeedParts, FM1828 для DEEBOT T10: https://ineedparts.eu/products/top-laser-module-model-fm1828-for-ecovacs-deebot-t10
- Reverse engineering and hacking Ecovacs robots (DEF CON 32, Dennis Giese, braelynn): https://dontvacuum.me/talks/DEFCON32/DEFCON32_reveng_hacking_ecovacs_robots.pdf
- Инструменты для прошивок Ecovacs (OTA-скачивание, расшифровка): https://github.com/denysvitali/ecovacs-firmware-tools
- Коды моделей Ecovacs (`library/models.js`): https://github.com/mrbungle64/ecovacs-deebot.js

## Родственный лидар LDS-006 (тот же набор команд, 115200, 4 точки в кадре)
- https://github.com/opravdin/lds-006-reverse-engineering — `startlds$`, `$`, ШИМ мотора
- https://github.com/Aluminum-z/Laser-Radar-LDS-006-Drive-Test — таблица команд и формат кадра (STM32)
- http://blog.underwd.net/lds-006/overview.html — распиновка, схема платы LDS-006, GD32F130
- https://github.com/0x416c6578/lds-006-firmware — альтернативная прошивка LDS-006
- https://github.com/msoftware/LDS-006-Lidar-Sensor-Reverse-Engineering и https://www.jentsch.io/lds-006-lidar-sensor-reverse-engineering/
- https://github.com/murray1978/BlenderLidar — LDS-006 в Blender (`startlds$` / `stoplds$`)
- LDS-007 (Neato-подобный формат, 22 байта): https://github.com/spad0604/datn (`lds007_uart_reader.py`)

## Библиотеки и каталоги 2D-лидаров
- https://github.com/kaiaai/LDS — Arduino-библиотека для 27 моделей лидаров пылесосов (FM1828 не поддерживает)
- https://github.com/kaiaai/awesome-2d-lidars — каталог протоколов, распиновок и цен
