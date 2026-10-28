
#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <LittleFS.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <ArduinoJson.h>
#include <math.h>
#include "gesture_model.h"
#include "yes_no_model.h"

// ========================================
// WIFI
// ========================================
const char* WIFI_SSID = "ur wifi ssd(basicaly ur name)";
const char* WIFI_PASSWORD = "ur wifi pssword";

// ========================================
// FLEX SENSOR PINS
// ========================================
#define FLEX_THUMB  34
#define FLEX_INDEX  35
#define FLEX_MIDDLE 32
#define FLEX_RING   33
#define FLEX_PINKY  36

// ========================================
// MPU6050: DIRECT I2C ACCESS
// SDA = GPIO 21, SCL = GPIO 22
// AD0 connected to GND -> address 0x68
// ========================================
#define SDA_PIN 21
#define SCL_PIN 22
#define MPU_ADDR 0x68

bool mpuDetected = false;
unsigned long lastMPURetry = 0;

// ========================================
// WEB SERVER
// ========================================
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

// ========================================
// EXISTING 8-CLASS RANDOM FOREST
// Feature order: thumb, index, middle, ring, pinky
// ========================================
Eloquent::ML::Port::GestureModel model;

const int NUM_CLASSES = 8;

const char* gestureLabels[NUM_CLASSES] = {
    "FOOD",
    "GOOD_FOR_YOU",
    "HAVE_A_GOOD_DAY",
    "IDLE",
    "IM_OKAY",
    "STOP",
    "THANK_YOU",
    "WATER"
};

unsigned long lastPredictionTime = 0;
unsigned long lastSendTime = 0;

const unsigned long PREDICTION_INTERVAL_MS = 100;
const unsigned long SEND_INTERVAL_MS = 300;

String lastGesture = "";

// ========================================
// YES / NO / REST MOTION MODEL
// Feature order must match train_yes_no.py:
// thumb, ax, ay, az, gx, gy, gz; each has
// mean, std, min, max, delta.
// ========================================
Eloquent::ML::Port::YesNoModel motionModel;

const char* motionLabels[3] = {"NO", "REST", "YES"};

const int NUM_SIGNALS = 7;
const int STATS_PER_SIGNAL = 5;
const int NUM_MOTION_FEATURES = 35;
const int WINDOW_SIZE = 8;
const int REQUIRED_STREAK = 3;

float motionWindow[WINDOW_SIZE][NUM_SIGNALS];
int windowCount = 0;
int windowWriteIndex = 0;

String activeMotionSign = "";
String candidateMotionSign = "";
int candidateCount = 0;

// ========================================
// LOW-LEVEL MPU6050 REGISTER FUNCTIONS
// ========================================
bool writeMPURegister(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(reg);
    Wire.write(value);

    return Wire.endTransmission() == 0;
}

bool readMPURegister(uint8_t reg, uint8_t &value) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(reg);

    if (Wire.endTransmission(false) != 0) {
        return false;
    }

    if (Wire.requestFrom((uint8_t)MPU_ADDR,
                         (uint8_t)1,
                         (uint8_t)true) != 1) {
        return false;
    }

    value = Wire.read();
    return true;
}

// ========================================
// INITIALIZE MPU6050 WITHOUT ADafruit begin()
// ========================================
bool initializeMPU() {
    Serial.println();
    Serial.println("Initializing MPU6050 directly...");
    Serial.println("SDA = GPIO 21, SCL = GPIO 22");

    Wire.beginTransmission(MPU_ADDR);

    if (Wire.endTransmission() != 0) {
        Serial.println("MPU6050 address 0x68 not responding.");
        return false;
    }

    uint8_t whoAmI = 0;

    if (!readMPURegister(0x75, whoAmI)) {
        Serial.println("Cannot read MPU6050 WHO_AM_I register.");
        return false;
    }

    Serial.printf("MPU WHO_AM_I = 0x%02X\n", whoAmI);

    // Standard MPU6050 normally returns 0x68.
    // Some compatible chips return a different ID.
    if (whoAmI != 0x68 && whoAmI != 0x70) {
    Serial.println("Unsupported chip ID.");
    return false;
}

if (whoAmI == 0x70) {
    Serial.println("MPU6500-compatible sensor detected.");
} else {
    Serial.println("MPU6050 detected.");
}

    // Wake up the sensor.
    if (!writeMPURegister(0x6B, 0x00)) {
        Serial.println("Failed to wake MPU6050.");
        return false;
    }

    delay(100);

    // Digital low-pass filter: approximately 44 Hz accel bandwidth.
    if (!writeMPURegister(0x1A, 0x03)) {
        return false;
    }

    // Gyroscope range: +/-500 degrees/second.
    if (!writeMPURegister(0x1B, 0x08)) {
        return false;
    }

    // Accelerometer range: +/-8 g.
    if (!writeMPURegister(0x1C, 0x10)) {
        return false;
    }

    Serial.println("MPU6050 INITIALIZED SUCCESSFULLY.");
    Serial.println("Accelerometer and gyroscope ready.");

    return true;
}

// ========================================
// READ 16-BIT SIGNED VALUE
// ========================================
int16_t readInt16() {
    uint8_t highByte = Wire.read();
    uint8_t lowByte = Wire.read();

    return (int16_t)(((uint16_t)highByte << 8) | lowByte);
}

// ========================================
// READ ACCELEROMETER AND GYROSCOPE
// Accelerometer output: m/s^2
// Gyroscope output: rad/s
// ========================================
bool readMPU(
    float &ax, float &ay, float &az,
    float &gx, float &gy, float &gz
) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x3B);  // First accelerometer output register

    if (Wire.endTransmission(false) != 0) {
        return false;
    }

    // Read 14 bytes: accel, temperature, gyro.
    if (Wire.requestFrom((uint8_t)MPU_ADDR,
                         (uint8_t)14,
                         (uint8_t)true) != 14) {
        return false;
    }

    int16_t rawAX = readInt16();
    int16_t rawAY = readInt16();
    int16_t rawAZ = readInt16();

    int16_t rawTemp = readInt16();
    (void)rawTemp;  // Temperature is not used for sign recognition.

    int16_t rawGX = readInt16();
    int16_t rawGY = readInt16();
    int16_t rawGZ = readInt16();

    // +/-8 g: 4096 raw counts per g.
    const float ACCEL_SCALE = 4096.0f;

    // +/-500 degrees/second: 65.5 counts per degree/second.
    const float GYRO_SCALE = 65.5f;
    const float MY_DEG_TO_RAD = 0.01745329252f;

    ax = ((float)rawAX / ACCEL_SCALE) * 9.80665f;
    ay = ((float)rawAY / ACCEL_SCALE) * 9.80665f;
    az = ((float)rawAZ / ACCEL_SCALE) * 9.80665f;

    gx = ((float)rawGX / GYRO_SCALE) * MY_DEG_TO_RAD;
    gy = ((float)rawGY / GYRO_SCALE) * MY_DEG_TO_RAD;
    gz = ((float)rawGZ / GYRO_SCALE) * MY_DEG_TO_RAD;

    return true;
}

// ========================================
// MOTION FEATURE WINDOW AND CLASSIFICATION
// ========================================
void addMotionSample(float thumb, float ax, float ay, float az,
                     float gx, float gy, float gz) {
    motionWindow[windowWriteIndex][0] = thumb;
    motionWindow[windowWriteIndex][1] = ax;
    motionWindow[windowWriteIndex][2] = ay;
    motionWindow[windowWriteIndex][3] = az;
    motionWindow[windowWriteIndex][4] = gx;
    motionWindow[windowWriteIndex][5] = gy;
    motionWindow[windowWriteIndex][6] = gz;

    windowWriteIndex = (windowWriteIndex + 1) % WINDOW_SIZE;

    if (windowCount < WINDOW_SIZE) {
        windowCount++;
    }
}

void makeMotionFeatures(float features[NUM_MOTION_FEATURES]) {
    for (int signal = 0; signal < NUM_SIGNALS; signal++) {
        float sum = 0.0f;
        float minimum = INFINITY;
        float maximum = -INFINITY;

        // Iterate in chronological order through the rolling window.
        for (int i = 0; i < windowCount; i++) {
            int index = (windowWriteIndex - windowCount + i + WINDOW_SIZE)
                        % WINDOW_SIZE;
            float value = motionWindow[index][signal];
            sum += value;
            if (value < minimum) minimum = value;
            if (value > maximum) maximum = value;
        }

        float mean = sum / windowCount;
        float squaredDifferenceSum = 0.0f;

        for (int i = 0; i < windowCount; i++) {
            int index = (windowWriteIndex - windowCount + i + WINDOW_SIZE)
                        % WINDOW_SIZE;
            float difference = motionWindow[index][signal] - mean;
            squaredDifferenceSum += difference * difference;
        }

        // Matches numpy.std(..., ddof=0) used by the collector.
        float standardDeviation = sqrtf(squaredDifferenceSum / windowCount);

        int firstIndex = (windowWriteIndex - windowCount + WINDOW_SIZE)
                         % WINDOW_SIZE;
        int lastIndex = (windowWriteIndex - 1 + WINDOW_SIZE) % WINDOW_SIZE;
        float delta = motionWindow[lastIndex][signal]
                      - motionWindow[firstIndex][signal];

        int base = signal * STATS_PER_SIGNAL;
        features[base + 0] = mean;
        features[base + 1] = standardDeviation;
        features[base + 2] = minimum;
        features[base + 3] = maximum;
        features[base + 4] = delta;
    }
}

void updateMotionClassification() {
    if (windowCount < WINDOW_SIZE) {
        return;
    }

    float features[NUM_MOTION_FEATURES];
    makeMotionFeatures(features);

    int prediction = motionModel.predict(features);
    if (prediction < 0 || prediction >= 3) {
        Serial.println("Invalid YES/NO model prediction.");
        return;
    }

    const char* predictedLabel = motionLabels[prediction];
    Serial.printf("Motion prediction: %s\n", predictedLabel);

    String predicted = String(predictedLabel);

    if (predicted == "REST") {
        if (candidateMotionSign == "REST") {
            candidateCount++;
        } else {
            candidateMotionSign = "REST";
            candidateCount = 1;
        }

        if (candidateCount >= REQUIRED_STREAK) {
            activeMotionSign = "";
        }
        return;
    }

    if (predicted != "YES" && predicted != "NO") {
        return;
    }

    if (predicted == candidateMotionSign) {
        candidateCount++;
    } else {
        candidateMotionSign = predicted;
        candidateCount = 1;
    }

    if (candidateCount >= REQUIRED_STREAK) {
        activeMotionSign = predicted;
    }
}

// ========================================
// FLEX SENSOR READING
// ========================================
void readFlexSensors(float features[5]) {
    features[0] = analogRead(FLEX_THUMB);
    features[1] = analogRead(FLEX_INDEX);
    features[2] = analogRead(FLEX_MIDDLE);
    features[3] = analogRead(FLEX_RING);
    features[4] = analogRead(FLEX_PINKY);
}

// ========================================
// WEBSOCKET EVENTS
// ========================================
void onWsEvent(
    AsyncWebSocket* server,
    AsyncWebSocketClient* client,
    AwsEventType type,
    void* arg,
    uint8_t* data,
    size_t len
) {
    if (type == WS_EVT_CONNECT) {
        Serial.printf("WebSocket connected: %u\n", client->id());
    } else if (type == WS_EVT_DISCONNECT) {
        Serial.printf("WebSocket disconnected: %u\n", client->id());
    }
}

// ========================================
// WIFI
// ========================================
bool connectToWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);

    Serial.println();
    Serial.println("Connecting to phone hotspot...");

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    unsigned long startTime = millis();

    while (WiFi.status() != WL_CONNECTED &&
           millis() - startTime < 20000) {
        Serial.printf("Wi-Fi status: %d\n", (int)WiFi.status());
        delay(1000);
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("Wi-Fi connected!");
        Serial.print("ESP32 IP address: ");
        Serial.println(WiFi.localIP());
        return true;
    }

    Serial.println("Wi-Fi connection failed.");
    return false;
}

// ========================================
// WEBSITE AND WEBSOCKET SERVER
// ========================================
void startWebServer() {
    ws.onEvent(onWsEvent);
    server.addHandler(&ws);

    server.on("/", HTTP_GET,
        [](AsyncWebServerRequest* request) {
            if (LittleFS.exists("/index.html")) {
                request->send(LittleFS, "/index.html", "text/html");
            } else {
                request->send(
                    404, "text/plain",
                    "index.html not found. Upload filesystem image."
                );
            }
        }
    );

    server.serveStatic("/", LittleFS, "/");

    server.onNotFound(
        [](AsyncWebServerRequest* request) {
            request->send(404, "text/plain", "Not found");
        }
    );

    server.begin();

    Serial.println("Web server started.");
    Serial.println("Website: http://" + WiFi.localIP().toString());
    Serial.println("WebSocket: ws://" +
                   WiFi.localIP().toString() + "/ws");
}

// ========================================
// SETUP
// ========================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("SIGN GLOVE - STATIC SIGNS + MPU6050");

    analogReadResolution(12);

    analogSetPinAttenuation(FLEX_THUMB, ADC_11db);
    analogSetPinAttenuation(FLEX_INDEX, ADC_11db);
    analogSetPinAttenuation(FLEX_MIDDLE, ADC_11db);
    analogSetPinAttenuation(FLEX_RING, ADC_11db);
    analogSetPinAttenuation(FLEX_PINKY, ADC_11db);

    // Initialize I2C ONCE using the confirmed pins.
    Wire.begin(SDA_PIN, SCL_PIN);
    Wire.setClock(100000);
    delay(100);

    mpuDetected = initializeMPU();
    lastMPURetry = millis();

    if (!mpuDetected) {
        Serial.println("MPU unavailable; will retry.");
    }

    if (!LittleFS.begin(false)) {
        Serial.println("LittleFS mount failed.");
    } else {
        Serial.println("LittleFS mounted.");
    }

    if (connectToWiFi()) {
        startWebServer();
    } else {
        Serial.println("Web server unavailable without Wi-Fi.");
    }

    Serial.println();
    Serial.println("Starting sensor readings...");
}

// ========================================
// MAIN LOOP
// ========================================
// MAIN LOOP
// ========================================
void loop() {
    ws.cleanupClients();

    unsigned long now = millis();

    // Retry initialization if the MPU is not detected.
    if (!mpuDetected && now - lastMPURetry >= 2000) {
        lastMPURetry = now;
        mpuDetected = initializeMPU();
    }

    if (now - lastPredictionTime < PREDICTION_INTERVAL_MS) {
        delay(1);
        return;
    }
    lastPredictionTime = now;

    // Existing eight-class static model: five flex readings.
    float flex[5];
    readFlexSensors(flex);

    int staticPrediction = model.predict(flex);
    if (staticPrediction < 0 || staticPrediction >= NUM_CLASSES) {
        Serial.println("Invalid static model prediction.");
        return;
    }

    String finalGesture = String(gestureLabels[staticPrediction]);

    // Read MPU6050 and update the YES/NO/REST rolling window.
    float ax = 0.0f, ay = 0.0f, az = 0.0f;
    float gx = 0.0f, gy = 0.0f, gz = 0.0f;
    bool motionReadOK = false;

    if (mpuDetected) {
        motionReadOK = readMPU(ax, ay, az, gx, gy, gz);

        if (motionReadOK) {
            addMotionSample(flex[0], ax, ay, az, gx, gy, gz);
            updateMotionClassification();
        } else {
            Serial.println("MPU read failed; clearing motion window.");
            mpuDetected = false;
            windowCount = 0;
            windowWriteIndex = 0;
            candidateCount = 0;
            candidateMotionSign = "";
            activeMotionSign = "";
        }
    }

    // A stable motion sign overrides the static model.
    if (activeMotionSign == "YES" || activeMotionSign == "NO") {
        finalGesture = activeMotionSign;
    }

    // Serial diagnostics; collector parses this format.
    Serial.printf(
        "Flex T=%.0f I=%.0f M=%.0f R=%.0f P=%.0f | Sign=%s",
        flex[0], flex[1], flex[2], flex[3], flex[4],
        finalGesture.c_str()
    );

    if (motionReadOK) {
        Serial.printf(
            " | Accel X=%.2f Y=%.2f Z=%.2f m/s^2"
            " | Gyro X=%.3f Y=%.3f Z=%.3f rad/s\n",
            ax, ay, az, gx, gy, gz
        );
    } else {
        Serial.println(" | MPU: NOT DETECTED");
    }

    // Send the final sign and sensor data to the existing dashboard.
    if (WiFi.status() == WL_CONNECTED &&
        (finalGesture != lastGesture ||
         now - lastSendTime >= SEND_INTERVAL_MS)) {

        StaticJsonDocument<512> doc;
        doc["type"] = "sign";
        doc["sign"] = finalGesture;
        doc["gesture"] = finalGesture;
        doc["confidence"] = 1.0;

        doc["thumb"] = (int)flex[0];
        doc["index"] = (int)flex[1];
        doc["middle"] = (int)flex[2];
        doc["ring"] = (int)flex[3];
        doc["pinky"] = (int)flex[4];

        doc["mpu_detected"] = motionReadOK;

        if (motionReadOK) {
            doc["accel_x"] = ax;
            doc["accel_y"] = ay;
            doc["accel_z"] = az;
            doc["gyro_x"] = gx;
            doc["gyro_y"] = gy;
            doc["gyro_z"] = gz;
        }

        String message;
        serializeJson(doc, message);
        ws.textAll(message);

        lastGesture = finalGesture;
        lastSendTime = now;
    }
}
