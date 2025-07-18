# OMNI Agent: Multimodal AI Chatbot with Memory and Hardware Integration

## Overview

OMNI Agent is an advanced AI chatbot system that combines natural language understanding, personalized memory, relationship management, and hardware integration (ESP32 IoT device). It leverages AIML for conversational logic, Neo4j for graph-based memory, and a modular Python backend with a modern web interface.

---

## Features

- **Conversational AI**: Uses AIML files for rich, customizable dialogue.
- **Personalized Memory**: Multi-layered memory (sensory, semantic, episodic, perceptual, social) for context-aware responses.
- **Relationship Management**: Detects, stores, and reasons about user relationships using Neo4j and Prolog.
- **Hardware Integration**: Real-time communication with ESP32 for sensor data, audio input/output, and device status.
- **User Management**: Signup, login, and personalized user stats.
- **Modern Web UI**: Responsive, feature-rich interface for chat, stats, relationships, and graph visualization.
- **Logging**: Persistent chat logs for each user session.
- **Gender Prediction**: Simple gender prediction based on names.
- **Prolog Knowledge Base**: Advanced relationship and fact reasoning.

---

## Directory Structure

```
ZToday/
│
├── main.py                  # Flask app entry point
├── requirements.txt         # Python dependencies
├── relationship_manager.py  # Relationship detection and Neo4j logic
├── chat_logger.py           # Session-based chat logging
├── simple_gender_predictor.py # Name-based gender prediction
├── ntlk_dependencies.py     # NLTK data downloader
├── pos_tags_dict.py         # POS tag dictionary
│
├── memories/                # Modular memory systems
│   ├── base_memory.py
│   ├── episodic_memory.py
│   ├── memory_manager.py
│   ├── perceptual_memory.py
│   ├── semantic_memory.py
│   ├── sensory_memory.py
│   └── social_memory.py
│
├── aiml files/              # AIML knowledge base
│   ├── *.aiml
│   └── startup.xml
│
├── prolog/                  # Prolog KB for relationships/facts
│   ├── kb.pl
│   └── facts/
│
├── static/                  # Static assets (images, etc.)
│   └── images/
│
├── templates/               # HTML templates for web UI
│   ├── home.html
│   ├── login.html
│   ├── signup.html
│   ├── relationships.html
│   ├── social_memory.html
│   ├── user_stats.html
│   └── graph_visualization.html
│
├── chat_logs/               # Per-user chat logs
├── names_to_train.csv       # Name-gender training data
├── Relations_set.csv        # Relationship types
├── esp_firmware.ino         # ESP32 firmware for hardware integration
├── HARDWARE_SETUP_GUIDE.md  # Hardware setup instructions
└── OMNI AGENT.zip           # (Archive, possibly backup or distribution)
```

---

## Memory Architecture

- **Sensory Memory**: Stores raw user input, tracks user IP/location, and links to user nodes in Neo4j.
- **Semantic Memory**: Extracts word meanings, synonyms, antonyms, and domains using NLTK/WordNet.
- **Episodic Memory**: Records time-stamped user interactions, sentiment, emotion, and topics.
- **Perceptual Memory**: Analyzes input for patterns, sentiment, named entities, and sentence types.
- **Social Memory**: Manages relationships and facts using a Prolog knowledge base and integrates with Neo4j.
- **Memory Manager**: Orchestrates all memory modules for synchronous/asynchronous processing.

---

## Relationship Management

- **relationship_manager.py**: Detects, validates, and stores relationships using patterns and CSV data. Integrates with Neo4j for persistent storage and querying.
- **prolog/kb.pl**: Prolog rules and facts for advanced relationship reasoning (Western/Eastern kinship, marriages, etc.).
- **Relations_set.csv**: List of valid relationship types.

---

## Hardware Integration

- **esp_firmware.ino**: ESP32 firmware for:
  - WiFi connectivity
  - Sensor data (BME280: temperature, humidity, pressure)
  - Audio input/output (I2S, microphone, speaker)
  - LED status indicators
  - Communication with Flask backend via HTTP API

- **HARDWARE_SETUP_GUIDE.md**: Step-by-step instructions for hardware assembly, wiring, firmware upload, and troubleshooting.

---

## Web Interface

- **Modern, responsive UI** using HTML/CSS (Inter font, Bootstrap, FontAwesome).
- **Pages**:
  - `home.html`: Main chat interface with sidebar, contacts, and chat window.
  - `login.html` / `signup.html`: User authentication.
  - `user_stats.html`: Visualizes user stats, chat history, and IP/location history.
  - `relationships.html`: Displays and manages user relationships.
  - `social_memory.html`: Visualizes social graph and relationships.
  - `graph_visualization.html`: Neo4j graph visualization (vis.js).

---

## AIML Knowledge Base

- **aiml files/**: Rich set of AIML files for conversational logic, including:
  - General knowledge, jokes, food, geography, emotions, relationships, and more.
  - `startup.xml`: Loads standard AIML sets at bot startup.

---

## Logging

- **chat_logger.py**: Logs each user-bot conversation turn to per-session files in `chat_logs/`.

---

## Data & Utilities

- **names_to_train.csv**: Name-gender pairs for gender prediction.
- **simple_gender_predictor.py**: Predicts gender from names using rules and CSV data.
- **pos_tags_dict.py**: Maps Penn Treebank POS tags to descriptions.
- **ntlk_dependencies.py**: Downloads required NLTK data for NLP tasks.

---

## Setup & Installation

### 1. Python Environment

```bash
pip install -r requirements.txt
python ntlk_dependencies.py
```

### 2. Neo4j Database

- Install Neo4j Community Edition (https://neo4j.com/download/)
- Start Neo4j server (default: `bolt://localhost:7687`, user: `neo4j`, pass: `12345678`)
- No extra setup required; the app will create nodes/relationships as needed.

### 3. AIML & Prolog

- AIML files are loaded automatically at startup.
- Prolog KB (`prolog/kb.pl`) is used for relationship reasoning.

### 4. Hardware (Optional)

- See `HARDWARE_SETUP_GUIDE.md` for ESP32 setup, wiring, and firmware upload.
- Update WiFi credentials and server IP in `esp_firmware.ino` before uploading.

### 5. Running the Application

```bash
python main.py
```
- Access the web interface at [http://localhost:5000](http://localhost:5000)

---

## API Endpoints

- `POST /api/hardware/heartbeat` - Device status updates
- `POST /api/hardware/audio/upload` - Audio processing
- `GET /api/hardware/commands/{device_id}` - Command queue
- `GET /api/hardware/status` - Hardware status
- `POST /api/hardware/trigger_recording/{device_id}` - Manual recording

---

## Security Notes

- Change default Neo4j and WiFi credentials before deployment.
- Use HTTPS and authentication for production.
- Regularly update firmware and dependencies.

---

## Troubleshooting

- See `HARDWARE_SETUP_GUIDE.md` for common hardware/software issues.
- Check Flask and ESP32 serial logs for errors.
- Ensure all dependencies are installed and Neo4j is running.

---

## License

- AIML files: GNU General Public License (see comments in `ai.aiml`)
- Python code: [Specify your license here]

---

## Credits

- AIML: ALICE A.I. Foundation, Dr. Richard S. Wallace
- Python, Flask, Neo4j, NLTK, scikit-learn, vis.js, and other open-source libraries.

---

## Contact

For support, open an issue or contact the maintainer. 