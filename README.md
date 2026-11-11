# MediMate: Smart Medicine Reminder & Adherence Tracker

MediMate is an IoT-enabled smart pillbox and medication tracking system. It integrates an ESP32 microcontroller, DS3231 Real-Time Clock (RTC), roller lever limit switch, and buzzer with a local Flask web dashboard.

---

## 🚀 Quick Start Guide

### 1. Start the Flask Backend & Dashboard
Open a terminal in this directory and run:
```bash
# On Windows PowerShell
.\venv\Scripts\python app.py
```
Flask will start listening on `http://0.0.0.0:5000/`.

Open your browser and navigate to:
```
http://localhost:5000/
```
*(Note: Always use `http://localhost:5000/` to access the live dashboard connected to the database and ESP32. Do not open `index.html` directly).*

---

## 📡 ESP32 Hardware & Network Setup

### 1. Wiring Pinout
| Component | ESP32 Pin | Description |
| :--- | :--- | :--- |
| **Roller Limit Switch (COM)** | **GND** | Ground reference |
| **Roller Limit Switch (NC or NO)** | **GPIO 25** | Limit switch input (`INPUT_PULLUP`) |
| **Buzzer (+)** | **GPIO 26** | Audible alarm |
| **Buzzer (-)** | **GND** | Ground reference |
| **DS3231 RTC (SDA)** | **GPIO 21** | I2C Data line |
| **DS3231 RTC (SCL)** | **GPIO 22** | I2C Clock line |
| **DS3231 RTC (VCC)** | **3.3V or 5V** | Power supply |
| **DS3231 RTC (GND)** | **GND** | Ground reference |

### 2. Network Configuration
1. Connect your computer and your ESP32 to the **same Wi-Fi network** (a mobile phone hotspot is strongly recommended to prevent university Wi-Fi AP isolation issues).
2. Open PowerShell and find your computer's local IPv4 address:
   ```powershell
   ipconfig
   ```
3. Update `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_BASE_URL` in your `.ino` sketch:
   ```cpp
   const char* WIFI_SSID = "YOUR_HOTSPOT_NAME";
   const char* WIFI_PASSWORD = "YOUR_HOTSPOT_PASSWORD";
   const char* SERVER_BASE_URL = "http://<YOUR_LAPTOP_IP>:5000";
   ```
4. If Windows Firewall prompts you when running Flask, select **Allow Access** for Private Networks, or create an inbound rule for port 5000.

---

## 🔬 How the Limit Switch Works
* **Lid Opened during Alarm:** The buzzer silences immediately, the alarm is acknowledged, and the event `compartment_opened` is sent to the backend, updating the medicine status to **Completed**.
* **Lid Opened anytime outside Alarm:** The event `compartment_opened` is still logged to the event history on the dashboard, showing live hardware interaction.
