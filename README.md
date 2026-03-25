# 🎯 CS2 Market Radar & Arbitrage Bot

![Version](https://img.shields.io/badge/version-1.0.0%20(MVP)-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-blue)
![Docker](https://img.shields.io/badge/docker-ready-blue)

## 📖 O projekcie
**CS2 Market Analyzer** to oparty na chmurze (VPS) system analityczny służący do monitorowania rynku wirtualnych przedmiotów w grze Counter-Strike 2. Aplikacja agreguje dane z wielu niezależnych rynków zewnętrznych (m.in. Skinport, CSFloat, Steam), parsuje różnorodne formaty JSON i analizuje je.

Głównym celem systemu jest automatyczne wykrywanie różnic cenowych (**arbitraż**) oraz anomalii wolumenowych (tzw. **Pump & Dump**), a następnie natychmiastowe dostarczanie alertów inwestycyjnych za pośrednictwem dedykowanego bota na platformie Discord.

## ✨ Główne funkcjonalności (MVP)
- 🔄 **Multi-Market Ingestion:** Pobieranie i normalizacja danych z API Skinport, CSFloat oraz Steam Market.
- ⚡ **Real-time Arbitrage:** Obliczanie opłacalności zakupu i sprzedaży pomiędzy platformami (z uwzględnieniem prowizji marketów).
- 🚨 **System Powiadomień:** Błyskawiczna wysyłka alertów na wyznaczony kanał Discord.
- 📈 **Historia i Analiza:** Bezpieczne przechowywanie logów cenowych w bazie PostgreSQL do późniejszej analizy trendów.
- 🛡️ **Rate-Limit Handling:** Inteligentne zarządzanie nagłówkami (np. `Brotli`) oraz limitami zapytań (HTTP 429), aby zapobiec blokadom IP.

## 🏗️ Architektura i Tech Stack
System oparty jest na architekturze skonteneryzowanej, rozdzielającej proces pobierania danych od logiki wysyłania powiadomień.

* **Backend / Data Ingestion:** Python (biblioteki: `requests`, `aiohttp`, `brotli`)
* **Baza Danych:** PostgreSQL (wykorzystanie natywnego formatu `JSONB` dla elastyczności)
* **Infrastruktura:** VPS + Docker & Docker Compose (pełna konteneryzacja środowiska)
* **Warstwa Prezentacji:** Discord API (`discord.py`)

## 🚀 Uruchomienie projektu (Lokalnie / Dev)

### Wymagania wstępne:
* Zainstalowany **Docker** oraz **Docker Compose**
* Zainstalowany **Python 3.10+** (do testów skryptów bez użycia Dockera)

### Krok po kroku:

1. **Sklonuj repozytorium:**
    ```bash
    git clone [https://github.com/TwojaOrganizacja/cs2-market-radar.git](https://github.com/TwojaOrganizacja/cs2-market-radar.git)
    cd cs2-market-radar
    ```

2. **Skonfiguruj zmienne środowiskowe:**
   Skopiuj plik `.env.example` i zmień jego nazwę na `.env`. Uzupełnij brakujące dane (np. token bota Discord).
    ```bash
    cp .env.example .env
    ```

3. **Uruchom środowisko przez Dockera:**
   Uruchomienie kontenerów w tle (baza PostgreSQL + mikroserwisy wstaną automatycznie).
    ```bash
    docker-compose up -d --build
    ```

4. **Sprawdź logi:**
   Upewnij się, że skrypty poprawnie pobierają i rozpakowują dane (np. format Brotli ze Skinporta).
    ```bash
    docker-compose logs -f
    ```
## 👥 Zespół i Role
* **Lider / Product Owner:** [Hubert / @rejmon1] - Zarządzanie MVP i wymaganiami MoSCoW.
* **Architekt Chmury:** [Dawid / @dawbie] - Projektowanie kontenerów, Docker, infrastruktura VPS.
* **Programista Backend:** [Aleks / @whatanxx] - Skrypty Python, integracje API rynków, obsługa JSON.
* **QA / Tester:** [Radek / RakosIX] - Weryfikacja arbitrażu, testy obciążeniowe limitów API.
