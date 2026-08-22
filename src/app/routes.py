import json
import queue
import shutil
import threading
from flask import Response, Blueprint, render_template, request, send_file, send_from_directory, make_response, current_app, stream_with_context
from pathlib import Path
import logging
from typing import Generator, NamedTuple, Optional
import urllib.parse
import time
import os
from collections.abc import Callable
from itertools import chain
from returns.result import Failure, Success

import flask
from jinja2 import Template

from ..core.models import ClipSettings, VideoScanStatus, Video, Subtitle
from ..utils.config import Config
from ..utils.rate_limit import RateLimiter
from ..utils.pagination import paginate_window
from sub2clip.subtitles import Subtitle as SSubtitle

logger = logging.getLogger(__name__)
bp = Blueprint('main', __name__)
config = Config()

# /gif runs ffmpeg and is by far the most expensive endpoint in this app, and it
# requires no authentication — bound how often a single client can hit it.
# Disabled (0) by default, since remote_addr-based limiting isn't meaningful behind a
# proxy that doesn't forward per-client IPs; set GIF_RATE_LIMIT_PER_MINUTE to enable.
_gif_rate_limit_per_minute = int(os.getenv("GIF_RATE_LIMIT_PER_MINUTE", "0"))
_gif_rate_limiter = RateLimiter(
    max_requests=_gif_rate_limit_per_minute,
    window_seconds=60,
) if _gif_rate_limit_per_minute > 0 else None

def cached_render_template(template, **context):
    """Render a template with caching headers."""
    rendered_template = render_template(template, **context)
    response = make_response(rendered_template)
    return response

class SseEvent(NamedTuple):
    event: str
    data: str

# Items produced by the given generator are streamed over an SSE connection
def sse_event_stream(cb: Generator[SseEvent, None, None]) -> Response:
    def sse_events():
        for event_data in cb:
            yield f"event: { event_data.event }\n"
            for line in event_data.data.splitlines():
                yield f"data: {line}\n"
            yield "\n"

    return Response(
        stream_with_context(sse_events()),
        mimetype="text/event-stream",
        headers={ 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', "Transfer-Encoding": "chunked", }
    )

def create_clip_settings_from_request() -> tuple[list[Subtitle], ClipSettings]:
    """Create ClipSettings from the current request's query parameters."""
    video_id = request.args.get('video_id', '', type=str)
    if config.subtitle_indexer.get_video(video_id) is None:
        raise Exception(f"video with id {video_id} not found")

    clips: dict[str, dict[str, str]] = {}
    for key in request.args.keys():
        if key.startswith('clips['):
            import re
            match = re.match(r'clips\[(\S+)\]\[(\w+)\]', key)
            if match:
                clip_id, field = match.groups()
                if clip_id not in clips:
                    clips[clip_id] = {}
                key_at_request = request.args.get(key)
                if key_at_request is not None:
                    clips[clip_id][field] = key_at_request


    sorted_clips = dict(sorted(clips.items()))
    subs = []

    for idx, [id, clip] in enumerate(sorted_clips.items()):
        start = round(float(clip['start_time']))
        end = round(float(clip['end_time']))

        if (idx > 0):
            prv = subs[-1].end
            if prv > start:
                start = prv

        sub = config.subtitle_indexer.find_subtitle(id)
        if sub is None:
            raise Exception(f"subtitle with id {id} not found")

        sub.start = start
        sub.end = end
        sub.text = clip['text']

        subs.append(sub)

    clip_settings = ClipSettings(
        start_time=subs[0].start_s,
        end_time=subs[-1].end_s,
        original_start_time=subs[0].start_s,
        original_end_time=subs[-1].end_s,
        crop=request.args.get('crop', False, type=bool),
        resolution=request.args.get('resolution', 500, type=int),
        subtitle_id=request.args.get('sub_id', '', type=str),
        video_id=video_id,
        font_size=request.args.get('font_size', 20, type=int),
        caption=request.args.get('caption', '', type=str),
        boomerang=request.args.get('boomerang', False, type=bool),
        colour=request.args.get('colour', False, type=bool),
        format=request.args.get('format', 'webp', type=str)
    )
    return subs, clip_settings

@bp.route("/public/<path:path>")
def get_public(path):
    """Serve static files from the static directory."""
    return send_from_directory("static", path)

@bp.route("/files", defaults={'path': '.'})
@bp.route("/files/<path:path>")
def videos(path: str):
    full_path = config.subtitle_indexer.get_path(path)
    if full_path is None:
        return f"Not found: {path}", 404
    root_path = config.subtitle_indexer.get_path('.')
    progress = config.subtitle_indexer.get_scanning_progress(Path(path) if path != '.' else Path(''))
    return cached_render_template(
        'filesystem_list_item.html',
        full_path=full_path,
        root_path=root_path,
        progress=progress
    )

@bp.route("/scan_status/")
def scan_status_root():
    progress = config.subtitle_indexer.get_scanning_progress(Path('.'))
    return cached_render_template(
        'filesystem_dir_scan_status.html',
        progress=progress
    )
@bp.route("/scan_status/<path:path>")
def scan_status(path: str):
    full_path = config.subtitle_indexer.get_path(path)
    if full_path is None:
        return f"Not found: {path}", 404
    if full_path.is_file():
        video = config.subtitle_indexer.get_video(path)
        if video is None:
            return f"Not found: video on path {path}", 404
        else:
            return cached_render_template(
                'filesystem_video_scan_status.html',
                video=video
            )
    else:
        progress = config.subtitle_indexer.get_scanning_progress(Path(path))
        return cached_render_template(
            'filesystem_dir_scan_status.html',
            progress=progress
        )


@bp.route("/scan_status_sse")
def scan_status_sse():
    def sse_events():
        # Queue where events from either generator arrive.
        event_queue: queue.Queue[Video | tuple[Path, float]] = queue.Queue()

        def pump(gen):
            for item in gen:
                event_queue.put(item)

        # Start listening to BOTH generators concurrently.
        threading.Thread(
            target=pump,
            args=(config.subtitle_indexer.on_videos_status_update(),),
            daemon=True
        ).start()

        threading.Thread(
            target=pump,
            args=(config.subtitle_indexer.on_scanning_progress(),),
            daemon=True
        ).start()

        # Now yield whichever event arrives first.
        while True:
            try:
                event = event_queue.get(timeout=10)

                if isinstance(event, tuple):
                    (path, progress) = event
                    logger.debug(f"path {path} progress changed to {progress}. Sending over SSE stream now")

                    yield SseEvent(
                        event=str(path),
                        data=render_template(
                            "filesystem_dir_scan_status.html",
                            progress=progress,
                        )
                    )

                else:
                    video = event
                    logger.debug(f"path {video.id} status changed to {video.status}. Sending over SSE stream now")

                    yield SseEvent(
                        event=video.id,
                        data=render_template(
                            "filesystem_video_scan_status.html",
                            video=video,
                        )
                    )
            except queue.Empty:
                yield SseEvent(event="ping", data="")
                continue


    return sse_event_stream(sse_events())

@bp.route("/video_status_sse")
def video_status_sse():

    def sse_events():
        for video in config.subtitle_indexer.on_videos_status_update():
            yield SseEvent(
                event=str(video.id),
                data=render_template(
                    "filesystem_video_scan_status.html",
                    video=video,
                )
            )

    return sse_event_stream(sse_events())

@bp.route("/scan", methods=[ 'POST' ], defaults={'path': '.'})
@bp.route("/scan/<path:path>", methods=[ 'POST' ])
def scan(path: str):
    config.subtitle_indexer.scan(Path(path))
    return "OK"

@bp.route("/video_selection_dropdown")
def current_path():
    path = request.args.get('path', '.', type=str) or '.'
    if path == "." and config.single_show_name is None:
        # We do not want to show it on the homescreen
        return ""
    else:
        return cached_render_template(
            'video_selection_dropdown.html',
            path=path
        )

@bp.route("/locate/<subtitle_id>")
def locate(subtitle_id: str):
    page_length = request.args.get("page_length", config.default_page_length, type=int)
    # Ensure sensible page length
    if page_length is None or page_length <= 0:
        page_length = config.default_page_length

    # Compute the subtitle's 0-based index using a DB-side count and derive the page
    search_subpath = ''
    search_string = ''
    index = config.subtitle_indexer.get_subtitle_index(subtitle_id, search_subpath, search_string)
    if index is None:
        return f"no subtitle with id {subtitle_id} found", 404

    page_num = int(index) // int(page_length)

    resp = flask.Response("OK")
    fragment_path = f"/?page={page_num}&page_length={page_length}#id{subtitle_id}"
    resp.headers['HX-Location'] = json.dumps({"path": fragment_path, "target": "main"})
    resp.status_code = 200

    return resp


@bp.route("/sub_form/<path:subtitle_id>")
def sub_form(subtitle_id: str):
    sub = config.subtitle_indexer.find_subtitle(subtitle_id)
    if sub is None:
        return "Subtitle not found", 404

    sub_data = sub.to_sub_data(active=True)

    return cached_render_template(
        "tweak_modal.html",
        subs_data=[sub_data],
        settings=get_default_settings(),
        errs=None
    )

@bp.route("/sub_data/<path:subtitle_id>")
def sub_data(subtitle_id: str):
    subs, settings = create_clip_settings_from_request()

    sub_exists = any(sub.id == subtitle_id for sub in subs)

    if sub_exists:
        new_subs = subs
    else:
        new_sub = config.subtitle_indexer.find_subtitle(subtitle_id)
        if new_sub is None:
            return f"Subtitle with id {subtitle_id} not found", 404

        new_subs = [*subs, new_sub]

    new_subs.sort(key=lambda sub: sub.get_ordering())

    subs_data = [sub.to_sub_data(active=sub.id == subtitle_id) for sub in new_subs]

    return cached_render_template(
        "settings.html",
        subs_data=subs_data,
        settings=settings,
        errs=None,
    )

@bp.route("/thumbnail/<path:subtitle_id>")
def thumbnail(subtitle_id: str):
    if not config.thumbnails_enabled:
        return "Thumbnails are disabled", 404

    resolution = request.args.get("resolution", 50, type=int)

    cache_path = config.video_processor.thumbnail_path_for(subtitle_id, resolution)
    if not cache_path.exists():
        subtitle = config.subtitle_indexer.find_subtitle(subtitle_id)
        if subtitle is None:
            return f"Subtitle with id {subtitle_id} not found", 404
        match config.video_processor.get_thumbnail(subtitle, resolution=resolution):
            case Failure(err):
                return f"{err}", 500
            case Success(_):
                pass

    response = send_from_directory(cache_path.parent, cache_path.name)
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response

def get_default_settings():
    return {
        'crop': False,
        'resolution': 200,
        'font_name': str(config.font_name),
        'font_size': 20,
        'caption': "",
        'colour': False,
        'boomerang': False
    }

def get_err_settings(clip_settings: ClipSettings):
    return {
        'crop': clip_settings.crop,
        'resolution': clip_settings.resolution,
        'font_name': str(config.font_name),
        'font_size': clip_settings.font_size,
        'caption': clip_settings.caption,
        'colour': clip_settings.colour,
        'boomerang': clip_settings.boomerang,
        'format': clip_settings.format
    }

@bp.route("/gif_view")
def get_gif_view():
    subs, settings = create_clip_settings_from_request()

    errors = settings.validate()
    if errors:
        resp = cached_render_template(
            "settings.html",
            errs=errors,
            settings=get_err_settings(settings),
            subs_data=[sub.to_sub_data() for sub in subs]
        )
        resp.headers['HX-Reswap'] = 'outerHTML'
        return resp, 400

    return cached_render_template("gif_view.html", url=f"/gif?{request.query_string.decode()}")

@bp.route("/gif")
def get_gif():
    if _gif_rate_limiter is not None and not _gif_rate_limiter.allow(request.remote_addr or "unknown"):
        return "Too many clip requests, please slow down and try again shortly", 429

    subs, settings = create_clip_settings_from_request()

    output_path = config.video_processor.generate_clip(settings, subs)
    match output_path:
        case Failure(error):
            logger.warning(f"Failed to generate clip: {error}")
            return error, 500
        case Success(output_path):
            try:
                response = send_file(output_path, mimetype=f'image/{settings.format}')
                response.headers['Cache-Control'] = 'public, max-age=86400'
                return response
            finally:
                # Clean up the temporary directory and its contents
                if output_path and output_path.exists():
                    tmp_dir = output_path.parent
                    try:
                        # Use shutil.rmtree to forcefully remove directory and all contents
                        # This handles cases where sub2clip or other processes leave files
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary files: {e}")
        case _:
            raise Exception("unreachable")

@bp.route("/", defaults={'path': '.'})
@bp.route("/<path:path>")
def index(path: str):
    filter = request.args.get("filter", '', type=str)
    selected = request.args.get("selected", None, type=str)
    page = request.args.get("page", None, type=int)
    page_length = request.args.get("page_length", config.default_page_length, type=int)

    hx_request = request.headers.get("HX-Request")
    if config.single_show_name is None and path == "." and filter == '' and page is None:
        template = "root.html" if hx_request is None else "index.html"
        return cached_render_template(
            template,
            subs_data=[],
            settings=get_default_settings(),
            url=None,
            errs=None,
            single_show_name=config.single_show_name,
        )
    else:
        requested_page = page or 0
        search_subpath = (path if path != '/' else '') or ''
        pages = config.subtitle_indexer.get_subtitle_pages(search_subpath, filter, page_length)
        page = max(0, min(requested_page, pages - 1)) if pages > 0 else 0
        subs = config.subtitle_indexer.search_subtitles(search_subpath, filter, page, page_length)

        template = "root.html" if hx_request is None else "subtitles.html"
        resp = cached_render_template(
            template,
            path=path,
            subs_data=[],
            settings=get_default_settings(),
            errs=None,
            single_show_name=config.single_show_name,

            subs=subs,
            page=page,
            page_length=page_length,
            pages=pages,
            page_numbers=paginate_window(page, pages),
        )
        resp.headers['HX-Trigger-After-Settle'] = 'refetch-current-path'

        if page != requested_page:
            corrected_args = request.args.copy()
            corrected_args['page'] = str(page)
            resp.headers['HX-Replace-Url'] = f"{request.path}?{urllib.parse.urlencode(list(corrected_args.items(multi=True)))}"

        return resp

