import json
from flask import Response, Blueprint, render_template, request, send_file, send_from_directory, make_response, jsonify, current_app
from pathlib import Path
import logging
from typing import Optional

import flask

from ..core.models import ClipSettings
from ..utils.config import Config
from ..core.video_processor import VideoProcessor
from sub2clip.subtitles import Subtitle

logger = logging.getLogger(__name__)
bp = Blueprint('main', __name__)
config = Config()

def cached_render_template(template, **context):
    """Render a template with caching headers."""
    rendered_template = render_template(template, show_name=config.show_name, **context)
    response = make_response(rendered_template)
    return response

def create_clip_settings_from_request() -> [list[Subtitle], ClipSettings]:
    """Create ClipSettings from the current request's query parameters."""

    clips = {}
    for key in request.args.keys():
        if key.startswith('clips['):
            import re
            match = re.match(r'clips\[(\d+)\]\[(\w+)\]', key)
            if match:
                clip_id, field = match.groups()
                if clip_id not in clips:
                    clips[clip_id] = {}
                clips[clip_id][field] = request.args.get(key)


    sorted_clips = dict(sorted(clips.items()))
    subs = []

    for idx, clip in enumerate(sorted_clips.values()):
        start = float(clip['start_time']) * 1000
        end = float(clip['end_time']) * 1000
        if (idx > 0):
            prv = subs[-1].end
            if prv > start:
                start = prv

        subs.append(Subtitle(
            start=start,
            end=end,
            text=[line for line in clip['text'].split('\n')]
        ))

    clip_settings = ClipSettings(
        start_time=subs[0].start_s,
        end_time=subs[-1].end_s,
        original_start_time=subs[0].start_s,
        original_end_time=subs[-1].end_s,
        crop=request.args.get('crop', False, type=bool),
        resolution=request.args.get('resolution', 500, type=int),
        id=request.args.get('sub_id', -1, type=int),
        episode=int(clip['episode']),
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

@bp.route("/")
def index():
    search = request.args.get("q")
    video_id = request.args.get("video", None, type=int)
    page = request.args.get("page", 0, type=int)
    page_length = request.args.get("page_length", config.default_page_length, type=int)
    highlight = request.args.get("highlight", None, type=str)

    videos = config.video_processor.load_videos()
    subs = config.video_processor.search_subtitles(search, video_id)
    sub_pages = [subs[x:x+page_length] for x in range(0, len(subs), page_length)]
    subs_from_page = sub_pages[page] if sub_pages else []

    hx_request = request.headers.get("HX-Request")
    template = "root.html" if hx_request is None else "subtitles.html"

    return cached_render_template(
        template,
        videos=videos,
        subs=subs_from_page,
        page_length=page_length,
        pages=sub_pages,
        sub_data=None,
        url=None,
        oob=hx_request is not None
    )

@bp.route("/locate/<video_id>/<sub_id>")
def locate(video_id: str, sub_id: str):
    video_id = int(video_id)
    sub_id = int(sub_id)
    page_length = request.args.get("page_length", config.default_page_length, type=int)
    subs = config.video_processor.search_subtitles(None, None)
    sub_pages = [subs[x:x+page_length] for x in range(0, len(subs), page_length)]
    sub_page = [i for i, page in enumerate(sub_pages) if len([sub for sub in page if sub.id == sub_id and sub.video_id == video_id]) > 0] if sub_pages else []

    if len(sub_page) == 0:
        return f"no subtitle with id {sub_id} from video with id {video_id} found", 404

    resp = flask.Response("OK")
    fragment_path = f"/?page={sub_page[0]}&page_length={page_length}#e{video_id}-s{sub_id}"
    resp.headers['HX-Location'] = json.dumps({"path": fragment_path, "target": "main"})
    resp.status_code = 200

    return resp


def sub(video_id, sub_id):
    videos = config.video_processor.load_videos()
    try:
        video = videos[int(video_id)]
    except (IndexError, ValueError):
        return "Video not found", 404

    try:
        sub = video.subs[int(sub_id)]
    except (IndexError, ValueError):
        return "Subtitle not found", 404

    prv = int(sub_id) - 1 if sub.prv else None
    nxt = int(sub_id) + 1 if sub.nxt else None

    return {
        'id': sub_id,
        'episode': video.id,
        'start_time': sub.start_s,
        'end_time': sub.end_s,
        'text': sub.text,
        'prv': prv,
        'nxt': nxt
    }

@bp.route("/sub_form/<video_id>/<sub_id>")
def temp(video_id, sub_id):
    videos = config.video_processor.load_videos()
    sub_data = sub(video_id, sub_id)
    hx_request = request.headers.get("HX-Request")
    if hx_request is None:
        return cached_render_template("root.html", sub_data=sub_data, videos=videos)
    else:
        return cached_render_template("tweak_modal.html", sub_data=sub_data, errs=None)

@bp.route("/sub_data/<video_id>/<sub_id>")
def get_sub(video_id, sub_id):
    videos = config.video_processor.load_videos()
    sub_data = sub(video_id, sub_id)

    hx_request = request.headers.get("HX-Request")
    if hx_request is None:
        return cached_render_template("root.html", sub_data=sub_data, videos=videos)
    else:
        return cached_render_template("clip_settings.html", sub=sub_data, errs=None)

@bp.route("/default_settings")
def get_default_settings():
    settings = {
        'crop': False,
        'resolution': 200,
        'font_name': str(config.font_name),
        'font_size': 25,
        'caption': "",
        'colour': False,
        'boomerang': False
    }

    return cached_render_template("global_settings.html", settings=settings)


@bp.route("/gif_view")
def get_gif_view():
    subs, settings = create_clip_settings_from_request()

    errors = settings.validate()
    if errors:
        resp = cached_render_template("settings.html", errs=errors, sub=settings.__dict__)
        resp.headers['HX-Reswap'] = 'outerHTML'
        return resp, 400

    return cached_render_template("gif_view.html", url=f"/gif?{request.query_string.decode()}")

@bp.route("/gif")
def get_gif():
    subs, settings = create_clip_settings_from_request()

    output_path, error = config.video_processor.generate_clip(settings, subs)
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
