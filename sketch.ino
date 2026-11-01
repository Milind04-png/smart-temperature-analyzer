/*
 * ============================================================================
 * ESP32 + DHT22 Advanced Telemetry Firmware (Wokwi & Hardware Ready)
 * ============================================================================
 * Features:
 * 1. High-precision 500ms non-blocking temperature sampling (AM2302 / DHT22).
 * 2. High-speed UART Serial output: "<time_ms>,<temp_c>".
 * 3. Wokwi Virtual WiFi Auto-Connect ("Wokwi-GUEST" with zero-password).
 * 4. Dual-mode HTTP telemetry transmitter: Posts live JSON packets directly 
 *    to the Smart Temperature Analyzer Flask backend (/api/telemetry).
 * 5. Hardware diagnostics LED pulse on each successful sample and transmission.
 * ============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// ----------------------------------------------------------------------------
// Pin & Sensor Configuration
// ----------------------------------------------------------------------------
#define DHTPIN 4           // DHT22 data line connected to ESP32 GPIO 4
#define DHTTYPE DHT22      // AM2302 sensor model
#define STATUS_LED 2       // Onboard ESP32 LED (GPIO 2)

DHT dht(DHTPIN, DHTTYPE);

// ----------------------------------------------------------------------------
// WiFi & Backend Telemetry Configuration
// ----------------------------------------------------------------------------
// "Wokwi-GUEST" is the built-in virtual WiFi for Wokwi online simulation.
// For physical ESP32, replace with your local WiFi credentials.
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";

// Smart Temperature Analyzer Flask endpoint.
// In Wokwi or LAN, point to your host machine's IP (or local development proxy)
const char* SERVER_URL = "http://localhost:5000/api/telemetry";

// ----------------------------------------------------------------------------
// Non-Blocking Timing Variables
// ----------------------------------------------------------------------------
const unsigned long SENSOR_SAMPLE_INTERVAL_MS = 500;  // 500ms sampling rate
const unsigned long HTTP_POST_INTERVAL_MS = 1000;     // HTTP packet rate (1 sec)

unsigned long lastSensorSampleTime = 0;
unsigned long lastHttpPostTime = 0;

float latestTemperature = 24.5;
bool sensorHealthy = false;

// ----------------------------------------------------------------------------
// Setup
// ----------------------------------------------------------------------------
void setup() {
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);

  // Initialize high-speed UART Serial
  Serial.begin(115200);
  delay(200);
  Serial.println("\n[SYSTEM] ESP32 Smart Temperature Sensor Initializing...");

  // Initialize DHT22
  dht.begin();
  Serial.println("[SYSTEM] DHT22 Initialized on GPIO 4.");

  // Connect to WiFi
  Serial.print("[WIFI] Connecting to ");
  Serial.print(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS, 6);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(250);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Connected successfully!");
    Serial.print("[WIFI] IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WIFI] Running in Serial-only mode (No WiFi connected).");
  }

  Serial.println("[SYSTEM] Telemetry pipeline active (500ms interval).\n");
}

// ----------------------------------------------------------------------------
// Main Loop
// ----------------------------------------------------------------------------
void loop() {
  unsigned long now = millis();

  // 1. Precise 500ms Sensor Acquisition
  if (now - lastSensorSampleTime >= SENSOR_SAMPLE_INTERVAL_MS) {
    lastSensorSampleTime = now;

    float tempC = dht.readTemperature();

    if (isnan(tempC)) {
      sensorHealthy = false;
      Serial.print(now);
      Serial.println(",NAN");
    } else {
      sensorHealthy = true;
      latestTemperature = tempC;

      // Required comma-separated Serial format: "<timestamp_ms>,<temperature_c>"
      Serial.print(now);
      Serial.print(",");
      Serial.println(tempC, 1);

      // Pulse LED briefly to indicate active sample
      digitalWrite(STATUS_LED, HIGH);
      delayMicroseconds(2000);
      digitalWrite(STATUS_LED, LOW);
    }
  }

  // 2. HTTP Telemetry Push (when WiFi is available)
  if (WiFi.status() == WL_CONNECTED && (now - lastHttpPostTime >= HTTP_POST_INTERVAL_MS)) {
    lastHttpPostTime = now;

    if (sensorHealthy) {
      HTTPClient http;
      http.begin(SERVER_URL);
      http.addHeader("Content-Type", "application/json");

      // Payload JSON: {"time": <millis>, "temperature": <tempC>}
      String jsonPayload = "{\"time\":" + String(now) + ",\"temperature\":" + String(latestTemperature, 2) + "}";
      
      // Non-blocking timeout
      http.setTimeout(800);
      int httpCode = http.POST(jsonPayload);
      http.end();
    }
  }
}
