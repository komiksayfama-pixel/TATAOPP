FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Flask'in çalışacağı port
ENV PORT=5000

CMD ["python", "bot.py"]
