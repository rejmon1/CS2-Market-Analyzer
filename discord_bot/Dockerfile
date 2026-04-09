FROM python:3.12-slim

WORKDIR /app

# Zależności serwisu
COPY discord_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pakiet wspólny (shared/) dostępny jako /app/shared
COPY shared/ /app/shared/

# Kod serwisu
COPY discord_bot/ /app/

CMD ["python", "main.py"]
