# Subclipper

An HTTP server that can generate GIFs on demand, based on subtitles in video files.

Inspired by https://github.com/lpalinckx/sub2clip

## Prerequisites

Before you can run Subclipper, you need to install the following dependencies:

- Python 3.12 or later
- FFmpeg (for video processing)
- Node.js and Yarn (for CSS compilation)
- Git (for installing dependencies)

### Installing Dependencies

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv ffmpeg nodejs npm git
sudo npm install -g yarn
```

#### Arch Linux
```bash
sudo pacman -S python python-virtualenv ffmpeg nodejs npm git
sudo npm install -g yarn
```

#### macOS (using Homebrew)
```bash
brew install python ffmpeg node git
npm install -g yarn
```

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/subclipper.git
cd subclipper
```

2. Set up the development environment:
```bash
make venv
source .venv/bin/activate  # or .venv/bin/activate.fish for fish shell
make install
```

3. Start the development server:
```bash
make run
```

The application will be available at http://localhost:5000

## Configuration

The application requires the following environment variables:

- `SEARCH_PATH` (required): Directory where the application will look for video files

The application also has the following optional environment variables:
- `DEFAULT_PAGE_LENGTH`: the amount of subtitles shown on each page, defaults to 50 if not set
- `SUB_LANG`: a list of ISO 639 language codes to filter subtitles based on language.
Precedence goes from left to right, if no matching subtitle is found, an error is thrown for that video file.
If left empty, the first subtitle track of each file is used instead.
- `THUMBNAIL_PATH`: directory where generated thumbnails are cached on disk, defaults to a
new temporary directory each time the app starts
- `DB_PATH`: path to the DuckDB database file used to store the subtitle index, defaults to
an in-memory database (not persisted across restarts) if not set
- `SINGLE_SHOW_NAME`: if set, the homepage skips the file browser and goes straight to this
show's subtitles
- `MAX_GIF_DURATION_SECONDS`: longest clip (in seconds) that `/gif` will generate. Defaults
to `15`
- `MAX_CONCURRENT_FFMPEG`: maximum number of ffmpeg/ffprobe subprocesses allowed to run at
once, defaults to 4. Each ffmpeg process holds its own decode buffers — a single-frame thumbnail
grab from a real 1080p episode was measured using 90-190MB RSS depending on how many decode
threads ffmpeg auto-selects. On a memory-constrained host (e.g. a container with `--memory` set),
lower this — the default of 4 can exceed a 512MB limit and get the process OOM-killed when a
burst of thumbnail requests comes in (e.g. loading a page of 50 subtitles). Lowering to 1-2
trades thumbnail-generation throughput for a much smaller peak memory footprint
- `SCAN_WORKERS`: number of videos scanned concurrently on startup, defaults to the number of
CPU cores. Actual ffmpeg/ffprobe concurrency during scanning is still capped by
`MAX_CONCURRENT_FFMPEG`
- `DISABLE_THUMBNAILS`: set to `true`/`1`/`yes`/`on` to turn off thumbnail generation entirely —
the UI won't request them and `/thumbnail` returns 404. Useful on memory-constrained hosts where
even a lowered `MAX_CONCURRENT_FFMPEG` isn't enough headroom
- `METRICS_PORT`: port for the `/metrics` (Prometheus) and `/debug/*` endpoints, served on their
own listener separate from the main application so they can be kept off the public ingress
without path-based blocking rules. Defaults to `9090`; set to `0` to disable the metrics server
entirely
- `METRICS_HOST`: interface the metrics/debug listener binds to. Defaults to `127.0.0.1` so it's
only reachable from inside the container/host by default; set to `0.0.0.0` if you specifically
want it reachable from outside and are handling access control (e.g. firewalling, a proxy) yourself
- `GIF_RATE_LIMIT_PER_MINUTE`: maximum number of `/gif` requests (clip generation, the most
expensive endpoint in the app) allowed per client IP per minute. Disabled (`0`) by default.
Note this is keyed on `request.remote_addr`, which is the app's direct TCP peer — behind a
reverse proxy that doesn't forward the real client IP, every request looks like it comes from
the proxy, so the limit effectively becomes a shared global cap rather than a per-client one

These are automatically set when using `make run`, but you can override them:

```bash
SEARCH_PATH=/path/to/videos DB_PATH="subclipper.db" make run
```

## Development

### Running Tests
```bash
make test
```

### Building Docker Image
```bash
make docker-build
make docker-run
```

### Cleaning Up
```bash
make clean
```
