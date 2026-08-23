FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN useradd --create-home --uid 1000 mira-home
USER mira-home

EXPOSE 8423

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8423"]
