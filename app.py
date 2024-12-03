from flask import Flask, request, send_file
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

#handler = logging.StreamHandler(sys.stdout)
#handler.setLevel(logging.INFO)
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#handler.setFormatter(formatter)
#logger.addHandler(handler)

# TODO env vars
searchPath = "/home/nibor/eiland/"

def get_videos(path):
     return [join(path,f) for f in listdir(path) if isfile(join(path, f))]

def get_video_names(path):
     return [ f for f in listdir(path) if isfile(join(path, f))]

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

def find_request_errors(start_time, end_time, text, crop, resolution, episode):
    if end_time <= start_time:
        return 'end time must be after start time'
    if end_time - start_time > 10:
        return 'gif too long'
    if resolution < 50 or resolution > 1024:
        return 'resolution must be between 50 and 1024'
    if episode < 0 or episode > len(video_names) - 1:
        return 'invalid episode id'
    return None

def find_font(name):
    ttf = font_manager.fontManager.ttflist
    for font in ttf:
        if name in font.name:
            logger.info(f'found font at {font.fname}')
            return Path(font.fname)
    logger.error(f'could not find a suitable font for {name}')
    exit()

videos = get_videos(searchPath)
video_names = get_video_names(searchPath)

# Preload the response; it's always the same
subs = subs2json(load_subs(videos))

# Find a suitable font
font = find_font('Noto')

logger.info("ready to start the application")

@app.route("/subs")
def get_subs():
    return subs

@app.route("/gif")
def get_gif():
    start_time = request.args.get('start_time', 0, type=int)
    end_time = request.args.get('end_time', 0, type=int)
    text = request.args.get('text', '', type=str)
    crop = request.args.get('crop', False, type=bool)
    resolution = request.args.get('resolution', 500, type=int)
    episode = request.args.get('episode', -1, type=int)
    errs = find_request_errors(start_time, end_time, text, crop, resolution, episode)
    if errs is not None:
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
                video_path,
                25,
                crop,
                resolution,
                font,
                20
        )
        if ok:
            return send_file(output_gif)
        logger.warn(f"could not generate GIF: {err}")
        return err, 500
