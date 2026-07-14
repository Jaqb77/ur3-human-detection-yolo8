import os
from dotenv import load_dotenv

load_dotenv()

TRYB_ONLINE = os.getenv("TRYB_ONLINE", "False").lower() in ("true", "1", "yes")
IP_ROBOTA = os.getenv("IP_ROBOTA") 

if TRYB_ONLINE and not IP_ROBOTA:
    raise ValueError(
        "[ERROR] Uruchomiono TRYB_ONLINE, ale nie zdefiniowano IP_ROBOTA w pliku .env"
    )

MODEL_PATH_NAME = 'yolov8n.pt'  
CAMERA_INDEX = 0  
HARDWARE_SETUP_STR = "cobot" if TRYB_ONLINE else "no cobot"
WINDOW_NAME = '(TRYB ONLINE)' if TRYB_ONLINE else '(TRYB OFFLINE)'

LOG_FILE_NAME = "logs_detection_ur3.xlsx"
CAMERA_ID = 0  

PREDKOSC_NOMINALNA = 1.0  
SPEED_GREEN = 0.50   
SPEED_YELLOW = 0.25 
SPEED_RED = 0.10     

MIN_DETECTION_TIME_S = 1
URUCHOM_KONFIGURATOR_STREF = True  
HYSTERESIS_TIME_S = 0.8  # Czas podtrzymania redukcji prędkości po zaniku detekcji (zapobiega drganiom/szarpaniu)
DETECTION_POINT_MODE = "bbox"  # "feet" (środek dolnej krawędzi boxa) lub "bbox" (cały bbox)

DB_HOST = os.getenv("DB_HOST", "local")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "robot_safety")