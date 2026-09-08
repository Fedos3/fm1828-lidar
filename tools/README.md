# Разбор прошивки DEEBOT ради команд лидара FM1828

Скрипты — порт на Python нужных частей [denysvitali/ecovacs-firmware-tools](https://github.com/denysvitali/ecovacs-firmware-tools)
(Go на машине нет). Зависимости в venv: `pycryptodome`, `PySquashfsImage`, `zstandard`.

```sh
python ota_query.py 659yh8,snxbvc fw0        # опрос OTA-API Ecovacs, пишет found.json
curl -L -o t9aivi_fw-1.4.9.bin '<url из found.json>'
python decrypt.py t9aivi_fw-1.4.9.bin t9aivi  # AES-128-CBC по секциям, ключ из типа и размера секции
python grep_fs.py t9aivi/normal_fs.img        # поиск строк lds в squashfs
```

Коды моделей (из `mrbungle64/ecovacs-deebot.js`, `library/models.js`): `659yh8` T9 AIVI, `snxbvc`/`yu362x` N8 PRO,
`h18jkh`/`b742vd`/`wgxm70` T8, `x5d34r` T8 AIVI, `ucn2xe`/`ipohi5` T9. На 2026-09-08 OTA отдавал только T9 AIVI 1.4.9
(`OTA/T9AIVI/px30-zj2011_fw-1.4.9.bin`, 59.6 МБ, md5 `1de7de90…`); файл не хранится в репозитории.

## Что найдено (T9 AIVI 1.4.9, `/usr/lib/node/liberos_node_hardware_platform.so`)

Строки команд лидара в бинарнике: `startlds$`, `startldspl$startlds$`, `stoplds$`. Рядом логи
`plus startup` и `send start cmd`: робот сначала шлёт `startldspl$startlds$` («plus startup»), затем `startlds$`.
Других команд лидару (`$`-терминированных) в прошивке нет. В прошивке MCU (`mcu.img`) есть строка `lds_power: %d`:
питание лидара в роботе коммутирует MCU.

Поведение на живом FM1828: `startldspl$` запустил лидар из состояния, в котором тот молчал (не слал кадры простоя),
но сразу после `stoplds$`, когда лидар шлёт кадры простоя, ни `startldspl$`, ни `startlds$` не работают.
Подробности и текущий статус — `../docs/protocol.md`.

## Дизассемблирование `liberos_node_hardware_platform.so` (aarch64, `xcrun llvm-objdump -d`)

Класс `common::LdsNode::Impl` (исходник в роботе: `eros_node_hardware_platform/src/common/LdsNode.cpp`). Граф вызовов:

| Функция робота | Что делает |
| --- | --- |
| `startLds()` | запускает таймер-сторож, `resetLdsData()`, **`powerOnLds()`**, затем `sendStartCmd()` |
| `sendStartCmd()` | шлёт по UART либо `startlds$` («send start cmd»), либо `startldspl$startlds$` («plus startup»), выбор по внутреннему флагу |
| `stopLds()` | **`sendStopCmd()` (`stoplds$`) + `powerOffLds()`** + остановка таймера + `resetLdsData()` |
| `powerOnLds()` / `powerOffLds()` | `sendControlMsg()` → публикация в comm-топик к MCU; в прошивке MCU есть лог `lds_power: %d` |
| `detectLdsState()` (таймер) | при `no data coming` / `low speed` / `speed abnormal` → `reportLdsErrorData()`, `stopLds()` или `powerOffLds()`, затем снова `sendStartCmd()`; лог `restart lds` |

Вывод: команда остановки `stoplds$` правильная, других нет, но робот **всегда** сопровождает остановку снятием питания
через MCU и перед каждым стартом включает питание. Программного пути «стоп → старт» без снятия питания в прошивке робота нет.
Скорость UART подтверждена строкой `stty -F %s 460800`.
