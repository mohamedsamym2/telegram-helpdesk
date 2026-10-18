# IT Support Helpdesk - Production Deployment & Client Delivery Guide

This document outlines how to deliver and deploy the **IT Support Helpdesk** system to a client or company. The system is designed to work in two deployment models:
1. **On-Premises (Windows Server / Local Office PC)**
2. **Cloud VPS Hosting (Online 24/7)**

---

## 📦 What is Included in the Client Release

1. **Standalone Windows Installer (`ITSupportHelpdesk_Setup_v2.0.exe`)**
   - Full offline bundle — **does not require Python, Node, or any external runtime installed**.
   - Runs silently in the background as a Windows service (`ITSupportHelpdesk.exe`).
   - Zero terminal windows or black command prompt popups.
   - Installs clean template database with **0 tickets, 0 messages, and blank tokens**.

2. **Clean Factory Database (`helpdesk_clean.db`)**
   - Pre-configured with 7 English Canned Quick-Reply templates.
   - Pre-configured with 5 English Knowledge Base / FAQ articles.
   - Default Administrator account: `admin` / `admin123`.
   - Ready for the client to enter their own Telegram Bot Token and IT Group ID.

3. **Cloud VPS & Docker Files (`Dockerfile`, `docker-compose.yml`)**
   - 1-command startup on any Linux Cloud VPS (`docker compose up -d`).

4. **Executive Pitch Presentation PDF (`IT_Support_Helpdesk_Proposal_Presentation.pdf`)**
   - 3-page professional executive proposal in 100% English, comparing On-Premises vs. Cloud VPS.

---

## 🚀 Deployment Option 1: On-Premises (Windows Server / Company PC)

### Requirements
- **OS**: Windows 10, 11, or Windows Server 2016/2019/2022/2025 (64-bit).
- **RAM**: Minimum 2 GB (Recommended 4 GB+).
- **Disk Space**: ~150 MB free disk space.
- **Network**: Internet connection for the Telegram Bot API (`api.telegram.org:443`).
- **Cost**: **$0 / month** (uses company's existing hardware and electricity).

### Installation Steps
1. Copy `ITSupportHelpdesk_Setup_v2.0.exe` to the server/PC.
2. Run the installer as Administrator.
3. Keep the checkbox **"Automatically start server on Windows boot (Silent background)"** checked.
4. Click **Next -> Install -> Finish**.
5. The server will start immediately in the background and open the dashboard in your default browser at:
   ```
   http://localhost:8080
   ```
   *(Or access from any device in the office network via `http://<SERVER_IP>:8080`)*

### First-Time Configuration
1. Log in with:
   - **Username**: `admin`
   - **Password**: `admin123` *(Prompted to change in Settings)*
2. The **Bot Setup Wizard** will appear automatically:
   - Paste the company's **Telegram Bot Token** (obtained from [@BotFather](https://t.me/BotFather)).
   - Paste the **IT Alert Telegram Group ID** (group where technicians receive ticket notifications).
3. Click **Save Settings**. The bot connects instantly and begins handling tickets!

---

## ☁️ Deployment Option 2: Cloud VPS Hosting (Online 24/7)

### Recommended Cloud Providers
- **Hetzner Cloud**: CX22 (~€3.79 / month)
- **DigitalOcean**: Basic Droplet (~$4 - $6 / month)
- **Linode / Akamai**: Nanode (~$5 / month)
- **Contabo**: Cloud VPS S (~$4.50 / month)

### Prerequisites
- Clean Ubuntu 22.04 LTS or 24.04 LTS VPS.
- Docker and Docker Compose installed:
  ```bash
  sudo apt update && sudo apt install -y docker.io docker-compose-v2
  ```

### Deployment Steps
1. Upload the project folder to the server:
   ```bash
   scp -r telegram-helpdesk user@<SERVER_IP>:/opt/helpdesk
   cd /opt/helpdesk
   ```
2. Start the containerized service:
   ```bash
   docker compose up -d --build
   ```
3. Open your browser and navigate to:
   ```
   http://<SERVER_IP>:8080
   ```
4. Log in (`admin` / `admin123`) and paste the Telegram Bot Token & IT Group ID.

---

## 🛠️ Management & Maintenance Commands

### On Windows:
- **Start Background Service**: Double-click `Start Server (Background)` shortcut on Desktop or `{app}\start_server.vbs`.
- **Stop Service**: Double-click `{app}\stop_server.bat` or run `taskkill /F /IM ITSupportHelpdesk.exe`.
- **Reset to Factory State**: Run `python reset_to_clean_state.py` to restore pristine state.

### On Linux (Docker):
- **View Live Logs**: `docker compose logs -f`
- **Restart Service**: `docker compose restart`
- **Stop Service**: `docker compose down`
