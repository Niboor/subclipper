FROM debian:12.8-slim

RUN apt-get update
RUN apt-get install -y python3 pip git wget xz-utils

# Precompiled latest FFmpeg build
RUN wget https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2025-01-15-12-55/ffmpeg-N-118315-g4f3c9f2f03-linux64-gpl.tar.xz \
    && tar xvf ffmpeg-N-118315-g4f3c9f2f03-linux64-gpl.tar.xz \
    && mv ffmpeg-N-118315-g4f3c9f2f03-linux64-gpl/bin/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-N-118315-g4f3c9f2f03-linux64-gpl/bin/ffprobe /usr/local/bin/ \
    && rm -rf ffmpeg-N-118315-g4f3c9f2f03-linux64-gpl*

WORKDIR /app
COPY app.py requirements.txt ./
COPY templates ./templates
COPY public ./public
RUN pip install --break-system-packages gunicorn && pip install --break-system-packages -r requirements.txt

EXPOSE 8000

CMD ["gunicorn", "app:app", "--log-level", "debug", "-b", ":8000", "--preload"]
