# Image Generation API

This project is a self-hosted, AI-powered image generation service. It uses DeepSeek for prompt engineering, Replicate (Flux) for image generation, and `rembg` for local background removal.

## Features

- **Python & Venv:** Runs in a standard Python virtual environment.
- **No Timeouts:** Performs background removal locally using `rembg`, bypassing serverless function limits.
- **Configurable Prompts:** Customize the AI persona and fallback prompts via environment variables.
- **Auto-Deploy:** GitHub Actions workflow for automatic deployment to self-hosted runners.

## Requirements (Server / VPS)

Since we are not using Docker, ensure the following are installed on your server (e.g., Ubuntu/Debian):

```bash
# Python and venv
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv

# System libraries for Rembg/OpenCV
sudo apt-get install libgl1-mesa-glx libglib2.0-0
```

## Installation (Local Development)

1.  Clone the repository.
2.  Rename `.env.example` to `.env` and fill in your API keys.
3.  Create a virtual environment and install dependencies:

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate
pip install -r app/requirements.txt

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
pip install -r app/requirements.txt
```

4.  Start the application:

```bash
# The app will read the PORT from .env or default to 8000
uvicorn app.main:app --reload --host 0.0.0.0 --port ${PORT:-8000}
```

## Running as a Service (Systemd)

To ensure the application runs continuously and restarts on boot:

1.  Create a service file at `/etc/systemd/system/image-gen-api.service`:

```ini
[Unit]
Description=Image Generation API Service
After=network.target

[Service]
User=root
WorkingDirectory=/home/youruser/image-generation-api
EnvironmentFile=/home/youruser/image-generation-api/.env
ExecStart=/bin/bash -c 'source /home/youruser/image-generation-api/venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port $PORT'
Restart=always

[Install]
WantedBy=multi-user.target
```

2.  Enable and start the service:

```bash
sudo systemctl enable image-gen-api
sudo systemctl start image-gen-api
```

## API Usage

**GET** `/api/generate?w=Hamburger&bgstyle=transparent`

### Parameters

- `w`: **(Required)** Product name (e.g., "Double Cheeseburger").
- `bgstyle`: **(Optional)** Defines the background style. Default: `transparent`.
    - `transparent`: Removes background, returns transparent WebP.
    - `#RRGGBB`: Removes background, fills with specific Hex color (e.g., `#FF0000`).
    - `solid`: AI generates a studio-like image with a solid/neutral background (No removal).
    - `image`: AI generates a natural/lifestyle scene (No removal).

### Examples

1.  **Transparent (Default):**
    `/api/generate?w=Pizza`
2.  **Red Background:**
    `/api/generate?w=Pizza&bgstyle=%23FF0000`
3.  **AI Studio Look:**
    `/api/generate?w=Pizza&bgstyle=solid`
4.  **Natural Scene:**
    `/api/generate?w=Pizza&bgstyle=image`

**Output:** Always returns a `WEBP` image.
