# System wizyjny dla Cobota UR3 CB3

System bezpieczeństwa czasu rzeczywistego - "Speed and Separation Monitoring" dedykowany dla robota współpracującego **Universal Robots UR3**. System integruje detekcję ludzi przy użyciu modelu **YOLOv8** ze sterowaniem prędkością robota w czasie rzeczywistym poprzez protokół Real-Time Data Exchange oraz asynchronicznym rejestrowaniem zdarzeń.

---
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
