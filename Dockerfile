FROM node:22 AS yarn
WORKDIR /yarn

COPY package.json yarn.lock tsconfig.json vite.config.ts ./
COPY src/app/static ./src/app/static
COPY src/scripts ./src/scripts
COPY src/app/templates ./src/app/templates
RUN yarn --frozen-lockfile
RUN yarn build

FROM python:3.14-slim

RUN apt-get update
RUN apt-get install -y git wget xz-utils fontconfig && rm -rf /var/lib/apt/lists/*

# Precompiled latest FFmpeg build
## Note: Autobuilds from BtbN get removed after 14days, except the last build of each month; those stay available for 2 years.
ARG FFMPEG_BUILD_DATETIME="2026-01-31-12-57"
ARG FFMPEG_BUILD="122607-g50bcc96a75"
# sha256 of ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl.tar.xz, from that release's checksums.sha256.
# Update this alongside FFMPEG_BUILD_DATETIME/FFMPEG_BUILD.
ARG FFMPEG_SHA256="44ef50b1e1bf9247025452415d162fd3354bbbaa4e5acc579dcb62bdf80c445f"
RUN wget https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-${FFMPEG_BUILD_DATETIME}/ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl.tar.xz \
	&& echo "${FFMPEG_SHA256}  ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl.tar.xz" | sha256sum -c - \
	&& tar xvf ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl.tar.xz \
	&& mv ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl/bin/ffmpeg /usr/local/bin/ \
	&& mv ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl/bin/ffprobe /usr/local/bin/ \
	&& rm -rf ffmpeg-N-${FFMPEG_BUILD}-linux64-gpl*

WORKDIR /app
COPY . .
COPY --from=yarn /yarn/src/app/static/dist ./src/app/static/dist

RUN pip install --upgrade pip
RUN pip install -e .

# Run as an unprivileged user rather than root. If SEARCH_PATH/DB_PATH/THUMBNAIL_PATH are
# bind-mounted from the host, make sure they're readable (and writable, for DB_PATH/
# THUMBNAIL_PATH) by uid 1000, or override with `docker run --user`.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser \
	&& chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
# Metrics/debug endpoints (/metrics, /debug/*), served on a separate port so
# they can be kept off the public ingress. See METRICS_PORT.
EXPOSE 9090

CMD ["gunicorn", "src.app:create_app()", "--worker-class", "gevent", "--threads", "10", "--workers", "1", "--log-level", "info", "-b", ":8000", "--limit-request-line", "0"]
