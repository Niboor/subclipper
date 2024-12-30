# Subclipper

An HTTP server that can generate GIFs on demand, based on subtitles in video files.

Inspired by https://github.com/lpalinckx/sub2clip

## Configuration
A number of environment variables are used to configure the application:

- SEARCH_PATH (required): directory where the application will look for episodes of the show.
- FONT: Name of the font that gets used to add subtitles to clips. Noto by default.
- SHOW_NAME: The name of the show.
