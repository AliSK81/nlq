FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY app/ app/
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
EXPOSE 8081

CMD ["python", "-m", "app.main"]
