# System Bezpieczeństwa Wizyjnego dla Cobota UR3 (CB3)

Niniejszy projekt to zaawansowany system bezpieczeństwa czasu rzeczywistego (Speed and Separation Monitoring) dedykowany dla robota współpracującego **Universal Robots UR3 (generacja CB3)**. System integruje detekcję obiektów (ludzi) przy użyciu modelu **YOLOv8** ze sterowaniem prędkością robota w czasie rzeczywistym poprzez protokół **RTDE** (Real-Time Data Exchange) oraz asynchronicznym rejestrowaniem zdarzeń.

---

## 1. Struktura Katalogów Projektu

Katalog główny został zoptymalizowany i podzielony na moduły tematyczne:

```
VisionSystem_UR3/
│
├── db/                           # Moduły zapisu danych i analizy statystycznej
│   ├── event_logger.py           # Asynchroniczny zapis logów do Excela (.xlsx)
│   ├── mysql_logger.py           # Asynchroniczny zapis logów do bazy MySQL
│   ├── latency_profiler.py       # Pomiar czasu reakcji i opóźnień (YOLO, CPU, RTDE)
│   └── logs_detection_ur3/       # Folder przechowujący zrzuty ekranu naruszeń (.jpg)
│
├── camera_gui/                   # Pakiety wizyjne, sterowanie strefami i interfejs HUD
│   ├── camera_utils.py           # Asynchroniczny odczyt klatek, helpery geometryczne stref
│   ├── gui_hud.py                # Zaawansowany, półprzezroczysty dashboard wideo (HUD)
│   ├── zone_config.py            # Narzędzie graficzne do definiowania stref (Zielona, Żółta, Czerwona)
│   └── console_logger.py         # Przechwytywanie konsoli i zrzucanie logów z czasem do pliku
│
├── .env                          # Plik ze zmiennymi środowiskowymi (hasła, adresy IP)
├── config.py                     # Centralny plik konfiguracyjny (prędkości, progi czasowe, tryby)
├── main.py                       # Główny plik uruchomieniowy systemu (pętla decyzyjna)
├── zones.json                    # Współrzędne narysowanych stref bezpieczeństwa
├── terminal_logs.txt             # Automatyczny log komunikatów terminala z sygnaturami czasowymi
├── yolov8n.pt                    # Plik wag sieci neuronowej YOLOv8 (wersja nano)
└── venv/                         # Środowisko wirtualne Pythona (.gitignore)
```

---

## 2. Opis Plików i Modułów

### A. Pliki Główne (Root)
*   **[main.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/main.py)**: Serce systemu. Inicjalizuje połączenie z robotem i kamerą, ładuje model YOLO, a w głównej pętli analizuje obraz, zarządza histerezą prędkości, synchronizuje ID sesji i steruje wywołaniami logerów.
*   **[config.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/config.py)**: Centralna konfiguracja. Zawiera definicje prędkości dla poszczególnych stref (Zielona: 50%, Żółta: 25%, Czerwona: 10%), czas podtrzymania histerezy (`HYSTERESIS_TIME_S = 0.8`), progi minimalnego czasu detekcji (`MIN_DETECTION_TIME_S = 0.5`) oraz dane połączeniowe bazy danych.
*   **[.env](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/.env)**: Przechowuje poufne dane (IP robota, hasło do bazy danych MySQL, tryb online/offline).

### B. Moduły Wizyjne i GUI (`camera_gui/`)
*   **[camera_utils.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/camera_gui/camera_utils.py)**:
    *   `ThreadedCamera`: Uruchamia osobny wątek pobierania klatek z kamery, odrzucając starszy bufor OpenCV. Gwarantuje to przetwarzanie obrazu bez opóźnień decyzyjnych.
    *   Funkcje geometryczne: Sprawdzają nachodzenie dwojakiego rodzaju (pełen prostokąt detekcji lub punkt stóp operatora) na strefy bezpieczeństwa.
*   **[gui_hud.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/camera_gui/gui_hud.py)**: Rysuje na obrazie nowoczesny interfejs (dashboard) z efektem szklanego panelu (Glassmorphism). Wyświetla boks statusu bezpieczeństwa (`SAFE`, `ZONE (G)`, `ZONE (Y)`, `ZONE (R)` lub `HOLD`), parametry FPS/YOLO oraz graficzny pasek postępu (Progress Bar) prędkości robota. Wszystkie style można edytować w słowniku `HUD_STYLE`.
*   **[zone_config.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/camera_gui/zone_config.py)**: Interaktywny konfigurator stref. Pozwala użytkownikowi narysować myszką prostokąty stref i zapisać je do pliku `zones.json`.
*   **[console_logger.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/camera_gui/console_logger.py)**: Automatycznie przekierowuje wyjście terminala i błędy do pliku tekstowego `terminal_logs.txt`, dodając przed każdą linijką czas zdarzenia.

### C. Logery i Statystyki (`db/`)
*   **[event_logger.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/db/event_logger.py)**: Obsługuje asynchroniczny zapis logów naruszeń do arkusza Excel (`logs_detection_ur3.xlsx`) oraz natychmiastowe zrzuty klatek w locie do folderu `logs_detection_ur3/`. W razie zablokowania arkusza przez użytkownika, zapisuje rekordy do cache lokalnego (`logs_detection_ur3.xlsx.cache`).
*   **[mysql_logger.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/db/mysql_logger.py)**: Asynchronicznie zapisuje dane naruszeń do tabeli `detections_v2` w bazie danych MySQL. Posiada auto-reconnect i mechanizm awaryjnego cache w pliku `mysql_logger.cache` w razie awarii sieci.
*   **[latency_profiler.py](file:///c:/Users/gjaqb/Desktop/VisionSystem_UR3/db/latency_profiler.py)**: Precyzyjnie mierzy czasy latencji w milisekundach (czas analizy YOLO, logika strefowa na CPU oraz czas komendy RTDE). Zwraca uśrednione podsumowanie po zakończeniu naruszenia strefy.

---

## 3. Główne Zaimplementowane Algorytmy i Funkcje Safety

1.  **Histereza prędkości robota**: Zabezpiecza stawy robota przed drganiem (jitterem) i nagłymi zmianami prędkości. Po wyjściu człowieka ze strefy prędkość nominalna przywracana jest dopiero po `0.8` sekundy podtrzymania strefy zagrożenia.
2.  **Rozprzężenie Logowania i Histerezy (Decoupling)**: Sterowanie prędkością korzysta z czasu podtrzymania, ale logi bazodanowe i pomiar czasu rejestrują faktyczny, fizyczny czas pobytu człowieka w strefie. Dzięki temu naruszenia krótsze niż `0.5s` są poprawnie rejestrowane ze statusem **`requires checking`** (potencjalny fałszywy alarm).
3.  **Zabezpieczenie Fail-Safe kamery**: Jeśli w pętli głównej nastąpi zanik klatek wideo trwający dłużej niż `1.0` sekunda (np. odłączenie kabla), program natychmiast wysyła komendę zatrzymania awaryjnego cobota (redukcja prędkości do 10%) i informuje o krytycznym błędu.
4.  **Zapis awaryjny przy wyłączeniu (Force Save)**: Jeśli operator zamknie program klawiszem `q` podczas aktywnego naruszenia strefy, system wymusza zapisanie trwającej sesji do Excela i MySQL, co zapobiega utracie spójności danych.
5.  **Centralizacja identyfikatorów (`det_id`)**: Identyfikator sesji naruszenia jest przypisywany i synchronizowany na poziomie `main.py`, co gwarantuje spójne powiązanie wiersza w Excelu, rekordu w MySQL oraz pliku graficznego `.jpg`.

---

## 4. Jak Uruchomić Projekt?

1.  **Przygotowanie środowiska wirtualnego**:
    ```bash
    # Upewnij się, że jesteś w folderze głównym VisionSystem_UR3
    .\venv\Scripts\activate
    ```
2.  **Uruchomienie systemu**:
    ```bash
    python main.py
    ```
3.  **Menu Główne (w konsoli)**:
    *   Wybierz `1`, aby narysować strefy (Zielona $\rightarrow$ Żółta $\rightarrow$ Czerwona) i zapisz je wciskając `s`.
    *   Wybierz `2`, aby sprawdzić narysowane strefy na podglądzie wideo.
    *   Wybierz `3`, aby uruchomić pełny system detekcji i kontroli robota.
