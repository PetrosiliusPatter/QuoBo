FROM python:3.11-slim-buster

WORKDIR /bot

COPY bot/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-u", "main.py"]