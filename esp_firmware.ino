#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <driver/i2s.h>
#include <mbedtls/base64.h>

// WiFi credentials
const char* ssid = "simple";
const char* password = "password";

// Flask server configuration
const char* serverURL = "http://10.169.96.26:5001"; // Your computer's IP address
String deviceId = "ESP32_OMNI_DEVICE";

// Hardware pin definitions
#define BME_SDA_PIN 17        // BME280 SDA
#define BME_SCL_PIN 18        // BME280 SCL
#define LED_PIN 2             // Built-in LED for status indication

// I2S Speaker pins (updated to match your working code)
#define I2S_BCLK 4            // I2S BCLK
#define I2S_LRC  5            // I2S LRC (WS)
#define I2S_DOUT 6            // I2S DOUT

#define BOOT_BUTTON_PIN 0     // Boot button for manual trigger

// BME280 sensor
Adafruit_BME280 bme;

// I2S configuration for speaker (updated to match your working code)
const i2s_config_t i2s_config_spk = {
  .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
  .sample_rate = 44100,  // Updated to match your working code
  .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
  .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
  .communication_format = I2S_COMM_FORMAT_STAND_I2S,
  .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
  .dma_buf_count = 8,    // Updated to match your working code
  .dma_buf_len = 256,    // Updated to match your working code
  .use_apll = false,
  .tx_desc_auto_clear = true,
  .fixed_mclk = 0
};

// I2S pin configuration for speaker (updated to match your working code)
const i2s_pin_config_t pin_config_spk = {
  .bck_io_num = I2S_BCLK,
  .ws_io_num = I2S_LRC,
  .data_out_num = I2S_DOUT,
  .data_in_num = I2S_PIN_NO_CHANGE
};

// Global variables
bool isPlaying = false;
float temperature = 0.0;
float humidity = 0.0;
float pressure = 0.0;
unsigned long lastSensorRead = 0;
unsigned long lastHeartbeat = 0;
const unsigned long sensorInterval = 5000;  // Read sensor every 5 seconds
const unsigned long heartbeatInterval = 10000;  // Send heartbeat every 10 seconds

// LED status colors
enum LedColor {
  LED_OFF,
  LED_BLUE,    // Listening
  LED_AMBER,   // Recording
  LED_PURPLE,  // Processing
  LED_GREEN,   // Success
  LED_RED      // Error
};

// Audio buffer for playback
const int AUDIO_BUFFER_SIZE = 4096;
int16_t audioBuffer[AUDIO_BUFFER_SIZE];

// I2S Setup function (based on your working code)
void setupI2S() {
  Serial.println("Setting up I2S...");
  
  esp_err_t result = i2s_driver_install(I2S_NUM_0, &i2s_config_spk, 0, nullptr);
  if (result != ESP_OK) {
    Serial.printf("Failed to install I2S driver: %d\n", result);
    while(1) delay(1000);
  }
  
  result = i2s_set_pin(I2S_NUM_0, &pin_config_spk);
  if (result != ESP_OK) {
    Serial.printf("Failed to set I2S pins: %d\n", result);
    while(1) delay(1000);
  }
  
  result = i2s_zero_dma_buffer(I2S_NUM_0);
  if (result != ESP_OK) {
    Serial.printf("Failed to zero DMA buffer: %d\n", result);
  }
  
  Serial.println("I2S setup completed successfully");
}

// Beep function (from your working code)
void beep(int freq, int ms) {
  const int SR = 44100;
  const int N = (SR * ms) / 1000;
  int16_t sample;
  size_t written;

  Serial.printf("Playing beep: %d Hz for %d ms\n", freq, ms);
  
  for (int i = 0; i < N; ++i) {
    sample = 15000 * sinf(2 * PI * freq * i / SR);   // Moderate volume sine wave
    int16_t stereo[2] = { sample, sample };
    i2s_write(I2S_NUM_0, stereo, sizeof(stereo), &written, portMAX_DELAY);
  }
  
  Serial.println("Beep completed");
}

// LED control function (simulated with built-in LED)
void setLED(LedColor color) {
  switch (color) {
    case LED_OFF:
      digitalWrite(LED_PIN, LOW);
      break;
    case LED_BLUE:
    case LED_AMBER:
    case LED_PURPLE:
    case LED_GREEN:
      digitalWrite(LED_PIN, HIGH);
      break;
    case LED_RED:
      // Blink for error
      for (int i = 0; i < 5; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(100);
        digitalWrite(LED_PIN, LOW);
        delay(100);
      }
      break;
  }
}

// Base64 helper functions
String base64Encode(const uint8_t* data, size_t len) {
  Serial.printf("Starting base64 encoding for %d bytes\n", len);
  Serial.printf("Free heap before encoding: %d bytes\n", ESP.getFreeHeap());
  
  size_t encodedLen = 0;
  int result = mbedtls_base64_encode(NULL, 0, &encodedLen, data, len);
  if (result != 0) {
    Serial.printf("Failed to calculate encoded length: %d\n", result);
    return "";
  }
  
  Serial.printf("Required encoded length: %d bytes\n", encodedLen);
  
  size_t requiredMemory = encodedLen + (encodedLen / 5);
  if (ESP.getFreeHeap() < requiredMemory) {
    Serial.printf("Insufficient memory: need %d, have %d\n", requiredMemory, ESP.getFreeHeap());
    return "";
  }
  
  char* encoded = (char*)malloc(encodedLen + 1);
  if (!encoded) {
    Serial.println("Failed to allocate memory for encoding");
    return "";
  }
  
  size_t actualLen = 0;
  result = mbedtls_base64_encode((unsigned char*)encoded, encodedLen, &actualLen, data, len);
  
  if (result == 0) {
    encoded[actualLen] = '\0';
    String encodedStr = String(encoded);
    free(encoded);
    Serial.printf("Base64 encoding successful: %d chars\n", encodedStr.length());
    return encodedStr;
  } else {
    Serial.printf("Base64 encoding failed with error: %d\n", result);
    free(encoded);
    return "";
  }
}

String base64Decode(const String& input) {
  size_t decodedLen = 0;
  mbedtls_base64_decode(NULL, 0, &decodedLen, (const unsigned char*)input.c_str(), input.length());
  
  uint8_t* decoded = (uint8_t*)malloc(decodedLen + 1);
  if (!decoded) return "";
  
  size_t actualLen = 0;
  int result = mbedtls_base64_decode(decoded, decodedLen, &actualLen, (const unsigned char*)input.c_str(), input.length());
  
  if (result == 0) {
    String decodedStr = "";
    for (size_t i = 0; i < actualLen; i++) {
      decodedStr += (char)decoded[i];
    }
    free(decoded);
    return decodedStr;
  }
  
  free(decoded);
  return "";
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Starting ESP32 OMNI Hardware Integration...");
  
  // Initialize LED pin
  pinMode(LED_PIN, OUTPUT);
  setLED(LED_OFF);
  
  // Initialize button pin
  pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
  
  // Initialize I2C for BME280
  Wire.begin(BME_SDA_PIN, BME_SCL_PIN);
  
  // Initialize BME280
  if (!bme.begin(0x76)) {
    Serial.println("Could not find BME280 sensor!");
    Serial.println("Check wiring or try address 0x77");
    setLED(LED_RED);
    // Continue anyway - sensor is optional
  } else {
    Serial.println("BME280 sensor initialized successfully");
  }
  
  // Initialize WiFi
  setupWiFi();
  
  // Initialize I2S for speaker using your working code
  setupI2S();
  
  // Test beep to confirm I2S is working
  Serial.println("Testing I2S with startup beep...");
  beep(1000, 200);   // 1kHz beep for 200ms
  delay(100);
  beep(1500, 200);   // 1.5kHz beep for 200ms
  
  // Send initial heartbeat
  sendHeartbeat();
  
  // Print memory information
  Serial.printf("ESP32 Memory Information:\n");
  Serial.printf("Total heap size: %d bytes\n", ESP.getHeapSize());
  Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
  Serial.printf("Min free heap: %d bytes\n", ESP.getMinFreeHeap());
  Serial.printf("Max alloc heap: %d bytes\n", ESP.getMaxAllocHeap());
  
  setLED(LED_GREEN);
  delay(1000);
  setLED(LED_OFF);
  
  Serial.println("ESP32 OMNI Hardware ready!");
  Serial.println("Device ID: " + deviceId);
  Serial.println("Server URL: " + String(serverURL));
}

void loop() {
  // Read sensors periodically
  if (millis() - lastSensorRead > sensorInterval) {
    readSensors();
    lastSensorRead = millis();
  }
  
  // Send heartbeat periodically
  if (millis() - lastHeartbeat > heartbeatInterval) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }
  
  // Check for server commands
  checkServerCommands();
  
  delay(100);
}

void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(1000);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println();
    Serial.println("Failed to connect to WiFi");
    Serial.println("Please check your WiFi credentials");
    setLED(LED_RED);
    while(1) delay(1000);
  }
}

void readSensors() {
  // Only read if BME280 is available
  if (bme.begin(0x76)) {
    temperature = bme.readTemperature();
    humidity = bme.readHumidity();
    pressure = bme.readPressure() / 100.0F; // Convert to hPa
    
    Serial.printf("Sensors -> Temp: %.2f°C, Humidity: %.2f%%, Pressure: %.2f hPa\n", 
                  temperature, humidity, pressure);
  } else {
    // Use dummy values if sensor not available
    temperature = 22.5;
    humidity = 45.0;
    pressure = 1013.25;
  }
}

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, skipping heartbeat");
    return;
  }
  
  Serial.println("Sending heartbeat to server...");
  
  HTTPClient http;
  http.begin(String(serverURL) + "/api/hardware/heartbeat");
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);
  
  StaticJsonDocument<300> doc;
  doc["device_id"] = deviceId;
  doc["status"] = "online";
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["pressure"] = pressure;
  doc["timestamp"] = millis();
  doc["wifi_rssi"] = WiFi.RSSI();
  
  String payload;
  serializeJson(doc, payload);
  
  Serial.println("Heartbeat payload: " + payload);
  
  int httpResponseCode = http.POST(payload);
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("Heartbeat sent successfully: %d\n", httpResponseCode);
    Serial.println("Server response: " + response);
  } else {
    Serial.printf("Error sending heartbeat: %d\n", httpResponseCode);
    Serial.println("HTTP error: " + http.errorToString(httpResponseCode));
  }
  
  http.end();
}

void checkServerCommands() {
  if (WiFi.status() != WL_CONNECTED) return;
  
  HTTPClient http;
  http.begin(String(serverURL) + "/api/hardware/commands/" + deviceId);
  http.setTimeout(5000);
  
  int httpResponseCode = http.GET();
  
  if (httpResponseCode == 200) {
    String response = http.getString();
    Serial.println("Received command: " + response);
    
    StaticJsonDocument<1000> doc;
    deserializeJson(doc, response);
    
    if (doc.containsKey("command")) {
      String command = doc["command"];
      
      if (command == "play_audio") {
        if (doc.containsKey("audio_data")) {
          String audioData = doc["audio_data"];
          playAudio(audioData);
        }
      } else if (command == "set_led") {
        if (doc.containsKey("color")) {
          String color = doc["color"];
          setLEDByColor(color);
        }
      } else if (command == "beep") {
        int freq = doc.containsKey("frequency") ? doc["frequency"] : 1000;
        int duration = doc.containsKey("duration") ? doc["duration"] : 200;
        beep(freq, duration);
      } else if (command == "get_sensors") {
        readSensors();
        sendHeartbeat();
      }
      
      // Acknowledge command
      if (doc.containsKey("command_id")) {
        acknowledgeCommand(doc["command_id"]);
      }
    }
  } else if (httpResponseCode != 204) {
    // 204 means no pending commands, which is normal
    Serial.printf("Error getting commands: %d\n", httpResponseCode);
  }
  
  http.end();
}

void setLEDByColor(String color) {
  if (color == "blue") {
    setLED(LED_BLUE);
  } else if (color == "amber") {
    setLED(LED_AMBER);
  } else if (color == "purple") {
    setLED(LED_PURPLE);
  } else if (color == "green") {
    setLED(LED_GREEN);
  } else if (color == "red") {
    setLED(LED_RED);
  } else {
    setLED(LED_OFF);
  }
}

void playAudio(String base64AudioData) {
  if (isPlaying) {
    Serial.println("Already playing audio, skipping");
    return;
  }
  
  Serial.println("Playing audio response...");
  isPlaying = true;
  setLED(LED_GREEN);
  
  // Play a notification beep first
  beep(800, 100);
  delay(100);
  
  // Decode base64 audio data
  String decodedAudio = base64Decode(base64AudioData);
  if (decodedAudio.length() == 0) {
    Serial.println("Failed to decode audio data");
    setLED(LED_RED);
    isPlaying = false;
    return;
  }
  
  // Get audio data as 16-bit samples
  int16_t* audioData = (int16_t*)decodedAudio.c_str();
  int sampleCount = decodedAudio.length() / sizeof(int16_t);
  
  Serial.printf("Playing %d audio samples at 44.1kHz\n", sampleCount);
  
  // Play audio through I2S
  size_t bytesWritten = 0;
  int samplesPlayed = 0;
  
  while (samplesPlayed < sampleCount) {
    int samplesToPlay = min(AUDIO_BUFFER_SIZE / 2, sampleCount - samplesPlayed);
    
    // Convert mono to stereo and play
    for (int i = 0; i < samplesToPlay; i++) {
      int16_t sample = audioData[samplesPlayed + i];
      int16_t stereo[2] = { sample, sample };
      i2s_write(I2S_NUM_0, stereo, sizeof(stereo), &bytesWritten, portMAX_DELAY);
    }
    
    samplesPlayed += samplesToPlay;
  }
  
  // Small delay to ensure audio finishes
  delay(200);
  
  // Play completion beep
  beep(1200, 100);
  
  setLED(LED_OFF);
  isPlaying = false;
  Serial.println("Audio playback completed");
}

void acknowledgeCommand(String commandId) {
  if (WiFi.status() != WL_CONNECTED) return;
  
  HTTPClient http;
  http.begin(String(serverURL) + "/api/hardware/commands/ack");
  http.addHeader("Content-Type", "application/json");
  
  StaticJsonDocument<200> doc;
  doc["device_id"] = deviceId;
  doc["command_id"] = commandId;
  doc["status"] = "completed";
  
  String payload;
  serializeJson(doc, payload);
  
  http.POST(payload);
  http.end();
  
  Serial.println("Command acknowledged: " + commandId);
} 