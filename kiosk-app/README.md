# Smart AIoT Kiosk V5

Hệ thống kiểm soát ra vào thông minh kết hợp nhận diện khuôn mặt và thẻ RFID.

## Kiến trúc

```
Web Admin ──────────────────────► Firebase (lệnh đăng ký)
                                       │
Python AI Engine (main.py) ◄───────────┘
        │
        │  HTTP POST /api/control
        ▼
ESP32 (cổng 80) ── RFID tự xử lý độc lập
        │
        ▼
Firebase (ghi log DailyLogs)
```

## Cấu trúc thư mục

```
smart-kiosk/
├── main.py              # Entry point
├── config.py            # Cấu hình IP, ngưỡng, thông số
├── core/
│   ├── kiosk.py         # Vòng lặp chính
│   ├── recognition.py   # AntiSpoof + InsightFace
│   └── registration.py  # Đăng ký khuôn mặt
├── bridges/
│   ├── esp32_bridge.py  # Gửi lệnh xuống ESP32
│   └── firebase_bridge.py # Poll lệnh Web Admin + ghi log
├── vision/
│   ├── camera.py        # Camera thread
│   └── cv_utils.py      # Các hàm xử lý ảnh
├── ui/
│   └── overlay.py       # Vẽ UI lên frame
└── models/              # Đặt file model vào đây (không commit)
    ├── best_model_quantized.onnx
    ├── face_landmarker.task
    └── vectors.npz
```

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cấu hình

Sửa `config.py`:
```python
ESP32_IP     = "192.168.1.XX"   # IP tĩnh của ESP32
FIREBASE_URL = "https://..."    # URL Firebase của bạn
```

## Chạy

```bash
python main.py
```

## Phím tắt

| Phím | Chức năng |
|------|-----------|
| `Q`  | Thoát     |
| `K`  | Bật/tắt bảng KPI |
