# SearXNG Setup Guide — Windows PC
## Shadow Project • Session 7

SearXNG is a self-hosted metasearch engine. It queries Google, Bing,
DuckDuckGo, and dozens of other engines simultaneously, returning
combined results. Reaper uses it as the primary search backend.

Runs in Docker on your PC. Completely private — no search history
sent to any third party.

---

## Step 1: Enable WSL2 (Windows Subsystem for Linux)

Docker Desktop requires WSL2. Open **PowerShell as Administrator**
(right-click Start → Terminal (Admin)) and run:

```
wsl --install
```

If WSL is already installed, this will tell you. If not, it installs
Ubuntu as the default distro. **Restart your PC when prompted.**

After restart, verify:
```
wsl --version
```

You should see WSL version 2.x.x. If it says version 1, run:
```
wsl --set-default-version 2
```

---

## Step 2: Install Docker Desktop

1. Download from: https://www.docker.com/products/docker-desktop/
2. Run the installer
3. **Check "Use WSL 2 instead of Hyper-V"** during install
4. Restart if prompted
5. Open Docker Desktop — it may take a minute to start
6. Accept the terms of service
7. You do NOT need a Docker account — skip sign-in

Verify Docker is working. Open a terminal (PowerShell or CMD):
```
docker --version
docker run hello-world
```

The hello-world container should download and print a success message.

---

## Step 3: Create SearXNG Configuration

Create a folder for SearXNG's config:
```
mkdir C:\Shadow\services\searxng
```

Create the settings file. Open VS Code or Notepad and save this as
`C:\Shadow\services\searxng\settings.yml`:

```yaml
# SearXNG Settings for Shadow/Reaper
use_default_settings: true

general:
  instance_name: "Shadow Search"
  debug: false

search:
  # Enable JSON API so Reaper can query programmatically
  formats:
    - html
    - json
  
  # Default language
  default_lang: "en"
  
  # Safe search off (Shadow is an adult tool, not a family browser)
  safe_search: 0

server:
  # Secret key — change this to any random string
  secret_key: "shadow-searxng-local-key-change-me"
  
  # Bind to localhost only (not accessible from outside your PC)
  bind_address: "0.0.0.0"
  port: 8080
  
  # Limiter off for local use (it's just you, not a public server)
  limiter: false

engines:
  # Enable the best engines for Shadow's research needs
  - name: google
    engine: google
    disabled: false
  - name: bing
    engine: bing
    disabled: false
  - name: duckduckgo
    engine: duckduckgo
    disabled: false
  - name: brave
    engine: brave
    disabled: false
  - name: reddit
    engine: reddit
    disabled: false
  - name: github
    engine: github
    disabled: false
  - name: arxiv
    engine: arxiv
    disabled: false
  - name: stackoverflow
    engine: stackoverflow
    disabled: false
```

---

## Step 4: Create Docker Compose File

Save this as `C:\Shadow\services\searxng\docker-compose.yml`:

```yaml
version: '3.7'

services:
  searxng:
    image: searxng/searxng:latest
    container_name: shadow-searxng
    ports:
      - "8888:8080"
    volumes:
      - ./settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://localhost:8888/
    restart: unless-stopped
```

---

## Step 5: Start SearXNG

Open a terminal, navigate to the folder, and start it:

```
cd C:\Shadow\services\searxng
docker-compose up -d
```

The `-d` flag runs it in the background (detached mode).

First run will download the SearXNG image (~200MB). After that,
startup takes about 5 seconds.

---

## Step 6: Verify It Works

### In your browser:
Open http://localhost:8888 — you should see the SearXNG search page.
Try a search. If results come back, it's working.

### Test the JSON API (what Reaper uses):
Open this URL in your browser:
http://localhost:8888/search?q=test&format=json

You should see raw JSON with search results. This is what Reaper
will call programmatically.

### From Python (optional quick test):
```python
import requests
response = requests.get(
    "http://localhost:8888/search",
    params={"q": "RTX 5090 review", "format": "json"}
)
data = response.json()
print(f"Found {len(data.get('results', []))} results")
for r in data.get('results', [])[:3]:
    print(f"  {r['title']}")
    print(f"  {r['url']}")
```

---

## Managing SearXNG

```
# Stop SearXNG
cd C:\Shadow\services\searxng
docker-compose down

# Start SearXNG
docker-compose up -d

# View logs (if something's wrong)
docker-compose logs

# Update to latest version
docker-compose pull
docker-compose up -d

# Check if it's running
docker ps
```

SearXNG uses minimal resources: ~50-100MB RAM, negligible CPU
when idle. It's fine to leave running 24/7 on your development PC.

---

## Troubleshooting

**"Port 8888 already in use"**
Change the port in docker-compose.yml: `"9999:8080"` instead.
Then access at http://localhost:9999

**"Cannot connect to Docker daemon"**
Open Docker Desktop and make sure it's running (whale icon in taskbar).

**"JSON API returns empty results"**
Check settings.yml — make sure `json` is in the formats list.
Some engines may take a moment to warm up on first query.

**SearXNG starts but searches fail**
Some engines require occasional CAPTCHA solving. Open the HTML
interface (localhost:8888), run a search manually to clear CAPTCHAs,
then the API should work.

---

## For Shadow PC (Ubuntu) Later

Same setup but simpler — Docker comes native on Ubuntu:
```bash
sudo apt install docker.io docker-compose
cd ~/shadow/services/searxng
docker-compose up -d
```

Everything migrates cleanly. Same files, same config.
