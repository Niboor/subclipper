FROM node:22 AS tailwind
WORKDIR /tailwind

COPY package.json yarn.lock ./
COPY subclipper/app/static ./subclipper/app/static
COPY subclipper/app/templates ./subclipper/app/templates
RUN yarn --frozen-lockfile
RUN npx @tailwindcss/cli -i subclipper/app/static/main.css -o subclipper/app/static/tailwind.css

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
COPY . .
COPY --from=tailwind /tailwind/subclipper/app/static/tailwind.css ./subclipper/app/static/tailwind.css
RUN pip install --break-system-packages gunicorn && pip install --break-system-packages -e .

EXPOSE 8000

CMD ["gunicorn", "subclipper.app:create_app()", "--log-level", "debug", "-b", ":8000", "--preload"]
