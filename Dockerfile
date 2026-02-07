FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN mkdir -p /app/saves

ENV PORT=5000
ENV FLASK_DEBUG=0

EXPOSE 5000

CMD ["gunicorn", "web_app:app", "--bind", "0.0.0.0:5000", "--workers", "1"]
