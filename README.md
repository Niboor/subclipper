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
- `SHOW_NAME`: Name of the show (defaults to "Subclipper Test")

These are automatically set when using `make run`, but you can override them:

```bash
SEARCH_PATH=/path/to/videos SHOW_NAME="My Show" make run
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
