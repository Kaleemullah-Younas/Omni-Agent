# ESP32 OMNI Hardware Integration Setup Guide

This guide will help you set up the complete hardware integration for your OMNI chatbot system with ESP32-S3, sensors, and audio components.

## 🔧 Hardware Components Required

1. **ESP32-S3-N16R8** - Main microcontroller
2. **GY BME280** - Temperature, humidity, and pressure sensor
3. **INMP441** - MEMS omnidirectional microphone 
4. **MAX98357** - I2S digital audio amplifier
5. **4Ohm 3W Speaker** - Audio output
6. **Jumper wires** - For connections

## 📐 Hardware Wiring Diagram

```
ESP32-S3-N16R8 Connections:
├── Audio Output (MAX98357)
│   ├── GPIO-6  → MAX98357 (LRC)
│   ├── GPIO-7  → MAX98357 (DIN)
│   └── GPIO-8  → MAX98357 (BCLK)
├── Audio Input (INMP441)
│   ├── GPIO-9  → INMP441 (WS)
│   ├── GPIO-10 → INMP441 (SCK)
│   └── GPIO-11 → INMP441 (SD)
├── Sensor (BME280)
│   ├── GPIO-17 → BME280 (SDA)
│   └── GPIO-18 → BME280 (SCL)
└── Power Distribution
    ├── 3V3 → MAX98357(VIN), MAX98357(SD), INMP441(VDD), BME280(VIN)
    └── GND → MAX98357(GND), INMP441(GND), BME280(GND)

Speaker Connection:
├── Speaker (+) → MAX98357 (+)
└── Speaker (-) → MAX98357 (-)
```

## 🚀 Software Setup

### Step 1: Arduino IDE Configuration

1. **Install Arduino IDE** (latest version)
2. **Add ESP32 Board Manager:**
   - Go to File → Preferences
   - Add to Additional Board Manager URLs:
     ```
     https://espressif.github.io/arduino-esp32/package_esp32_index.json
     ```
   - Tools → Board → Board Manager → Search "ESP32" → Install

3. **Select Board Configuration:**
   - Board: "ESP32S3 Dev Module"
   - Upload Speed: 921600
   - CPU Frequency: 240MHz (WiFi/BT)
   - Flash Mode: QIO
   - Flash Size: 16MB (128Mb)
   - Partition Scheme: 16M Flash (3MB APP/9.9MB FATFS)
   - PSRAM: OPI PSRAM

### Step 2: Install Required Libraries

Open Arduino IDE Library Manager (Tools → Manage Libraries) and install:

1. **ArduinoJson** by Benoit Blanchon
2. **Adafruit BME280 Library** by Adafruit (install all dependencies)
3. **FastLED** by Daniel Garcia
4. **Base64** by Densaugeo

### Step 3: Configure ESP32 Firmware

1. **Update WiFi Credentials** in `esp32_firmware.ino`:
   ```cpp
   const char* ssid = "YOUR_WIFI_NETWORK_NAME";
   const char* password = "YOUR_WIFI_PASSWORD";
   ```

2. **Update Server IP Address:**
   ```cpp
   const char* serverURL = "http://YOUR_COMPUTER_IP:5000";
   ```
   
   To find your computer's IP:
   - Windows: `ipconfig` in Command Prompt
   - macOS/Linux: `ifconfig` in Terminal

3. **Upload Firmware:**
   - Connect ESP32 via USB
   - Select correct COM port in Tools → Port
   - Click Upload button

### Step 4: Flask Application Setup

1. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Flask Application:**
   - Update `main.py` if needed for your specific network configuration
   - Ensure your computer firewall allows connections on port 5000

3. **Run the Application:**
   ```bash
   python main.py
   ```

## 🎯 System Features

### RGB LED Status Indicators
- **🔴 Red:** Error state or offline
- **🟢 Green:** Ready/responding state  
- **🔵 Blue:** Taking audio input
- **🟠 Amber:** Processing/thinking

### Audio Functionality
- **Hardware Microphone:** Press boot button on ESP32 or use web interface
- **Speaker Output:** Automatic TTS response through speaker
- **Web Integration:** Audio also appears in web chat interface

### Sensor Monitoring
- **Temperature:** Real-time display in web interface
- **Humidity:** Live humidity readings
- **Pressure:** Atmospheric pressure monitoring
- **Device Status:** Online/offline indicator

## 🔧 Usage Instructions

### Web Interface
1. Open browser and navigate to `http://localhost:5000`
2. Login with your credentials
3. View hardware status in left sidebar
4. Use "Hardware Mic" button to trigger ESP32 recording
5. Monitor temperature/humidity readings in real-time

### Hardware Interaction
1. **Button Recording:** Press and hold boot button on ESP32
2. **Voice Input:** Speak clearly within 2-3 feet of microphone
3. **Audio Response:** Bot replies through speaker and web interface
4. **LED Feedback:** Watch RGB LED for status updates

## 🛠️ Troubleshooting

### ESP32 Issues
- **Not Connecting to WiFi:** Check credentials and signal strength
- **Upload Errors:** Ensure correct board and port selection
- **Audio Not Working:** Verify I2S pin connections
- **Sensor Errors:** Check I2C wiring (SDA/SCL)

### Flask Application Issues
- **Hardware Not Detected:** Check IP address configuration
- **Audio Processing Errors:** Ensure internet connection for speech recognition
- **TTS Not Working:** Check pyttsx3 installation and audio drivers

### Network Issues
- **Connection Timeout:** Verify firewall settings
- **IP Changes:** Update ESP32 firmware with new IP address
- **Port Conflicts:** Ensure port 5000 is available

## 📊 API Endpoints

The system provides several API endpoints for hardware communication:

- `POST /api/hardware/heartbeat` - Device status updates
- `POST /api/hardware/audio/upload` - Audio processing
- `GET /api/hardware/commands/{device_id}` - Command queue
- `GET /api/hardware/status` - Hardware status
- `POST /api/hardware/trigger_recording/{device_id}` - Manual recording

## 🔐 Security Notes

- Change default WiFi credentials before deployment
- Consider using HTTPS for production environments
- Implement authentication for hardware endpoints if needed
- Regular firmware updates for security patches

## 📈 Performance Optimization

- **Audio Quality:** 16kHz sample rate for optimal balance
- **Network:** Use 5GHz WiFi for better performance
- **Processing:** Hardware processes audio locally before sending
- **Memory:** Efficient buffer management prevents overflow

## 🆘 Support

If you encounter issues:

1. Check serial monitor output from ESP32
2. Verify all hardware connections
3. Test individual components separately
4. Check Flask application logs
5. Ensure all dependencies are installed correctly

## 🎉 Success Indicators

You'll know everything is working when:
- ESP32 LED shows green (ready state)
- Web interface shows "ESP32 Online"
- Temperature/humidity readings appear
- Hardware mic button triggers recording
- Audio responses play through speaker
- Bot responses appear in web chat

---

**Enjoy your hardware-integrated OMNI chatbot system!** 🤖🎤🔊