FROM python:3.12-slim

WORKDIR /app

# Zależności serwisu
COPY ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pakiet wspólny (shared/) dostępny jako /app/shared
COPY shared/ /app/shared/

# Kod serwisu
COPY ingestion/ /app/

CMD ["python", "main.py"]
