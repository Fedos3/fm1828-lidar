# Что делает с лидаром сам робот (по прошивке DEEBOT T9 AIVI 1.4.9)

Прошивка получена через OTA-API Ecovacs (`tools/ota_query.py`, модель `659yh8`), расшифрована (`tools/decrypt.py`,
порт алгоритма из [denysvitali/ecovacs-firmware-tools](https://github.com/denysvitali/ecovacs-firmware-tools)),
squashfs прочитан `PySquashfsImage`. Драйвер лидара: `/usr/lib/node/liberos_node_hardware_platform.so` (aarch64),
класс `common::LdsNode::Impl` из `eros_node_hardware_platform/src/common/LdsNode.cpp`. Дизассемблировано `llvm-objdump`.

| Функция | Действия |
| --- | --- |
| `startLds()` | таймер-сторож, `resetLdsData()`, **`powerOnLds()`**, `sendStartCmd()` |
| `sendStartCmd()` | UART: `startldspl$startlds$` («plus startup») либо `startlds$` («send start cmd») |
| `stopLds()` | `sendStopCmd()` = `stoplds$`, затем **`powerOffLds()`**, стоп таймера, `resetLdsData()` |
| `powerOnLds()` / `powerOffLds()` | `sendControlMsg()` → сообщение MCU (в прошивке MCU строка `lds_power: %d`) |
| `detectLdsState()` | по таймеру: `no data coming`, `low speed`, `speed abnormal`, `lds stuck` → `stopLds()`/`powerOffLds()`, затем `sendStartCmd()` («restart lds») |

Вывод: робот включает питание лидара перед каждым стартом и снимает его при каждой остановке. Программного пути
«стоп → старт» без снятия питания нет, поэтому FM1828 в автономной сборке требует ключ 5 В (или не останавливать мотор).

Строк-команд в бинарнике ровно три: `startlds$`, `startldspl$startlds$`, `stoplds$`. Скорость: `stty -F %s 460800`.
Прошивка и её фрагменты в репозитории не хранятся; скрипты в `tools/` позволяют повторить анализ.
