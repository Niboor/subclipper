FROM debian:12.8-slim

RUN apt-get update
RUN apt-get install -y ffmpeg python3 pip git fonts-noto

WORKDIR /app
COPY app.py requirements.txt ./
RUN pip install --break-system-packages gunicorn && pip install --break-system-packages -r requirements.txt

EXPOSE 8000

CMD ["gunicorn", "app:app", "--log-level", "debug", "-b", ":8000"]
