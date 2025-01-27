# Subclipper

An HTTP server that can generate GIFs on demand, based on subtitles in video files.

Inspired by https://github.com/lpalinckx/sub2clip

## Running the application

Install Tailwind and Daisy UI (CSS packages):
```
yarn
```

Whenever making changes to the CSS, rerun the tailwind script:
```
npx @tailwindcss/cli -i public/main.css -o public/tailwind.css
```

Start a virtual environment:
```
python -m venv .
```

Source:
```
source bin/activate # if using bash
source bin/activate.fish # if using fish
# if using another shell, use the corresponding activate script
```

Install dependencies:
```
pip install -r requirements.txt
```

Run the application:
```
flask run
```
You will need to provide some environment variables however. See the [configuration section](#configuration) below


## Configuration
A number of environment variables are used to configure the application:

- SEARCH_PATH (required): directory where the application will look for episodes of the show.
- FONT: Name of the font that gets used to add subtitles to clips. Noto by default.
- SHOW_NAME: The name of the show.
