import json
import queue
import threading
from flask import Response, Blueprint, render_template, request, send_file, send_from_directory, make_response, jsonify, current_app, stream_with_context
from pathlib import Path
import logging
from typing import Generator, NamedTuple, Optional
import urllib.parse
import time
import os
from collections.abc import Callable
from itertools import chain

import flask
from jinja2 import Template

from ..core.models import ClipSettings, VideoScanStatus, Video
from ..utils.config import Config
from ..core.video_processor import VideoProcessor

logger = logging.getLogger(__name__)
bp = Blueprint('main', __name__)
config = Config()

def cached_render_template(template, **context):
    """Render a template with caching headers."""
    rendered_template = render_template(template, **context)
    response = make_response(rendered_template)
    return response

class SseEvent(NamedTuple):
    event: str
    data: str

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

def create_clip_settings_from_request() -> ClipSettings:
    """Create ClipSettings from the current request's query parameters."""
    return ClipSettings(
        start_time=request.args.get('start', 0, type=float),
        end_time=request.args.get('end', 0, type=float),
        original_start_time=request.args.get('original_start', 0, type=float),
        original_end_time=request.args.get('original_end', 0, type=float),
        text=request.args.get('text', '', type=str),
        crop=request.args.get('crop', False, type=bool),
        resolution=request.args.get('resolution', 500, type=int),
        subtitle_id=request.args.get('subtitle_id', "", type=str),
        video_id=request.args.get('video_id', '', type=str),
        font_size=request.args.get('font_size', 20, type=int),
        caption=request.args.get('caption', '', type=str),
        boomerang=request.args.get('boomerang', False, type=bool),
        colour=request.args.get('colour', False, type=bool),
        format=request.args.get('format', 'webp', type=str),
        font_path=config.font_path
    )

@bp.route("/public/<path:path>")
def get_public(path):
    """Serve static files from the static directory."""
    return send_from_directory("static", path)

@bp.route("/", defaults={'path': '.'})
@bp.route("/<path:path>")
def index(path: str):
    filter = request.args.get("filter", '', type=str)
    selected = request.args.get("selected", None, type=str)
    page = request.args.get("page", None, type=int)
    page_length = request.args.get("page_length", config.default_page_length, type=int)

    hx_request = request.headers.get("HX-Request")
    if path == "." and filter == '' and page is None:
        template = "root.html" if hx_request is None else "index.html"
        return cached_render_template(
            template,
            sub_data=None,
            url=None,
            errs=None,
        )
    else:
        page = page or 0
        subs = config.subtitle_indexer.search_subtitles((path if path != '/' else '') or '', filter)
        sub_pages = [subs[x:x+page_length] for x in range(0, len(subs), page_length)]
        subs_from_page = sub_pages[page] if sub_pages and sub_pages[page] else []

        template = "root.html" if hx_request is None else "subtitles.html"
        resp = cached_render_template(
            template,
            path=path,
            sub_data=None,
            errs=None,

            subs=subs_from_page,
            page_length=page_length,
            pages=sub_pages,
        )
        resp.headers['HX-Trigger-After-Settle'] = 'refetch-current-path'

        return resp

@bp.route("/files", defaults={'path': '.'})
@bp.route("/files/<path:path>")
def videos(path: str):
    full_path = config.subtitle_indexer.get_path(path)
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
                    logger.info(f"path {path} progress changed to {progress}. Sending over SSE stream now")

                    yield SseEvent(
                        event=str(path),
                        data=render_template(
                            "filesystem_dir_scan_status.html",
                            progress=progress,
                        )
                    )

                else:
                    video = event
                    logger.info(f"path {video.id} status changed to {video.status}. Sending over SSE stream now")

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
    path = request.args.get("path", None, type=str)

    if path is None:
        return ""
    else:
        return cached_render_template(
            'video_selection_dropdown.html',
        )

@bp.route("/locate/<subtitle_id>")
def locate(subtitle_id: str):
    page_length = request.args.get("page_length", config.default_page_length, type=int)
    subs = config.subtitle_indexer.search_subtitles('', '')
    sub_pages = [subs[x:x+page_length] for x in range(0, len(subs), page_length)]
    sub_page = [i for i, page in enumerate(sub_pages) if len([sub for sub in page if sub.id == subtitle_id]) > 0] if sub_pages else []

    if len(sub_page) == 0:
        return f"no subtitle with id {subtitle_id} found", 404
    
    resp = flask.Response("OK")
    fragment_path = f"/?page={sub_page[0]}&page_length={page_length}#id{subtitle_id}"
    resp.headers['HX-Location'] = json.dumps({"path": fragment_path, "target": "main"})
    resp.status_code = 200

    return resp
    


@bp.route("/sub_form/<path:subtitle_id>")
def get_sub(subtitle_id: str):
    sub = config.subtitle_indexer.find_subtitle(subtitle_id)
    if sub is None:
        return "Subtitle not found", 404

    sub_data = {
        'id': subtitle_id,
        'video_id': sub.video_id,
        'start_time': sub.start,
        'end_time': sub.end,
        'text': sub.text,
        'crop': False,
        'resolution': 320,
        'font_type': str(config.font_path),
        'font_size': 20,
        'caption': "",
        'colour': False,
        'boomerang': False,
    }

    hx_request = request.headers.get("HX-Request")
    if hx_request is None:
        return cached_render_template("root.html", sub_data=sub_data, videos=[])
    else:
        return cached_render_template("tweak_modal.html", sub_data=sub_data)

@bp.route("/gif_view")
def get_gif_view():
    settings = create_clip_settings_from_request()

    errors = settings.validate()
    if errors:
        resp = cached_render_template("settings.html", errs=errors, sub=settings.__dict__)
        resp.headers['HX-Reswap'] = 'outerHTML'
        return resp, 400

    return cached_render_template("gif_view.html", url=f"/gif?{request.query_string.decode()}")

@bp.route("/gif")
def get_gif():
    settings = create_clip_settings_from_request()

    output_path, error = config.video_processor.generate_clip(settings)
    if error:
        logger.warning(f"Failed to generate clip: {error}")
        return error, 500

    try:
        response = send_file(output_path, mimetype=f'image/{settings.format}')
        response.headers['Cache-Control'] = 'public, max-age=86400'
        return response
    finally:
        # Clean up the temporary directory and its contents
        if output_path and output_path.exists():
            tmp_dir = output_path.parent
            try:
                output_path.unlink()
                (tmp_dir / 'clip.mp4').unlink(missing_ok=True)
                tmp_dir.rmdir()
            except Exception as e:
                logger.warning(f"Failed to clean up temporary files: {e}")
