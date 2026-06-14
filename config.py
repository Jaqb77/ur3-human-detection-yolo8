import os
from dotenv import load_dotenv

load_dotenv()

TRYB_ONLINE = os.getenv("TRYB_ONLINE", "False").lower() in ("true", "1", "yes")
IP_ROBOTA = os.getenv("IP_ROBOTA") 

if TRYB_ONLINE and not IP_ROBOTA:
    raise ValueError(
        "[ERROR] Uruchomiono TRYB_ONLINE, ale nie zdefiniowano IP_ROBOTA w pliku .env"
    )

MODEL_PATH_NAME = 'yolov8n-pose.pt'
CAMERA_INDEX = 1  
HARDWARE_SETUP_STR = "cobot" if TRYB_ONLINE else "no cobot"
WINDOW_NAME = '(TRYB ONLINE)' if TRYB_ONLINE else '(TRYB OFFLINE)'

LOG_FILE_NAME = "logs_detection_ur3.xlsx"
CAMERA_ID = 1  

PREDKOSC_NOMINALNA = 1.0  
PREDKOSC_ZREDUKOWANA = 0.3  
MIN_DETECTION_TIME_S = 0.5 