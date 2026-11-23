FROM python:3.10-slim-bookworm

RUN apt-get update -qq && apt-get -y install ffmpeg

ENV PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
