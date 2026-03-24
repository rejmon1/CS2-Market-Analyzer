# db

Skrypty SQL dla bazy danych **PostgreSQL**.

## Zawartość
- `init.sql` — schemat bazy danych (tabele, indeksy), wykonywany automatycznie przy pierwszym uruchomieniu kontenera PostgreSQL.
- Przyszłe migracje i przykładowe dane testowe.

## Schemat (szkic)
- `items` — przedmioty CS2 (nazwa, typ, itp.)
- `prices` — historia cen pobrana z rynków (z kolumną JSONB na surowe dane API)
- `alerts` — wyniki analizy gotowe do wysłania przez bota Discord
