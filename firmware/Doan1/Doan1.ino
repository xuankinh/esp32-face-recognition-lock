    #include <Arduino.h>
    #include <SPI.h>
    #include <MFRC522.h>
    #include <Adafruit_GFX.h>
    #include <Adafruit_ILI9341.h>
    #include <WiFi.h>
    #include <Audio.h>
    #include <Preferences.h>
    #include <esp_task_wdt.h>
    #include <time.h>
    #include <Firebase_ESP_Client.h>
    #include <addons/TokenHelper.h>
    #include <addons/RTDBHelper.h>
    #include <ESP32Servo.h>
    #include <ESPAsyncWebServer.h>
    #include <AsyncTCP.h>
    #include <ArduinoJson.h>

    // --- CHÂN ---
    #define SPI_SCK   1
    #define SPI_MISO  2
    #define SPI_MOSI  3
    #define LCD_CS    10
    #define LCD_DC    9
    #define LCD_RST   8
    #define RFID_CS   5
    #define RFID_RST  4
    #define I2S_LRC   15
    #define I2S_BCLK  16
    #define I2S_DIN   7
    #define SERVO_PIN 21

    // --- NETWORK ---
    const char* ssid     = "Xuan Kinh";
    const char* password = "20091974";

    #define FIREBASE_API_KEY "AIzaSyBMQMICyPwbxdYkbm7bELC_xytcPvmqPlY"
    #define FIREBASE_URL     "project1-d5875-default-rtdb.firebaseio.com"

    AsyncWebServer server(80);

    // ============================================================
    //  QUEUE TYPES
    // ============================================================
    typedef struct {
        char command[20];
        int  targetID;
        char rfid[20];
        char name[50];
        char step[30];
    } CommandMessage;

    typedef struct {
        char path[64];
        char value[64];
        bool isJSON;
        char jsonRaw[256];
    } FirebaseSyncRequest;

    typedef struct {
        char text[128];
    } AudioMessage;

    QueueHandle_t cmdQueue;
    QueueHandle_t firebaseQueue;
    QueueHandle_t audioQueue;

    // ============================================================
    //  BIẾN TRẠNG THÁI
    // ============================================================
    bool          isRFID_Connected = false;
    bool          isWaiting        = true;
    int           eyeDirection     = 0;
    String        currentSysDate   = "--/--/----";

    // === DOOR LOCK: biến kiểm soát chu kỳ mở cửa ===
    volatile bool doorLocked   = false;   // true = đang trong 10s mở cửa, bỏ qua quét mới
    unsigned long doorOpenTime = 0;       // millis() lúc mở cửa
    #define DOOR_OPEN_DURATION  10000     // 10 giây

    bool          hasAdmin           = false;
    unsigned long lastAdminRefresh   = 0;
    #define ADMIN_REFRESH_INTERVAL   60000

    TaskHandle_t TaskAudioHandle;
    TaskHandle_t TaskSensorsHandle;
    TaskHandle_t TaskFirebaseHandle;

    MFRC522          mfrc522(RFID_CS, RFID_RST);
    Adafruit_ILI9341 tft = Adafruit_ILI9341(&SPI, LCD_DC, LCD_CS, LCD_RST);
    Audio            audio;
    Preferences      prefs;
    FirebaseAuth     auth;
    FirebaseConfig   config;
    Servo            myServo;

    FirebaseData fbdo_stream;
    FirebaseData fbdo_sensor;
    FirebaseData fbdo_async;

    // Forward declarations
    void drawChillEyes(); void drawHappyEyes(); void drawAngryEyes(); void drawInfoEyes();
    void triggerEmotion(int type, String msg, String speechText);
    void openDoorAndLock(String name, String speechText, String logPath, FirebaseJson* logEntry);
    String getUID(); void executeEnrollment(int id); void refreshAdminStatus(bool force);
    void firebaseSetString(const char* path, const char* value);

    // ============================================================
    //  UTILS
    // ============================================================
    String removeAccents(String text) {
        String r = text;
        r.replace("á","a"); r.replace("à","a"); r.replace("ả","a"); r.replace("ã","a"); r.replace("ạ","a");
        r.replace("â","a"); r.replace("ấ","a"); r.replace("ầ","a"); r.replace("ẩ","a"); r.replace("ẫ","a"); r.replace("ậ","a"); r.replace("ă","a"); r.replace("ắ","a"); r.replace("ằ","a"); r.replace("ẳ","a"); r.replace("ẵ","a"); r.replace("ặ","a");
        r.replace("é","e"); r.replace("è","e"); r.replace("ẻ","e"); r.replace("ẽ","e"); r.replace("ẹ","e");
        r.replace("ê","e"); r.replace("ế","e"); r.replace("ề","e"); r.replace("ể","e"); r.replace("ễ","e"); r.replace("ệ","e");
        r.replace("í","i"); r.replace("ì","i"); r.replace("ỉ","i"); r.replace("ĩ","i"); r.replace("ị","i");
        r.replace("ó","o"); r.replace("ò","o"); r.replace("ỏ","o"); r.replace("õ","o"); r.replace("ọ","o");
        r.replace("ô","o"); r.replace("ố","o"); r.replace("ồ","o"); r.replace("ổ","o"); r.replace("ỗ","o"); r.replace("ộ","o"); r.replace("ơ","o"); r.replace("ớ","o"); r.replace("ờ","o"); r.replace("ở","o"); r.replace("ỡ","o"); r.replace("ợ","o");
        r.replace("ú","u"); r.replace("ù","u"); r.replace("ủ","u"); r.replace("ũ","u"); r.replace("ụ","u");
        r.replace("ư","u"); r.replace("ứ","u"); r.replace("ừ","u"); r.replace("ử","u"); r.replace("ữ","u"); r.replace("ự","u");
        r.replace("ý","y"); r.replace("ỳ","y"); r.replace("ỷ","y"); r.replace("ỹ","y"); r.replace("ỵ","y");
        r.replace("đ","d");
        r.replace("Á","A"); r.replace("À","A"); r.replace("Ả","A"); r.replace("Ã","A"); r.replace("Ạ","A");
        r.replace("Â","A"); r.replace("Ấ","A"); r.replace("Ầ","A"); r.replace("Ẩ","A"); r.replace("Ẫ","A"); r.replace("Ậ","A"); r.replace("Ă","A"); r.replace("Ắ","A"); r.replace("Ằ","A"); r.replace("Ẳ","A"); r.replace("Ẵ","A"); r.replace("Ặ","A");
        r.replace("É","E"); r.replace("È","E"); r.replace("Ẻ","E"); r.replace("Ẽ","E"); r.replace("Ẹ","E");
        r.replace("Ê","E"); r.replace("Ế","E"); r.replace("Ề","E"); r.replace("Ể","E"); r.replace("Ễ","E"); r.replace("Ệ","E");
        r.replace("Í","I"); r.replace("Ì","I"); r.replace("Ỉ","I"); r.replace("Ĩ","I"); r.replace("Ị","I");
        r.replace("Ó","O"); r.replace("Ò","O"); r.replace("Ỏ","O"); r.replace("Õ","O"); r.replace("Ọ","O");
        r.replace("Ô","O"); r.replace("Ố","O"); r.replace("Ồ","O"); r.replace("Ổ","O"); r.replace("Ỗ","O"); r.replace("Ộ","O"); r.replace("Ơ","O"); r.replace("Ớ","O"); r.replace("Ờ","O"); r.replace("Ở","O"); r.replace("Ỡ","O"); r.replace("Ợ","O");
        r.replace("Ú","U"); r.replace("Ù","U"); r.replace("Ủ","U"); r.replace("Ũ","U"); r.replace("Ụ","U");
        r.replace("Ư","U"); r.replace("Ứ","U"); r.replace("Ừ","U"); r.replace("Ử","U"); r.replace("Ữ","U"); r.replace("Ự","U");
        r.replace("Ý","Y"); r.replace("Ỳ","Y"); r.replace("Ỷ","Y"); r.replace("Ỹ","Y"); r.replace("Ỵ","Y");
        r.replace("Đ","D");
        return r;
    }

    String getUID() {
        String s = "";
        for (byte i = 0; i < mfrc522.uid.size; i++) {
            s += String(mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
            s += String(mfrc522.uid.uidByte[i], HEX);
        }
        s.toUpperCase();
        return s;
    }

    bool getTimeNonBlocking(struct tm* timeinfo) {
        time_t now; time(&now); localtime_r(&now, timeinfo);
        return (now > 1000000000UL);
    }

    void refreshAdminStatus(bool force) {
        unsigned long now = millis();
        if (!force && (now - lastAdminRefresh < ADMIN_REFRESH_INTERVAL)) return;
        if (!Firebase.ready()) return;
        if (Firebase.RTDB.getString(&fbdo_sensor, "/admin/exists")) {
            String val = fbdo_sensor.stringData();
            val.trim(); val.toLowerCase();
            hasAdmin = (val == "true" || val == "1");
            lastAdminRefresh = now;
            Serial.printf("[Firebase] Admin=%s\n", hasAdmin ? "true" : "false");
        }
    }

  
    * @param name        Tên người được xác thực
    * @param speechText  Văn bản TTS
    * @param logPath     Path Firebase để push log (có thể "")
    * @param logEntry    Con trỏ FirebaseJson log (NULL nếu không cần)
    */
    void openDoorAndLock(String name, String speechText, String logPath, FirebaseJson* logEntry) {
        // Nếu đang trong chu kỳ mở → bỏ qua hoàn toàn
        if (doorLocked) {
            Serial.println("[DOOR] Đang trong chu kỳ mở cửa, bỏ qua lệnh mới.");
            return;
        }

        // Mở cửa
        myServo.write(90);
        doorLocked   = true;
        doorOpenTime = millis();

        Serial.printf("[DOOR] Mở cửa cho: %s — Khóa 10 giây.\n", name.c_str());

        // Hiển thị & phát âm
        triggerEmotion(1, name, speechText);

        // Ghi log Firebase (tuỳ chọn)
        if (logPath != "" && logEntry != nullptr) {
            firebasePushJSON(logPath.c_str(), logEntry->raw());
        }

        // Báo trạng thái lên Firebase
        firebaseSetString("/RobotLeTan/Status", "DOOR_OPEN");
    }

    // ============================================================
    //  FIREBASE TASK
    // ============================================================
    void TaskFirebaseCode(void* pvParameters) {
        FirebaseSyncRequest req;
        for (;;) {
            if (xQueueReceive(firebaseQueue, &req, portMAX_DELAY) == pdTRUE) {
                if (!Firebase.ready()) { vTaskDelay(100 / portTICK_PERIOD_MS); continue; }
                if (req.isJSON) {
                    FirebaseJson j; j.setJsonData(String(req.jsonRaw));
                    Firebase.RTDB.pushJSON(&fbdo_async, req.path, &j);
                } else {
                    Firebase.RTDB.setString(&fbdo_async, req.path, req.value);
                }
            }
            vTaskDelay(10 / portTICK_PERIOD_MS);
        }
    }

    void firebaseSetString(const char* path, const char* value) {
        FirebaseSyncRequest req; memset(&req, 0, sizeof(req));
        strncpy(req.path,  path,  63);
        strncpy(req.value, value, 63);
        req.isJSON = false;
        xQueueSend(firebaseQueue, &req, 0);
    }

    void firebasePushJSON(const char* path, const char* jsonRaw) {
        FirebaseSyncRequest req; memset(&req, 0, sizeof(req));
        strncpy(req.path,    path,    63);
        strncpy(req.jsonRaw, jsonRaw, 255);
        req.isJSON = true;
        xQueueSend(firebaseQueue, &req, 0);
    }

    // ============================================================
    //  ENROLLMENT
    // ============================================================
    void executeEnrollment(int id) {
        triggerEmotion(3, "DANG KY ADMIN", "Vui lòng quẹt thẻ từ để thiết lập Quản trị viên");
        unsigned long waitTime = millis();
        bool cardLinked = false;
        while (millis() - waitTime < 15000) {
            esp_task_wdt_reset();
            if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
                String uid = getUID();
                mfrc522.PICC_HaltA();
                prefs.putInt(uid.c_str(), id);
                firebaseSetString(("/students/" + String(id) + "/rfid").c_str(), uid.c_str());
                firebaseSetString("/admin/exists", "true");
                hasAdmin = true;
                lastAdminRefresh = millis();
                triggerEmotion(1, "TAO ADMIN OK", "Đã thiết lập thẻ Quản trị viên thành công.");
                cardLinked = true;
                break;
            }
            vTaskDelay(50 / portTICK_PERIOD_MS);
        }
        if (!cardLinked) triggerEmotion(2, "HUY DANG KY", "Hết thời gian. Đăng ký bị hủy.");
    }

    // ============================================================
    //  TASK SENSORS — Core 1
    // ============================================================
    void TaskSensorsCode(void* pvParameters) {
        esp_task_wdt_add(NULL);
        CommandMessage cmd;

        for (;;) {
            esp_task_wdt_reset();

            // Cập nhật ngày giờ
            struct tm timeinfo;
            if (getTimeNonBlocking(&timeinfo)) {
                char d[15]; strftime(d, sizeof(d), "%d/%m/%Y", &timeinfo);
                currentSysDate = String(d);
            }

            refreshAdminStatus(false);

            // ============================================================
            //  XỬ LÝ QUEUE LỆNH (từ Web / Python AI / Firebase Stream)
            // ============================================================
            while (xQueueReceive(cmdQueue, &cmd, 0) == pdTRUE) {
                String command = String(cmd.command);

                // ---- Các lệnh quản trị không bị ảnh hưởng bởi doorLocked ----
                if (command == "FORCE_SAVE_RFID") {
                    String rfid = String(cmd.rfid); rfid.trim();
                    if (rfid != "") {
                        prefs.putInt(rfid.c_str(), cmd.targetID);
                        Serial.printf("[RFID] Lưu thẻ %s → ID %d\n", rfid.c_str(), cmd.targetID);
                        triggerEmotion(1, "DA LUU THE MOI", "Đồng bộ thẻ thành công!");
                    }
                }
                else if (command == "SYNC_ADMIN")   { refreshAdminStatus(true); }
                else if (command == "DELETE_CARD") {
                    String rfid = String(cmd.rfid); rfid.trim();
                    if (rfid != "" && rfid != "Trống") {
                        prefs.remove(rfid.c_str());
                        triggerEmotion(2, "THE DA VO HIEU", "Đã xóa thẻ khỏi bộ nhớ máy.");
                    }
                }
                else if (command == "REG_ADMIN")    { executeEnrollment(1); }
                else if (command == "UNLOCK_ADMIN") {
                    triggerEmotion(3, "XAC THUC ADMIN", "Vui lòng quẹt thẻ Quản trị viên.");
                    unsigned long t = millis(); bool ok = false;
                    while (millis() - t < 10000) {
                        esp_task_wdt_reset();
                        if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
                            String uid = getUID(); mfrc522.PICC_HaltA();
                            if (prefs.getInt(uid.c_str(), 0) == 1) { ok = true; break; }
                            else triggerEmotion(2, "SAI THE", "Thẻ không có quyền.");
                        }
                        vTaskDelay(50 / portTICK_PERIOD_MS);
                    }
                    firebaseSetString("/RobotLeTan/Status", ok ? "ADMIN_UNLOCKED" : "UNLOCK_FAILED");
                    if (!ok) triggerEmotion(2, "SAI QUYEN", "Từ chối mở khóa.");
                }
                else if (command == "CHANGE_ADMIN") {
                    triggerEmotion(2, "DOI ADMIN", "Quẹt thẻ Admin CŨ để xác nhận.");
                    unsigned long t = millis(); bool ok = false;
                    while (millis() - t < 10000) {
                        esp_task_wdt_reset();
                        if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
                            String uid = getUID(); mfrc522.PICC_HaltA();
                            if (prefs.getInt(uid.c_str(), 0) == 1) { prefs.remove(uid.c_str()); ok = true; break; }
                        }
                        vTaskDelay(50 / portTICK_PERIOD_MS);
                    }
                    if (ok) {
                        firebaseSetString("/RobotLeTan/Status", "ADMIN_CLEARED");
                        triggerEmotion(1, "ADMIN DA GO", "Sẵn sàng đăng ký mới.");
                        hasAdmin = false;
                    } else triggerEmotion(2, "THAT BAI", "Xác thực không hợp lệ.");
                }
                else if (command == "ADMIN_RESET") {
                    triggerEmotion(2, "XAC THUC RESET", "Quẹt thẻ Admin để xác nhận xóa!");
                    unsigned long t = millis(); bool verified = false; String adminUid = "";
                    while (millis() - t < 10000) {
                        esp_task_wdt_reset();
                        if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
                            String uid = getUID(); mfrc522.PICC_HaltA();
                            if (prefs.getInt(uid.c_str(), 0) == 1) { adminUid = uid; verified = true; break; }
                        }
                        vTaskDelay(50 / portTICK_PERIOD_MS);
                    }
                    if (verified) {
                        prefs.clear(); prefs.putInt(adminUid.c_str(), 1); hasAdmin = true;
                        triggerEmotion(1, "DA XOA DATA", "Đã xóa toàn bộ dữ liệu.");
                        firebaseSetString("/RobotLeTan/Status", "RESET_DONE");
                    } else triggerEmotion(3, "HET GIO", "Hủy thao tác xóa.");
                }

                // ---- Lệnh từ Python AI (face pipeline) ----
                else if (command == "START_REGISTER") {
                    String regName = String(cmd.name);
                    triggerEmotion(3, "DANG KY MAT", "Bắt đầu đăng ký khuôn mặt cho " + regName + ". Nhìn thẳng vào camera.");
                }
                else if (command == "CHALLENGE_STEP") {
                    String s = String(cmd.step);
                    if      (s == "PASSIVE")    triggerEmotion(3, "DANG KIEM TRA",  "Hệ thống đang xác thực.");
                    else if (s == "BLINK")      triggerEmotion(3, "NHAY MAT 1 LAN", "Vui lòng nháy mắt.");
                    else if (s == "TURN_LEFT")  triggerEmotion(3, "QUAY TRAI",      "Vui lòng quay mặt sang trái.");
                    else if (s == "TURN_RIGHT") triggerEmotion(3, "QUAY PHAI",      "Vui lòng quay mặt sang phải.");
                    else if (s == "RECOGNIZE")  triggerEmotion(3, "DANG NHAN DIEN", "Đang nhận diện khuôn mặt.");
                    else if (s == "IDLE")       { isWaiting = true; drawChillEyes(); }
                }
                else if (command == "FACE_UNKNOWN") {
                    // Chỉ hiển thị nếu cửa đang đóng (tránh flicker trong chu kỳ mở)
                    if (!doorLocked)
                        triggerEmotion(2, "KHONG NHAN RA", "Khuôn mặt không có trong hệ thống.");
                }
                else if (command == "SPOOF_ALERT") {
                    if (!doorLocked)
                        triggerEmotion(2, "PHAT HIEN GIAN LAN", "Phát hiện hành vi giả mạo. Từ chối truy cập.");
                }
                // ---- FACE_RECOGNIZED: dùng openDoorAndLock ----
                else if (command == "FACE_RECOGNIZED") {
                    String recognizedName = String(cmd.name);
                    String speech = "Xin chao " + recognizedName + ". Chuc ban mot ngay tot lanh.";
                    openDoorAndLock(recognizedName, speech, "", nullptr);

                    // Lấy thời gian cho log
                    struct tm st; String todayStr = "Unknown", timeStr = "00:00:00";
                    if (getTimeNonBlocking(&st)) {
                        char d[15]; strftime(d, sizeof(d), "%d-%m-%Y", &st); todayStr = String(d);
                        char t2[10]; strftime(t2, sizeof(t2), "%H:%M:%S", &st); timeStr = String(t2);
                    }
                    FirebaseJson faceLog;
                    faceLog.add("name",   recognizedName);
                    faceLog.add("method", "face");
                    faceLog.add("time",   timeStr);
                    String facePath = "/DailyLogs/" + todayStr;

                    openDoorAndLock(recognizedName, speech, facePath, &faceLog);
                }
            }

            // ============================================================
            //  KIỂM TRA ĐÓNG CỬA SAU 10 GIÂY (thay thế logic 5s cũ)
            // ============================================================
            if (doorLocked && (millis() - doorOpenTime >= DOOR_OPEN_DURATION)) {
                myServo.write(0);           // Đóng cửa
                doorLocked = false;         // Mở khóa để chấp nhận người tiếp theo
                isWaiting  = true;
                eyeDirection = 0;
                drawChillEyes();
                firebaseSetString("/RobotLeTan/Status", "READY");
                Serial.println("[DOOR] Đóng cửa sau 10 giây — Sẵn sàng quét tiếp.");
            }

            // ============================================================
            //  RFID SCAN — chỉ xử lý khi cửa đang đóng (doorLocked == false)
            // ============================================================
            if (!doorLocked && mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
                String uid = getUID();
                mfrc522.PICC_HaltA();

                struct tm scanTime;
                String todayStr = "Unknown", timeStr = "00:00:00";
                if (getTimeNonBlocking(&scanTime)) {
                    char d[15]; strftime(d, sizeof(d), "%d-%m-%Y", &scanTime); todayStr = String(d);
                    char t[10]; strftime(t, sizeof(t), "%H:%M:%S", &scanTime); timeStr  = String(t);
                }

                int id = prefs.getInt(uid.c_str(), -1);

                if (!hasAdmin) {
                    triggerEmotion(2, "HE THONG TRONG", "Chưa cấu hình Quản trị viên.");
                    FirebaseJson j; j.add("rfid", uid); j.add("time", timeStr);
                    firebasePushJSON("/RobotLeTan/UnregisteredCards", j.raw());
                }
                else if (id != -1) {
                    // Lấy tên từ Firebase
                    String name = "";
                    if (Firebase.RTDB.getString(&fbdo_sensor, "/students/" + String(id) + "/name"))
                        name = fbdo_sensor.stringData();
                    if (name == "" || name == "null")
                        name = (id == 1) ? "Quan tri vien" : "Nguoi dung " + String(id);

                    String speech = "Xin chào " + name + ". Chúc bạn một ngày tốt lành.";
                    FirebaseJson logEntry;
                    logEntry.add("id",     id);
                    logEntry.add("cardId", uid);
                    logEntry.add("name",   name);
                    logEntry.add("method", "rfid");
                    logEntry.add("time",   timeStr);
                    String logPath = "/DailyLogs/" + todayStr;

                    openDoorAndLock(name, speech, logPath, &logEntry);
                }
                else {
                    // Thẻ lạ — không mở cửa, không lock
                    triggerEmotion(3, "THE KHONG HOP LE", "Thẻ chưa được cấp phép.");
                    FirebaseJson j; j.add("rfid", uid); j.add("time", timeStr);
                    firebasePushJSON("/RobotLeTan/UnregisteredCards", j.raw());
                }
            }

            // Mắt nhìn ngẫu nhiên khi idle (chỉ khi chờ và cửa đóng)
            if (isWaiting && !doorLocked && random(0, 100) < 5) {
                eyeDirection = random(0, 3);
                drawChillEyes();
                vTaskDelay(300 / portTICK_PERIOD_MS);
            }

            vTaskDelay(50 / portTICK_PERIOD_MS);
        }
    }

    // ============================================================
    //  TASK AUDIO
    // ============================================================
    void TaskAudioCode(void* pvParameters) {
        AudioMessage audioMsg;
        for (;;) {
            if (xQueueReceive(audioQueue, &audioMsg, pdMS_TO_TICKS(10)) == pdTRUE)
                audio.connecttospeech(audioMsg.text, "vi");
            audio.loop();
            vTaskDelay(1 / portTICK_PERIOD_MS);
        }
    }

    void speakText(const String& text) {
        AudioMessage msg; memset(&msg, 0, sizeof(msg));
        strncpy(msg.text, text.c_str(), 127);
        xQueueSend(audioQueue, &msg, pdMS_TO_TICKS(50));
    }

    // ============================================================
    //  LOCAL API SERVER
    // ============================================================
    void setupServer() {
        DefaultHeaders::Instance().addHeader("Access-Control-Allow-Origin",  "*");
        DefaultHeaders::Instance().addHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
        DefaultHeaders::Instance().addHeader("Access-Control-Allow-Headers", "Content-Type");

        server.on("/api/control", HTTP_POST, [](AsyncWebServerRequest* request){},
        NULL, [](AsyncWebServerRequest* request, uint8_t* data, size_t len, size_t index, size_t total){
            DynamicJsonDocument doc(512);
            if (deserializeJson(doc, (const char*)data, len)) {
                request->send(400, "application/json", "{\"status\":\"error\",\"message\":\"JSON parse failed\"}");
                return;
            }
            CommandMessage cmd; memset(&cmd, 0, sizeof(cmd));
            if (doc.containsKey("command"))  strncpy(cmd.command,  doc["command"],  19);
            if (doc.containsKey("targetID")) cmd.targetID = doc["targetID"].as<int>();
            if (doc.containsKey("rfid"))     strncpy(cmd.rfid,     doc["rfid"],     19);
            if (doc.containsKey("name"))     strncpy(cmd.name,     doc["name"],     49);
            if (doc.containsKey("step"))     strncpy(cmd.step,     doc["step"],     29);
            if (doc.containsKey("reason"))   strncpy(cmd.step,     doc["reason"],   29);
            xQueueSend(cmdQueue, &cmd, 0);
            Serial.println("[API] Lệnh cục bộ: " + String(cmd.command));
            request->send(200, "application/json", "{\"status\":\"success\"}");
        });

        server.onNotFound([](AsyncWebServerRequest* request){
            if (request->method() == HTTP_OPTIONS) request->send(200);
            else request->send(404, "text/plain", "Not found");
        });

        server.begin();
        Serial.println("[HTTP] Server cục bộ chạy tại Port 80");
    }

    // ============================================================
    //  FIREBASE STREAM (lệnh từ Web)
    // ============================================================
    void streamCallback(FirebaseStream data) {
        if (data.dataType() == "json") {
            FirebaseJson json; json.setJsonData(data.jsonString());
            FirebaseJsonData result;
            CommandMessage cmd; memset(&cmd, 0, sizeof(cmd));
            json.get(result, "command");  if (result.success) strncpy(cmd.command, result.stringValue.c_str(), 19);
            json.get(result, "targetID"); if (result.success) cmd.targetID = result.intValue;
            json.get(result, "rfid");     if (result.success) strncpy(cmd.rfid, result.stringValue.c_str(), 19);
            json.get(result, "name");     if (result.success) strncpy(cmd.name, result.stringValue.c_str(), 49);
            xQueueSend(cmdQueue, &cmd, 0);
            Serial.println("[FIREBASE WEB] Lệnh từ giao diện: " + String(cmd.command));
        }
    }

    void streamTimeoutCallback(bool timeout) {
        if (timeout) Serial.println("[FIREBASE] Stream timeout, đang kết nối lại...");
    }

    // ============================================================
    //  SETUP
    // ============================================================
    void setup() {
        delay(1000);
        Serial.begin(115200);
        Serial.println("\n[SYSTEM] Hệ thống đang khởi động...");

        SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI, -1);
        tft.begin(); tft.setRotation(3); tft.fillScreen(ILI9341_BLACK);

        esp_task_wdt_config_t wdt = { .timeout_ms = 12000, .idle_core_mask = 3, .trigger_panic = true };
        esp_task_wdt_reconfigure(&wdt);

        ESP32PWM::allocateTimer(0);
        myServo.setPeriodHertz(50);
        myServo.attach(SERVO_PIN, 500, 2400);
        myServo.write(0);   // Đảm bảo cửa đóng khi khởi động

        mfrc522.PCD_Init();
        byte v = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
        isRFID_Connected = (v != 0x00 && v != 0xFF);

        prefs.begin("robot_data", false);

        Serial.println("[WiFi] Đang kết nối...");
        WiFi.begin(ssid, password);
        while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
        Serial.printf("\n[WiFi] IP: %s\n", WiFi.localIP().toString().c_str());

        configTime(7 * 3600, 0, "pool.ntp.org", "time.nist.gov");

        cmdQueue      = xQueueCreate(15, sizeof(CommandMessage));
        firebaseQueue = xQueueCreate(20, sizeof(FirebaseSyncRequest));
        audioQueue    = xQueueCreate(5,  sizeof(AudioMessage));

        config.api_key      = FIREBASE_API_KEY;
        config.database_url = FIREBASE_URL;
        config.signer.test_mode = true;
        Firebase.begin(&config, &auth);
        Firebase.reconnectWiFi(true);

        if (Firebase.RTDB.beginStream(&fbdo_stream, "/RobotLeTan/Control")) {
            Firebase.RTDB.setStreamCallback(&fbdo_stream, streamCallback, streamTimeoutCallback);
            Serial.println("[FIREBASE] Stream lắng nghe Web đã bật.");
        }

        refreshAdminStatus(true);
        setupServer();

        audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DIN);
        audio.setVolume(18);
        drawChillEyes();

        xTaskCreatePinnedToCore(TaskAudioCode,    "TaskAudio",    16000, NULL, 2, &TaskAudioHandle,    0);
        xTaskCreatePinnedToCore(TaskSensorsCode,  "TaskSensors",  16000, NULL, 1, &TaskSensorsHandle,  1);
        xTaskCreatePinnedToCore(TaskFirebaseCode, "TaskFirebase",  8000, NULL, 1, &TaskFirebaseHandle,  0);

        Serial.println("[SYSTEM] Khởi động đa nhân hoàn tất.");
    }

    void loop() {
        vTaskDelay(1000 / portTICK_PERIOD_MS);
    }

    // ============================================================
    //  DISPLAY
    // ============================================================
    void triggerEmotion(int type, String msg, String speechText) {
        isWaiting = false;
        tft.fillScreen(ILI9341_BLACK);
        tft.setCursor(10, 5);  tft.setTextColor(ILI9341_WHITE); tft.setTextSize(1); tft.print(currentSysDate);
        tft.fillRect(0, 20, 320, 40, ILI9341_DARKGREY);
        tft.setCursor(10, 32); tft.setTextColor(ILI9341_WHITE); tft.setTextSize(2); tft.print(removeAccents(msg));
        speakText(speechText);
        if      (type == 1) drawHappyEyes();
        else if (type == 2) drawAngryEyes();
        else                drawInfoEyes();
    }

    void drawChillEyes() {
        tft.fillScreen(ILI9341_BLACK);
        tft.setCursor(10, 5);   tft.setTextColor(ILI9341_WHITE); tft.setTextSize(1); tft.print(currentSysDate);
        tft.setCursor(280, 5);  tft.setTextColor(isRFID_Connected ? ILI9341_GREEN : ILI9341_RED); tft.print("RFID");
        tft.fillRoundRect(60,  90, 60, 80, 20, ILI9341_CYAN);
        tft.fillRoundRect(200, 90, 60, 80, 20, ILI9341_CYAN);
        int o = (eyeDirection == 1) ? -15 : (eyeDirection == 2 ? 15 : 0);
        tft.fillCircle(90  + o, 130, 15, ILI9341_BLACK);
        tft.fillCircle(230 + o, 130, 15, ILI9341_BLACK);
    }

    void drawHappyEyes() {
        tft.fillRoundRect(60,  90, 60, 80, 20, ILI9341_GREEN);
        tft.fillRoundRect(200, 90, 60, 80, 20, ILI9341_GREEN);
        tft.fillCircle(90,  150, 40, ILI9341_BLACK);
        tft.fillCircle(230, 150, 40, ILI9341_BLACK);
    }

    void drawAngryEyes() {
        tft.fillRoundRect(60,  90, 60, 80, 20, ILI9341_RED);
        tft.fillRoundRect(200, 90, 60, 80, 20, ILI9341_RED);
        tft.fillTriangle(40,  80, 140, 80, 140, 130, ILI9341_BLACK);
        tft.fillTriangle(180, 80, 280, 80, 180, 130, ILI9341_BLACK);
    }

    void drawInfoEyes() {
        tft.fillRoundRect(60, 80, 60, 90, 20, ILI9341_YELLOW);
        tft.fillCircle(230, 125, 35, ILI9341_YELLOW);
    }
