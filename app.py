from flask import Flask, render_template, request, send_file, send_from_directory, make_response
from subs.subs import (extract_subs, generate_gif)
from os import listdir
from os.path import isfile, join
from matplotlib import font_manager
from pathlib import Path
import logging
import json
import sys
import tempfile
import os
from logging.config import dictConfig
from jinja2 import Environment, FileSystemLoader
import unicodedata

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__)

logger = app.logger

def bail():
    sys.exit(4)

searchPath = os.getenv("SEARCH_PATH")
if searchPath is None:
    logger.error("search path has not been configured. set the SEARCH_PATH env var")
    bail()

showName = os.getenv("SHOW_NAME")
if showName is None:
    logger.error("show name has not been configured. set the SHOW_NAME env var")
    bail()

# get the full path of all video files in the given path
def get_videos(path):
     videos = [join(path,f) for f in listdir(path) if isfile(join(path, f))]
     videos.sort()
     return videos

# get the filenames of all video files in the given path
def get_video_names(path):
     videos = [ f for f in listdir(path) if isfile(join(path, f))]
     videos.sort()
     return videos

# We assume that episodes are in alphabetical order
# TODO check if error occurred
def load_subs(videos_list):
    return list(map(extract_subs, videos_list))

def ssa_to_dict(ssa):
    return {
            'start': ssa.start,
            'end': ssa.end,
            'text': ssa.text,
    }

def subs2json(subs):
    out = [None] * len(subs)
    for idx, sub in enumerate(subs):
        video = video_names[idx]
        logger.info(f"adding subs for {video}")
        ssa_events = sub[0]
        ssa_events_dict = list(map(ssa_to_dict, ssa_events))
        ssa_events_dict.sort(key=lambda x: x['start'])
        ep_dict = {
                'ep_name': video_names[idx],
                'ep_id': idx,
                'subs': ssa_events_dict
        }
        out[idx] = ep_dict
    return json.dumps(out)

def find_request_errors(start_time, end_time, text, crop, resolution, episode, caption, font_size):

    errs = {}

    if end_time <= start_time:
        errs['end']='end time must be after start time'
    if end_time - start_time > 10:
        errs['end']='gif too long'
    if resolution < 50 or resolution > 1024:
        errs['resolution']='resolution must be between 50 and 1024'
    if episode < 0 or episode > len(video_names) - 1:
        errs['episode']='invalid episode id'
    if len(text) > 200:
        errs['text']='subtitle text too large'
    if len(caption) > 200:
        errs['caption']='caption too large'
    if font_size > 50:
        errs['font_size']='font size too large'
    return errs

#def find_font(name):
#    ttf = font_manager.fontManager.ttflist
#    for font in ttf:
#        if name in font.name:
#            logger.info(f'found font at {font.fname}')
#            return Path(font.fname)
#    logger.error(f'could not find a suitable font for {name}')
#    bail()

def find_font():
    font = font_manager.findfont('') # I can't be bothered right now to figure out how fonts work, this just gets us a fallback font
    return Path(font)

def normalize_string(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def drop_suffix(s):
    return s.removesuffix('.mp4').removesuffix('.mkv')

def cached_render_template(template, **context):
    rendered_template = render_template(template, **context)
    response = make_response(rendered_template)
    # response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

videos = get_videos(searchPath)
video_names = get_video_names(searchPath)

# Loads the video subtitles
video_subs = load_subs(videos)
# Creates a list of video data with subtitles
videos_with_subs = [{ 'title': drop_suffix(video_names[idx]), 'id': idx, 'subs': [{ 'id': idx, 'start': sub.start, 'end': sub.end, 'text': sub.text } for idx, sub in enumerate(v[0])] } for idx, v in enumerate(video_subs)]

# Convert sub data to JSON data
subs = subs2json(video_subs)

# Find a suitable font
#font_name = os.getenv("FONT")
#if font_name is None:
#    font_name = "DejaVuSans"
font = find_font()

# Jinja2 templates
templates = Environment(loader = FileSystemLoader('templates'))

logger.info("ready to start the application")

# Serves anything stored in public folder
@app.route("/public/<path:path>")
def get_public(path):
    response = send_from_directory("public", path)
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

def get_sub_pages(search, video_id, page_length):
    subs = [{ **sub, 'video_id': video['id']} for video in videos_with_subs for sub in video['subs'] if (normalize_string(search.lower()) in normalize_string(sub['text'].lower()) if search else True) and (video_id == video['id'] if video_id is not None else True)]
    sub_pages = [subs[x:x+page_length] for x in range(0, len(subs), page_length)]
    return sub_pages

# Shows the main UI
@app.route("/")
def get_index():
    search = request.args.get("q")
    video_id = request.args.get("video", None, type=int)
    page = request.args.get("page", 0, type=int)
    page_length = request.args.get("page_length", 50, type=int)
    sub_pages = get_sub_pages(search, video_id, page_length)
    subs_from_page = sub_pages[page] if sub_pages else []

    hx_request = request.headers.get("HX-Request")
    if hx_request is None:
        return cached_render_template("index_with_root.html", videos=videos_with_subs, subs=subs_from_page, pages=sub_pages, show_name=showName, sub_data=None, url=None)
    else:
        return cached_render_template("index.html", videos=videos_with_subs, subs=subs_from_page, pages=sub_pages, show_name=showName, sub_data=None, url=None)

def get_sub_data_by_id(video_id, sub_id):
    video = [video for video in videos_with_subs if video['id'] == int(video_id)]
    if len(video) == 0:
        return "video with ID '{}' not found".format(video_id), 404

    sub = [sub for sub in video[0]['subs'] if sub['id'] == int(sub_id)]
    if len(sub) == 0:
        return "subtitle with ID '{}' in video '{}' not found".format(sub_id, video[0]['title']), 404
    sub_data = {
        'id': sub_id,
        'episode': video[0]['id'],
        'start': sub[0]['start'] / 1000,
        'end': sub[0]['end'] / 1000,
        'text': sub[0]['text'],
        'crop': False,
        'resolution': 320,
        'font_type': font.as_posix(),
        'font_size': 20,
        'caption': "",
        'colour': False,
        'crop': False,
        'boomerang': False,
    }
    return sub_data

# Creates the GIF settings that is shown at the bottom of the page
# to prevent XSS attacks, user input MUST not be shown unless sanitized
@app.route("/sub_form/<video_id>/<sub_id>")
def get_sub(video_id, sub_id):
    sub_data = get_sub_data_by_id(video_id, sub_id)
    video_id = request.args.get("video", None, type=int)

    search = request.args.get("q")
    page = request.args.get("page", 0, type=int)
    page_length = request.args.get("page_length", 50, type=int)
    sub_pages = get_sub_pages(search, video_id, page_length)
    subs_from_page = sub_pages[page] if subs else []

    hx_request = request.headers.get("HX-Request")
    if hx_request is None:
        return cached_render_template("index_with_root.html", videos=videos_with_subs, subs=subs_from_page, pages=sub_pages, show_name=showName, sub_data=sub_data, url=None)
    else:
        return cached_render_template("tweak_modal.html", sub_data=sub_data, url=None)

# Creates the GIF image when submitting the GIF settings form
@app.route("/gif_view")
def get_gif_view():
    start_time = request.args.get('start', 0, type=float)
    end_time = request.args.get('end', 0, type=float)
    text = request.args.get('text', '', type=str)
    crop = request.args.get('crop', False, type=bool)
    resolution = request.args.get('resolution', 500, type=int)
    episode = request.args.get('episode', -1, type=int)
    sub_id = request.args.get('sub_id', -1, type=int)
    font_size = request.args.get('font_size', 20, type=int)
    caption = request.args.get('caption', '', type=str)
    boomerang = request.args.get('boomerang', False, type=bool)
    colour = request.args.get('colour', False, type=bool)
    errs = find_request_errors(start_time, end_time, text, crop, resolution, episode, caption, font_size)

    if errs:
        sub_data = {
            'id': sub_id,
            'episode': episode,
            'start': start_time,
            'end': end_time,
            'text': text,
            'crop': crop,
            'resolution': resolution,
            'font_type': font.as_posix(),
            'font_size': font_size,
            'caption': caption,
            'colour': colour,
            'crop': crop,
            'boomerang': boomerang,
        }
        return cached_render_template("settings.html", errs=errs, sub=sub_data, url=None), 400
    else: return cached_render_template("gif_view.html", url="/gif?{}".format(request.query_string.decode()))

# Returns subs as JSON. This is not used in the UI
@app.route("/subs")
def get_subs():
    response = make_response(subs)
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

# Creates the GIF and returns the created binary
@app.route("/gif")
def get_gif():
    start_time = request.args.get('start', 0, type=float)
    end_time = request.args.get('end', 0, type=float)
    text = request.args.get('text', '', type=str)
    fps = 20
    crop = request.args.get('crop', False, type=bool)
    resolution = request.args.get('resolution', 500, type=int)
    episode = request.args.get('episode', -1, type=int)
    font_size = request.args.get('font_size', 20, type=int)
    caption = request.args.get('caption', '', type=str)
    boomerang = request.args.get('boomerang', False, type=bool)
    colour = request.args.get('colour', False, type=bool)
    errs = find_request_errors(start_time, end_time, text, crop, resolution, episode, caption, font_size)
    if errs:
        logger.warn(f"got invalid request: {errs}")
        return errs, 400
    with tempfile.TemporaryDirectory() as tmp:
        output_clip = os.path.join(tmp, 'clip.mp4')
        output_gif = os.path.join(tmp, 'clip.gif')
        video_path = os.path.join(searchPath, video_names[episode])
        err, ok = generate_gif(
                start_time,
                end_time,
                output_clip,
                output_gif,
                text,
                caption,
                video_path,
                fps,
                crop,
                boomerang,
                resolution,
                font,
                font_size,
                colour,
        )
        if ok:
            response = send_file(output_gif, mimetype='image/gif')
            response.headers['Cache-Control'] = 'public, max-age=86400'
            return response
        logger.warn(f"could not generate GIF: {err}")
        return err, 500
