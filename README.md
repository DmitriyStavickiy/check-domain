# Check Host — Batch IP Lookup

**Check Host** is a multi-threaded Python utility for performing batch IP lookups (HTTP-based) using the [ip-api.com](http://ip-api.com) service. It supports rate-limit handling, chunked processing, intermediate file writes, and optional Telegram notifications.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Linux & macOS](#linux--macos)
  - [Windows](#windows)
- [Command-Line Options](#command-line-options)
- [Logging](#logging)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Multi-threaded lookups** with configurable worker pool
- **Rate-limit compliance** (45 req/min) with header-based X-Rl and X-Ttl handling
- **Chunked processing** to control memory usage (default: 100 domains per chunk)
- **Intermediate results** written to disk to avoid large in-memory datasets
- **Configurable logging** (INFO, DEBUG levels) with thread names and timestamps
- **Optional Telegram notifications** for summary or errors

---

## Requirements

- Python **3.8** or higher
- Dependencies (see [`requirements.txt`](requirements.txt)):
  - `requests`
  - `tqdm` (optional for progress bar)
  - `python-dotenv` (optional for `.env` support)
  - `python-telegram-bot` (optional for Telegram notifications)

---

## Installation

1. **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/check-host.git
    cd check-host
    ```

2. **Create a virtual environment** (recommended):
    ```bash
    # Linux & macOS
    python3 -m venv venv
    source venv/bin/activate

    # Windows (PowerShell)
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    ```

3. **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

---

## Configuration

1. **Environment variables** (optional)

   Create a `.env` file in the project root with the following variables:
   ```dotenv
   TELEGRAM_BOT_TOKEN=<your_bot_token>
   TELEGRAM_CHAT_ID=<chat_id>
   CHUNK_SIZE=100          # domains per batch
   WORKERS=3               # number of threads
   ```

2. **Command-line arguments** override `.env` values.

---

## Usage

Process a list of domains and write results to CSV:

```bash
# Basic usage
python batch_ip_lookup.py --input domains.txt --output results.csv
```

### Linux & macOS

```bash
python3 batch_ip_lookup.py \
  --input domains.txt \
  --output results.csv \
  --workers 4 \
  --chunk-size 50
```

### Windows

```powershell
python batch_ip_lookup.py `
  --input domains.txt `
  --output results.csv `
  --workers 4 `
  --chunk-size 50
```

---

## Command-Line Options

| Option             | Description                                         | Default    |
|--------------------|-----------------------------------------------------|------------|
| `-i`, `--input`    | Path to input file (one domain per line)            | **(req.)** |
| `-o`, `--output`   | Path to output CSV file                             | **(req.)** |
| `-w`, `--workers`  | Number of parallel threads                          | `3`        |
| `-c`, `--chunk-size` | Domains per chunk for queue management            | `100`      |
| `--no-telegram`    | Disable Telegram notifications                      | _flag_     |
| `--log-level`      | Logging level (`INFO`, `DEBUG`, `WARNING`, `ERROR`) | `INFO`     |

---

## Logging

- Logs are printed to console by default.
- DEBUG logs include thread names, HTTP URLs, headers, and response bodies.
- To write logs to file, modify the `logging.basicConfig` in `batch_ip_lookup.py`:
  ```python
  logging.basicConfig(
      filename='app.log',
      filemode='a',
      format=LOG_FORMAT,
      level=LOG_LEVEL,
  )
  ```

---

## Troubleshooting

- **Rate-limit (HTTP 429)**:
  - The script checks the `X-Rl` header; if it reaches zero, it sleeps for the duration specified by `X-Ttl`.
  - Ensure your public IP isn’t shared by other heavy users.

- **Missing dependencies**:
  ```bash
  pip install requests tqdm python-dotenv python-telegram-bot
  ```

- **Module not found `tqdm`**:
  - Install via `pip install tqdm` or run without `--use-tqdm` flag.

- **Permission errors on Windows**:
  - Run PowerShell as Administrator or adjust file permissions.

---

*Happy batch processing!*

