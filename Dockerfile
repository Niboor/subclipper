FROM node:22 AS yarn
WORKDIR /yarn

COPY package.json yarn.lock tsconfig.json vite.config.ts ./
COPY subclipper/app/static ./subclipper/app/static
COPY subclipper/scripts ./subclipper/scripts
COPY subclipper/app/templates ./subclipper/app/templates
RUN yarn --frozen-lockfile
RUN yarn build

FROM python:3.14-slim

RUN apt-get update
RUN apt-get install -y git wget xz-utils fontconfig && rm -rf /var/lib/apt/lists/*

# Precompiled latest FFmpeg build
## Note: Autobuilds from BtbN get removed after 14days, except the last build of each month; those stay available for 2 years.
ARG FFMPEG_BUILD_DATETIME="2026-01-31-12-57"
ARG FFMPEG_BUILD="122607-g50bcc96a75"
RUN wget https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-${FFMPEG_BUILD_DATETIME}/ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl.tar.xz \
	&& tar xvf ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl.tar.xz \
	&& mv ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl/bin/ffmpeg /usr/local/bin/ \
	&& mv ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl/bin/ffprobe /usr/local/bin/ \
	&& rm -rf ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl*

WORKDIR /app
COPY . .
COPY --from=yarn /yarn/subclipper/app/static/dist ./subclipper/app/static/dist

RUN pip install --upgrade pip
RUN pip install gunicorn
RUN pip install -e .

EXPOSE 8000

CMD ["gunicorn", "subclipper.app:create_app()", "--log-level", "debug", "-b", ":8000", "--preload"]
