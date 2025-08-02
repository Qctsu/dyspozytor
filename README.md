# 📦 PortDataScraper

Skrypt w Pythonie do pobierania danych z konferencji dyspozytorskiej portu Szczecin oraz planów pracy terminali. Dane zapisywane są do pliku `port_data.csv` w formacie CSV z poprawnym kodowaniem dla Excela (`utf-8-sig`).

---

## 🛠️ Wymagania

- Python 3.8 lub nowszy
- Dostęp do internetu

---

## ⚙️ Instalacja

### 1. Pobierz pliki

Upewnij się, że masz w folderze:

- `scrape_port.py` – główny skrypt
- `requirements.txt` – lista zależności

### 2. (Opcjonalnie) Utwórz wirtualne środowisko

**Windows:**

```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Zainstaluj wymagane biblioteki

```bash
pip install -r requirements.txt
```

---

## 🚀 Uruchomienie skryptu

Uruchomienie polega na wywołaniu skryptu z poziomu terminala lub CMD:

```bash
python scrape_port.py [opcjonalnie_ścieżka_do_pliku_html]
```

Skrypt automatycznie pobierze dane ze strony:

```
http://www.dyspozytor.port.szczecin.pl
```

i zapisze je do pliku `port_data.csv`.

---

## 📄 Format danych CSV

Zapisany plik zawiera dane w czytelnej strukturze, podzielone na dwie kategorie:

- **Uczestnicy konferencji** – z nazwą i statusem
- **Plan pracy terminali** – zawierający m.in. terminal, statek, towar, tonaż, relację, zmiany I/II/III

Dzięki kodowaniu `utf-8-sig` plik otwiera się poprawnie w Excelu (bez krzaczków typu `Â`, `Ĺ`, itp.).

---

## 🧠 Inteligentne działanie

- Skrypt automatycznie sprawdza, czy dane dla danej daty zostały już wcześniej zapisane, aby uniknąć duplikatów.
- Obsługuje błędy pobierania strony i nie przerywa pracy, jeśli strona jest chwilowo niedostępna.

---

## 📝 Przykład użycia

```bash
python scrape_port.py
```

Efekt: dane zostaną pobrane i zapisane (lub zaktualizowane) w pliku `port_data.csv`.

---

## 📬 Kontakt

Masz pytania, pomysły lub chcesz rozwinąć ten projekt? Śmiało napisz lub otwórz issue!