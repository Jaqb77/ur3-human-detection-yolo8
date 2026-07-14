import os
from dotenv import load_dotenv

load_dotenv()

# --- Connection Configuration ---
ONLINE_MODE = os.getenv("TRYB_ONLINE", "False").lower() in ("true", "1", "yes")
ROBOT_IP = os.getenv("IP_ROBOTA") 

if ONLINE_MODE and not ROBOT_IP:
    raise ValueError(
        "[ERROR] Uruchomiono TRYB_ONLINE, ale nie zdefiniowano IP_ROBOTA w pliku .env"
    )

# --- Hardware and UI Configuration ---
MODEL_PATH_NAME = 'yolov8n.pt'  
CAMERA_INDEX = 0  
HARDWARE_SETUP_STR = "cobot" if ONLINE_MODE else "no cobot"
WINDOW_NAME = '(TRYB ONLINE)' if ONLINE_MODE else '(TRYB OFFLINE)'

# --- Log Files Configuration ---
LOG_FILE_NAME = "logs_detection_ur3.xlsx"
CAMERA_ID = 0  

# --- Robot Speeds Configuration ---
NOMINAL_SPEED = 1.0  
SPEED_GREEN = 0.50   
SPEED_YELLOW = 0.25 
SPEED_RED = 0.10     

# --- Detection Parameters ---
MIN_DETECTION_TIME_S = 0.5 
RUN_ZONE_CONFIGURATOR = True  
HYSTERESIS_TIME_S = 0.8 
DETECTION_POINT_MODE = "bbox"  # "feet" or "bbox"
SHOW_LATENCY_PROFILER = False  

# --- MySQL Database Configuration ---
DB_HOST = os.getenv("DB_HOST", "local")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "robot_safety")