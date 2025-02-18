FROM node:22 AS tailwind
WORKDIR /tailwind

COPY package.json yarn.lock ./
COPY public/ ./public
COPY templates ./templates
RUN yarn --frozen-lockfile
RUN npx @tailwindcss/cli -i public/main.css -o public/tailwind.css

FROM debian:12.8-slim

RUN apt-get update
RUN apt-get install -y python3 pip git wget xz-utils

# Precompiled latest FFmpeg build
RUN wget https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2025-02-01-12-57/ffmpeg-N-118389-gc6194b50b1-linux64-gpl.tar.xz \
    && tar xvf ffmpeg-N-118389-gc6194b50b1-linux64-gpl.tar.xz \
    && mv ffmpeg-N-118389-gc6194b50b1-linux64-gpl/bin/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-N-118389-gc6194b50b1-linux64-gpl/bin/ffprobe /usr/local/bin/ \
    && rm -rf ffmpeg-N-118389-gc6194b50b1-linux64-gpl*

WORKDIR /app
COPY app.py requirements.txt ./
COPY templates ./templates
COPY public ./public
COPY --from=tailwind /tailwind/public/tailwind.css ./public/tailwind.css
RUN pip install --break-system-packages gunicorn && pip install --break-system-packages -r requirements.txt

EXPOSE 8000

CMD ["gunicorn", "app:app", "--log-level", "debug", "-b", ":8000", "--preload"]
