import json
from flask import Response, Blueprint, render_template, request, send_file, send_from_directory, make_response, jsonify, current_app, stream_with_context
from pathlib import Path
import logging
from typing import Optional
import urllib.parse
import time
import os

import flask

from ..core.models import ClipSettings
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

# @bp.route("/")
# def index():
#     search = request.args.get("q") or ''
#     video_id = request.args.get("video", None, type=int)
#     page = request.args.get("page", 0, type=int)
#     page_length = request.args.get("page_length", config.default_page_length, type=int)
#     highlight = request.args.get("highlight", None, type=str)

#     subs = config.video_processor.search_subtitles('', search)
#     sub_pages = [subs[x:x+page_length] for x in range(0, len(subs), page_length)]
#     subs_from_page = sub_pages[page] if sub_pages else []

#     hx_request = request.headers.get("HX-Request")
#     template = "root.html" if hx_request is None else "subtitles.html"

#     return cached_render_template(
#         template,
#         videos=[],
#         subs=subs_from_page,
#         page_length=page_length,
#         pages=sub_pages,
#         sub_data=None,
#         url=None,
#         oob=hx_request is not None
#     )

@bp.route("/")
def index():
    path = request.args.get("path", None, type=str)
    filter = request.args.get("filter", '', type=str)
    selected = request.args.get("selected", None, type=str)
    page = request.args.get("page", 0, type=int)
    page_length = request.args.get("page_length", config.default_page_length, type=int)

    hx_request = request.headers.get("HX-Request")
    if path is None and filter == '':
        template = "root.html" if hx_request is None else "index.html"
        return cached_render_template(
            template,
            sub_data=None,
            url=None,
            errs=None,
        )
    else:
        subs = config.subtitle_indexer.search_subtitles((path if path != '/' else '') or '', filter)
        sub_pages = [subs[x:x+page_length] for x in range(0, len(subs), page_length)]
        subs_from_page = sub_pages[page] if sub_pages and sub_pages[page] else []

        template = "root.html" if hx_request is None else "subtitles.html"
        resp = cached_render_template(
            template,
            sub_data=None,
            url=None,
            errs=None,

            subs=subs_from_page,
            page_length=page_length,
            pages=sub_pages,
        )
        resp.headers['HX-Trigger-After-Settle'] = 'refetch-current-path'

        return resp

@bp.route("/files")
def videos():
    root_path = config.subtitle_indexer.get_path('')
    return cached_render_template(
        'filesystem_list_item.html',
        path=root_path,
        root=root_path
    )

@bp.route("/scanning_progress", defaults={'path': '.'})
@bp.route("/scanning_progress/<path:path>")
def scanning_progress(path: str):

    def sse_events():
        for progress in config.subtitle_indexer.get_scanning_progress(config.subtitle_indexer.get_path(path)):
            rendered_template = render_template("progress_scanning_status.html", progress=progress)
            yield "event: progress\n"
            for line in rendered_template.splitlines():
                yield f"data: {line}\n"
            yield "\n"

    return Response(
        stream_with_context(sse_events()),
        mimetype="text/event-stream",
        headers={ 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', "Transfer-Encoding": "chunked", }
    )

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
    fragment_path = f"/?path=.&page={sub_page[0]}&page_length={page_length}#id{subtitle_id}"
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
