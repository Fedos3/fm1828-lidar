# FM1828 — Arduino/PlatformIO driver for the Ecovacs DEEBOT T8/T9/N8 Pro dToF lidar

Wiring (3.3 V UART): lidar TX → ESP32 RX (GPIO16), lidar RX ← ESP32 TX (GPIO17), GND common, lidar VCC 5 V (0.35 A).

```cpp
#include <FM1828.h>
FM1828 lidar;
void setup() { lidar.begin(Serial2, 16, 17); lidar.setScanCallback(onScan); lidar.start(); }
void loop() { lidar.loop(); }
```

* `start()` sends `$`, then `startlds$` two seconds later (the lidar ignores `startlds$` as the very first byte sequence).
* `stop()` sends `stoplds$`. After a stop the lidar has needed a power cycle before it accepted a new start (observed twice) — plan a switched 5 V rail if you need restarts.
* Points arrive through `setPointCallback(angle_deg, distance_mm, valid)`; 1440 points per revolution (0.25°), about 5 rev/s.
* Zero-angle direction and rotation sense are not yet calibrated against the housing.

Protocol details: `../../docs/protocol.md`.

## Restart after stop

`stop()` (`stoplds$`) puts the lidar into a state where `startlds$` is ignored until VCC is cycled (verified across four
power cycles; 37 candidate unlock commands failed). Wire a 5 V high-side switch (relay module or P-MOSFET) on the lidar's
+5 V, control it from a GPIO and call:

```cpp
lidar.setPowerPin(4);   // HIGH = lidar powered; setPowerPin(4, false) for active-low modules
lidar.restart();        // power off 1.5 s, on, settle 2.5 s, then "$" + "startlds$"
```

Switch the +5 V line, not GND: with GND switched the lidar stays half-powered through its RX pin.
