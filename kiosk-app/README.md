# Smart AIoT Access Control Kiosk

A multi-factor access control system combining **RFID card authentication** and **AI-based face recognition with liveness detection**, built on ESP32-S3 + Python AI Engine + Firebase Realtime Database.

> Final project — Computer Engineering, Ho Chi Minh City University of Technology and Education (HCMUTE)

---

## Author

- **Dinh Xuan Kinh** — HCMUTE, Computer Engineering  
  [GitHub](https://github.com/xuankinh)

---

## System Architecture

Three-tier architecture operating in parallel:

```
Web Admin (Browser)
      │  Firebase REST (lệnh quản trị)
      ▼
Firebase RTDB  ◄──────────────────────────────────┐
      │  Poll 0.5s                                 │ Log DailyLogs / AIEvents
      ▼                                            │
Python AI Engine (main.py)  ──── HTTP POST ──►  ESP32-S3 (Port 80)
   MediaPipe · ONNX · InsightFace                RFID · Servo · LCD · I2S
```

| Component | Role |
|-----------|------|
| **ESP32-S3** | RFID scanning, servo door control, LCD display, TTS audio, HTTP server |
| **Python AI** | Camera pipeline, anti-spoofing, face recognition, Firebase bridge |
| **Firebase RTDB** | Command relay (Web → Python/ESP32), attendance log, admin management |
| **Web Admin** | Register students, manage profiles, view attendance history |

---

## Features

- **5-step liveness challenge**: STABLE → PASSIVE (AntiSpoof ONNX) → BLINK (EAR-based, 2×) → POSE (head turn) → RECOGNIZE (InsightFace buffalo_s)
- **Dual authentication**: Face recognition OR RFID card, both log to Firebase
- **Anti-spoofing multi-layer**: ONNX binary classifier + blink detection + random pose challenge
- **Real-time telemetry dashboard**: FPS, LAN ping, inference latency, pipeline timing per step
- **Web Admin**: register card + face in one flow, attendance history, CSV export
- **Async architecture**: all network calls (HTTP + Firebase) run in background threads — main loop never blocked

---

## Hardware

| Component | Spec | GPIO |
|-----------|------|------|
| ESP32-S3 DevKitC-1 N16R8 | Xtensa LX7 240MHz, 16MB Flash, 8MB PSRAM | — |
| RFID RC522 | 13.56MHz, ISO 14443A | SCK=1 MISO=2 MOSI=3 CS=5 RST=4 |
| LCD ILI9341 | TFT 2.8" 320×240 | CS=10 DC=9 RST=8 |
| Servo SG90 | PWM 50Hz, 0°/90° | GPIO 21 |
| I2S Audio | DAC + Speaker, Google TTS | BCLK=16 LRC=15 DIN=7 |
| Webcam USB | 640×480 | — (Python side) |

> **Note:** GPIO 26–32 are reserved for internal Octal SPI Flash — not used for peripherals.

---

## Project Structure

```
esp32-face-recognition-lock/
├── smart-kiosk/                  # Python AI Engine
│   ├── main.py                   # Entry point
│   ├── config.py                 # All thresholds, IPs, paths
│   ├── core/
│   │   ├── kiosk.py              # Main loop & 5-step pipeline orchestrator
│   │   ├── recognition.py        # AntiSpoofWorker + FaceRecognizer
│   │   └── registration.py       # Multi-angle face registration
│   ├── bridges/
│   │   ├── esp32_bridge.py       # Async HTTP POST to ESP32
│   │   └── firebase_bridge.py    # Firebase poll + log writer
│   ├── vision/
│   │   ├── camera.py             # Threaded camera reader
│   │   └── cv_utils.py           # EAR, head pose, blur, smooth box
│   ├── ui/
│   │   └── overlay.py            # OpenCV UI: telemetry, guide, steps
│   └── models/                   # Place model files here (not committed)
│       ├── best_model_quantized.onnx
│       ├── face_landmarker.task
│       └── vectors.npz
├── esp32/
│   └── Doan1/
│       └── Doan1.ino             # ESP32-S3 firmware (FreeRTOS, 3 tasks)
├── web/
│   ├── index.html                # Single-page Web Admin
│   ├── function.js               # Firebase listeners + admin logic
│   └── style.css
└── README.md
```

---

## Setup

### Python AI Engine

**Requirements:** Python 3.10, CUDA optional (CPU-only also works)

```bash
pip install opencv-python mediapipe onnxruntime insightface requests numpy
```

**Model files** (not included — place in `smart-kiosk/models/`):
- `best_model_quantized.onnx` — AntiSpoof binary classifier
- `face_landmarker.task` — MediaPipe FaceLandmarker model
- `vectors.npz` — face embedding database (auto-generated on first registration)

**Configure** `smart-kiosk/config.py`:
```python
ESP32_IP     = "192.168.x.x"    # your ESP32 LAN IP
FIREBASE_URL = "https://your-project-default-rtdb.firebaseio.com"
```

**Run:**
```bash
cd smart-kiosk
python main.py
# Press K to toggle telemetry dashboard
# Press Q to quit
```

### ESP32 Firmware

1. Open `esp32/Doan1/Doan1.ino` in Arduino IDE
2. Install libraries: `ESPAsyncWebServer`, `AsyncTCP`, `Firebase_ESP_Client`, `MFRC522`, `Adafruit_ILI9341`, `ESP32-audioI2S`, `ESP32Servo`, `ArduinoJson`
3. Set **Tools → Board → ESP32S3 Dev Module**, **USB CDC On Boot → Enabled**, **Partition Scheme → Huge APP**
4. Edit credentials in `Doan1.ino`:
```cpp
const char* ssid     = "your_wifi";
const char* password = "your_password";
#define FIREBASE_API_KEY "your_api_key"
#define FIREBASE_URL     "your-project-default-rtdb.firebaseio.com"
```
5. Hold **BOOT**, click **Upload**, release **BOOT** when `Connecting...` appears

### Web Admin

Open `web/index.html` in a browser directly (no web server needed — uses Firebase JS SDK).  
Default login: `admin` / `123456`

### Firebase Setup

Enable **Realtime Database** in test mode. The system auto-creates the following structure:

```
/students/          ← student profiles (name, studentId, rfid)
/DailyLogs/         ← attendance logs by date DD-MM-YYYY
/RobotLeTan/
  /Control          ← Web Admin → Python/ESP32 commands
  /AIEvents         ← Python → Web Admin events
  /Status           ← ESP32 door status (DOOR_OPEN / READY)
/admin/             ← admin existence flag
```

---

## Implementation Results

### Real-Time Telemetry (measured on test hardware)

| Metric | Value |
|--------|-------|
| Pipeline FPS | 45 fps |
| LAN Ping (Python → ESP32) | 111 ms |
| Face Inference (InsightFace buffalo_s) | 59 ms |
| AntiSpoof Eval (ONNX quantized) | 5 ms |
| RFID Response Time | 0.38 s |
| Door Hold Time | ~8–9 s |

### Pipeline Timing (per authentication step)

| Step | Time |
|------|------|
| STABLE (3s hold) | 3.01 s |
| BLINK (2× blink) | 3.35 s |
| POSE (head turn) | 3.17 s |
| **E2E Total** | **10.71 s** |

### ESP32 System Stats (Serial Monitor, uptime ~20 min)

| Metric | Value |
|--------|-------|
| Uptime | 1258 s (no watchdog reset) |
| Free Heap | 7,271,652 bytes (~7 MB) |
| WiFi RSSI | −41 dBm |
| Stack Sensor remaining | 8,896 bytes |
| cmdQueue pending | 0 items |

### Test Scenarios

| Scenario | Result |
|----------|--------|
| Unregistered RFID card | ✅ Rejected — Web shows security alert |
| Registered RFID card | ✅ Door opens, attendance logged |
| Valid face (registered) | ✅ Door opens, Web shows name + timestamp |
| Unknown face (unregistered) | ✅ Rejected — ESP32 shows angry eyes |
| Spoofing with printed photo | ✅ Blocked at PASSIVE step (SPOOF! 0%) |
| Spoofing with phone screen (far) | ✅ Blocked at PASSIVE step |
| Spoofing with phone screen (close) | ⚠️ PASSIVE bypassed — blocked at BLINK step |

---

## Limitations and Future Work

- **Video replay attack vulnerability.** The current pipeline cannot distinguish a pre-recorded video with blink + head-turn from a live person. Mitigations such as depth estimation or Moiré pattern analysis are identified as future work.
- **`detect_screen()` geometry-dependent.** The screen detection heuristic (contour area > 15000px, 4-sided polygon) fails when the phone is held close enough that the device frame is outside the ROI. A texture-based approach would be more robust.
- **Single-person per frame.** The pipeline is designed for one user at a time (`num_faces=1`). Multi-person scenarios are not handled.
- **Face DB stored locally.** `vectors.npz` is a flat file on the Python host — not synchronized to cloud. A Redis or SQLite backend would improve scalability.
- **No physical enclosure.** The current prototype is assembled on a breadboard. A proper PCB and enclosure are required for deployment.

---

## License

MIT
