FROM python:3.10-slim-bookworm

RUN apt-get update -qq && apt-get -y install ffmpeg

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
