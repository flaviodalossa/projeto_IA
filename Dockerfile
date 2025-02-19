FROM python:3.12-slim-bullseye

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

ENV FLASK_APP=app.py
ENV GOOGLE_APPLICATION_CREDENTIALS=/secrets/service_account_key.json

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
