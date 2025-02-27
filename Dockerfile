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
## Note: Autobuilds from BtbN get removed after 14days, except the last build of each month; those stay available for 2 years.
ARG FFMPEG_BUILD_DATETIME="2024-08-31-12-50"
ARG FFMPEG_BUILD="116806-g4c0372281b" 
RUN wget https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-${FFMPEG_BUILD_DATETIME}/ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl.tar.xz \
	&& tar xvf ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl.tar.xz \
	&& mv ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl/bin/ffmpeg /usr/local/bin/ \
	&& mv ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl/bin/ffprobe /usr/local/bin/ \
	&& rm -rf ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl*

WORKDIR /app
COPY app.py requirements.txt ./
COPY templates ./templates
COPY public ./public
COPY --from=tailwind /tailwind/public/tailwind.css ./public/tailwind.css
RUN pip install --break-system-packages gunicorn && pip install --break-system-packages -r requirements.txt

EXPOSE 8000

CMD ["gunicorn", "app:app", "--log-level", "debug", "-b", ":8000", "--preload"]
