from flask import Blueprint, render_template, request, send_file, send_from_directory, make_response, jsonify, current_app
from pathlib import Path
import logging
from typing import Optional
import time
from contextlib import contextmanager

from ..core.models import ClipSettings
from ..utils.config import Config
from ..core.video_processor import VideoProcessor

logger = logging.getLogger(__name__)
bp = Blueprint('main', __name__)
config = Config()

@contextmanager
def log_request():
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"Request completed in {duration:.2f} seconds - {request.method} {request.path}")

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
    template = "index_with_root.html" if hx_request is None else "index.html"
    
    return cached_render_template(
        template,
        videos=videos,
        subs=subs_from_page,
        pages=sub_pages,
        show_name=config.show_name,
        sub_data=None,
        url=None
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
        return cached_render_template("index_with_root.html", sub_data=sub_data)
    else:
        return cached_render_template("tweak_modal.html", sub_data=sub_data)

@bp.route("/gif_view")
def get_gif_view():
    settings = create_clip_settings_from_request()
    
    errors = settings.validate()
    if errors:
        return cached_render_template("settings.html", errs=errors, sub=settings.__dict__), 400
        
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

@bp.route('/videos', methods=['GET'])
def get_videos():
    with log_request():
        try:
            logger.debug("Fetching list of videos")
            processor = current_app.config['VIDEO_PROCESSOR']
            videos = processor.load_videos()
            return jsonify([{
                'id': v.id,
                'title': v.title,
                'subtitle_count': len(v.subs)
            } for v in videos])
        except Exception as e:
            logger.exception("Failed to fetch videos")
            return jsonify({'error': 'Failed to fetch videos'}), 500

@bp.route('/search', methods=['GET'])
def search_subtitles():
    with log_request():
        try:
            query = request.args.get('q')
            video_id = request.args.get('video_id', type=int)
            logger.debug(f"Searching subtitles with query: {query}, video_id: {video_id}")
            
            processor = current_app.config['VIDEO_PROCESSOR']
            results = processor.search_subtitles(query, video_id)
            return jsonify([{
                'id': r.id,
                'start': r.start,
                'end': r.end,
                'text': r.text,
                'video_id': r.video_id
            } for r in results])
        except Exception as e:
            logger.exception("Failed to search subtitles")
            return jsonify({'error': 'Failed to search subtitles'}), 500

@bp.route('/generate', methods=['POST'])
def generate_clip():
    with log_request():
        try:
            data = request.get_json()
            logger.debug(f"Generating clip with settings: {data}")
            
            settings = ClipSettings(
                episode_id=data['episode_id'],
                start_time=data['start_time'],
                end_time=data['end_time'],
                text=data.get('text'),
                caption=data.get('caption'),
                crop=data.get('crop', False),
                boomerang=data.get('boomerang', False),
                resolution=data.get('resolution', '720p'),
                font_size=data.get('font_size', 24),
                colour=data.get('colour', '#FFFFFF'),
                format=data.get('format', 'mp4')
            )
            
            processor = current_app.config['VIDEO_PROCESSOR']
            output_path, error = processor.generate_clip(settings)
            
            if error:
                logger.error(f"Failed to generate clip: {error}")
                return jsonify({'error': error}), 400
                
            return jsonify({'path': str(output_path)})
        except Exception as e:
            logger.exception("Failed to generate clip")
            return jsonify({'error': 'Failed to generate clip'}), 500 