from flask import Blueprint, render_template, request, send_file, send_from_directory, make_response, jsonify, current_app
from pathlib import Path
import logging
from typing import Optional

from ..core.models import ClipSettings
from ..utils.config import Config
from ..core.video_processor import VideoProcessor

logger = logging.getLogger(__name__)
bp = Blueprint('main', __name__)
config = Config()

def cached_render_template(template, **context):
    """Render a template with caching headers."""
    rendered_template = render_template(template, show_name=config.show_name, **context)
    response = make_response(rendered_template)
    return response

def create_clip_settings_from_request() -> ClipSettings:
    """Create ClipSettings from the current request's query parameters."""
    return ClipSettings(
        start_time=request.args.get('start', 0, type=float),
        end_time=request.args.get('end', 0, type=float),
        text=request.args.get('text', '', type=str),
        crop=request.args.get('crop', False, type=bool),
        resolution=request.args.get('resolution', 500, type=int),
        episode_id=request.args.get('episode', -1, type=int),
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

@bp.route("/")
def index():
    search = request.args.get("q")
    video_id = request.args.get("video", None, type=int)
    page = request.args.get("page", 0, type=int)
    page_length = request.args.get("page_length", 50, type=int)
    
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
        pages=sub_pages,
        sub_data=None,
        url=None,
        oob=hx_request is not None
    )

@bp.route("/sub_form/<video_id>/<sub_id>")
def get_sub(video_id, sub_id):
    videos = config.video_processor.load_videos()
    try:
        video = videos[int(video_id)]
    except (IndexError, ValueError):
        return "Video not found", 404
        
    try:
        sub = video.subs[int(sub_id)]
    except (IndexError, ValueError):
        return "Subtitle not found", 404
        
    sub_data = {
        'id': sub_id,
        'episode': video.id,
        'start': sub.start,
        'end': sub.end,
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
        return cached_render_template("root.html", sub_data=sub_data, videos=videos)
    else:
        return cached_render_template("tweak_modal.html", sub_data=sub_data)

@bp.route("/gif_view")
def get_gif_view():
    settings = create_clip_settings_from_request()
    
    errors = settings.validate()
    if errors:
        # Create a dict with all the current values to preserve them
        current_values = {
            'id': request.args.get('sub_id'),
            'episode': request.args.get('episode'),
            'start': request.args.get('start', type=float),
            'end': request.args.get('end', type=float),
            'text': request.args.get('text', ''),
            'crop': request.args.get('crop', False, type=bool),
            'resolution': request.args.get('resolution', 320, type=int),
            'font_size': request.args.get('font_size', 20, type=int),
            'caption': request.args.get('caption', ''),
            'boomerang': request.args.get('boomerang', False, type=bool),
            'colour': request.args.get('colour', False, type=bool),
            'format': request.args.get('format', 'webp')
        }
        return cached_render_template("settings.html", errs=errors, sub=current_values), 400
        
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
