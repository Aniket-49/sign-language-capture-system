#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <LittleFS.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <ArduinoJson.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "gesture_model.h"

// ========================================
// WIFI SETTINGS
// Enter your existing hotspot credentials
// ========================================
const char* WIFI_SSID = "YOUR_HOTSPOT_NAME";
const char* WIFI_PASSWORD = "YOUR_HOTSPOT_PASSWORD";

// ========================================
// FLEX SENSOR PINS
// ========================================
#define FLEX_THUMB  34
#define FLEX_INDEX  35
#define FLEX_MIDDLE 32
#define FLEX_RING   33
#define FLEX_PINKY  36

// ========================================
// MPU6050 I2C PINS
// Based on your newer PCB wiring
// ========================================
#define MPU_SDA 2
#define MPU_SCL 15
#define MPU_ADDRESS 0x68

Adafruit_MPU6050 mpu;
bool mpuReady = false;

// ========================================
// WEB SERVER
// ========================================
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

// ========================================
// EXISTING 8-CLASS FLEX MODEL
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

// ========================================
// TIMING
// ========================================
unsigned long lastPredictionTime = 0;
unsigned long lastSendTime = 0;

const unsigned long PREDICTION_INTERVAL_MS = 100;
const unsigned long SEND_INTERVAL_MS = 300;

String lastGesture = "";

// ========================================
// READ FLEX SENSORS
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

    Serial.println("Connecting to hotspot...");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    unsigned long startTime = millis();

    while (
        WiFi.status() != WL_CONNECTED &&
        millis() - startTime < 20000
    ) {
        Serial.printf("Wi-Fi status: %d\n", (int)WiFi.status());
        delay(1000);
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("Wi-Fi connected!");
        Serial.print("ESP32 IP: ");
        Serial.println(WiFi.localIP());
        return true;
    }

    Serial.println("Wi-Fi connection failed.");
    return false;
}

// ========================================
// WEBSITE
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
                    "index.html missing. Upload LittleFS image."
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
    Serial.println("WebSocket: ws://" + WiFi.localIP().toString() + "/ws");
}

// ========================================
// SETUP
// ========================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("SIGN GLOVE - FLEX + MPU6050");

    // Flex ADC
    analogReadResolution(12);

    analogSetPinAttenuation(FLEX_THUMB, ADC_11db);
    analogSetPinAttenuation(FLEX_INDEX, ADC_11db);
    analogSetPinAttenuation(FLEX_MIDDLE, ADC_11db);
    analogSetPinAttenuation(FLEX_RING, ADC_11db);
    analogSetPinAttenuation(FLEX_PINKY, ADC_11db);

    // MPU6050 initialization
    Wire.begin(MPU_SDA, MPU_SCL);

    Serial.println("Initializing MPU6050...");

    if (mpu.begin(MPU_ADDRESS, &Wire)) {
        mpuReady = true;

        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
        mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

        Serial.println("MPU6050 detected and initialized.");
    } else {
        mpuReady = false;
        Serial.println("ERROR: MPU6050 not detected.");
        Serial.println("Check SDA, SCL, power, GND and I2C address.");
    }

    // Filesystem
    if (!LittleFS.begin(false)) {
        Serial.println("LittleFS mount failed.");
    } else {
        Serial.println("LittleFS mounted.");
    }

    // Wi-Fi and dashboard
    if (connectToWiFi()) {
        startWebServer();
    } else {
        Serial.println("Dashboard unavailable until Wi-Fi connects.");
    }
}

// ========================================
// MAIN LOOP
// ========================================
void loop() {
    ws.cleanupClients();

    unsigned long now = millis();

    if (now - lastPredictionTime < PREDICTION_INTERVAL_MS) {
        delay(1);
        return;
    }

    lastPredictionTime = now;

    // Read flex sensors and preserve existing predictions
    float features[5];
    readFlexSensors(features);

    int prediction = model.predict(features);

    if (prediction < 0 || prediction >= NUM_CLASSES) {
        Serial.println("Invalid flex-model prediction.");
        return;
    }

    const char* sign = gestureLabels[prediction];

    // Read MPU6050
    float ax = 0, ay = 0, az = 0;
    float gx = 0, gy = 0, gz = 0;

    if (mpuReady) {
        sensors_event_t accel;
        sensors_event_t gyro;
        sensors_event_t temperature;

        mpu.getEvent(&accel, &gyro, &temperature);

        ax = accel.acceleration.x;
        ay = accel.acceleration.y;
        az = accel.acceleration.z;

        gx = gyro.gyro.x;
        gy = gyro.gyro.y;
        gz = gyro.gyro.z;
    }

    // Serial output for sensor verification and future training
    Serial.printf(
        "Flex: %.0f %.0f %.0f %.0f %.0f | Sign: %s | "
        "ACC: %.2f %.2f %.2f | GYRO: %.2f %.2f %.2f\n",
        features[0], features[1], features[2],
        features[3], features[4], sign,
        ax, ay, az, gx, gy, gz
    );

    // Send flex prediction and motion readings to dashboard
    if (
        WiFi.status() == WL_CONNECTED &&
        (
            String(sign) != lastGesture ||
            now - lastSendTime >= SEND_INTERVAL_MS
        )
    ) {
        StaticJsonDocument<384> doc;

        doc["type"] = "sign";
        doc["sign"] = sign;
        doc["gesture"] = sign;

        doc["thumb"] = (int)features[0];
        doc["index"] = (int)features[1];
        doc["middle"] = (int)features[2];
        doc["ring"] = (int)features[3];
        doc["pinky"] = (int)features[4];

        doc["mpu_ready"] = mpuReady;
        doc["accel_x"] = ax;
        doc["accel_y"] = ay;
        doc["accel_z"] = az;
        doc["gyro_x"] = gx;
        doc["gyro_y"] = gy;
        doc["gyro_z"] = gz;

        String message;
        serializeJson(doc, message);
        ws.textAll(message);

        lastGesture = sign;
        lastSendTime = now;
    }
}