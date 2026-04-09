FROM python:3.10-slim

WORKDIR /app

# Kopiuj wymagania i zainstaluj
COPY inventory/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiuj kod serwisu oraz kod współdzielony
COPY inventory/ inventory/
COPY shared/ shared/

# Ustaw PYTHONPATH, aby moduły były widoczne
ENV PYTHONPATH=/app

CMD ["python", "inventory/main.py"]
