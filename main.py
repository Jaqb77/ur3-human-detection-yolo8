import sys
# Redirect all console prints and traceback errors to terminal_logs.txt immediately
from camera_gui.console_logger import ConsoleLogger
sys.stdout = ConsoleLogger()
sys.stderr = sys.stdout

import cv2
import time
import json
import os
from datetime import datetime
from ultralytics import YOLO
from db.event_logger import excel_logger  
from db.mysql_logger import mysql_logger 
import config
import camera_gui.zone_config as zone_config
from camera_gui.camera_utils import ThreadedCamera, point_in_zone, bbox_overlaps_zone, show_saved_zones
from camera_gui.gui_hud import draw_hud
from camera_gui.safety_failsafe import CameraFailSafe
from db.latency_profiler import LatencyProfiler

if config.ONLINE_MODE:
    import rtde_io
    import rtde_receive

def run_camera_robot_test():
    while True:
        # User menu 
        print("\n" + "="*45)
        print("       SYSTEM WIZYJNY BEZPIECZEŃSTWA UR3")
        print("="*45)
        print("1. Wyznacz nowe strefy")
        print("2. Pokaz aktualne strefy")
        print("3. Uruchom glowny skrypt detekcji")
        print("0. Wyjdz")
        print("="*45)
        
        wybor = input("Wybierz opcje: ").strip()
        
        if wybor == '1':
            zone_config.run()
        elif wybor == '2':
            show_saved_zones()
        elif wybor == '3':
            print("\n[INFO] Pomijam menu, uruchamianie glownego systemu detekcji...")
            break 
        elif wybor == '0':
            print("\n[INFO] Zamykanie programu.")
            sys.exit(0)
        else:
            print("\n[ERROR] Bledny wybor. Wpisz '1', '2', '3' lub '0'.")

    # Load YOLO Model
    print("Trwa ladowanie modelu YOLO do pamieci VRAM")
    model = YOLO(config.MODEL_PATH_NAME)

    # Load safety zones from zones.json
    zones = {"green": None, "yellow": None, "red": None}
    if os.path.exists('zones.json'):
        with open('zones.json', 'r') as f:
            zones = json.load(f)
        print("Strefy wczytane poprawnie do glownego programu.")
    else:
        print("[ERROR] Brak pliku zones.json. Zabezpieczenie strefowe nieaktywne")

    # Start threaded camera feed
    print("[Kamera] Inicjalizacja wątku kamery...")
    threaded_cap = ThreadedCamera(config.CAMERA_INDEX)
    ret, initial_frame = threaded_cap.read()
    if not ret or initial_frame is None:
        print("[ERROR] Nie można zainicjalizować kamery.")
        threaded_cap.release()
        return

    rtde_io_interface = None
    rtde_r = None

    # Connect to the Universal Robots UR3 cobot via RTDE
    if config.ONLINE_MODE:
        print(f"[COBOT] Nawiazywanie polaczenia z {config.ROBOT_IP}...")
        try:
            rtde_io_interface = rtde_io.RTDEIOInterface(config.ROBOT_IP)
            rtde_r = rtde_receive.RTDEReceiveInterface(config.ROBOT_IP)
            rtde_io_interface.setSpeedSlider(config.NOMINAL_SPEED)
            print("[COBOT] Polaczono z RTDE pomyślnie.")
        except Exception as e:
            print(f"[ERROR] RTDE: {e}")
            threaded_cap.release()
            return
    else:
        print("Skrypt uruchomiony w trybie offline.")

    # Initialize loggers
    logger_excel = excel_logger()
    logger_excel.init_check(config.LOG_FILE_NAME)
    
    logger_mysql = mysql_logger()
    logger_mysql.init_check()

    prev_time = time.time()
    last_sent_speed = config.NOMINAL_SPEED 

    # Jitter prevention and session tracking variables
    last_violation_time = 0.0
    last_active_zone = "NONE"
    current_det_id = logger_excel.next_id
    session_active = False
    session_id = None
    
    # Initialize safety failsafe and latency profiler
    failsafe = CameraFailSafe(timeout_s=1.0)
    profiler = LatencyProfiler()

    print("\n[INFO] Główna pętla detekcji uruchomiona. Wciśnij 'q', aby wyjść.")

    try:
        while True:
            ret, frame = threaded_cap.read()
            if not ret or frame is None:
                forced_speed = failsafe.check(rtde_io_interface, last_sent_speed)
                if forced_speed is not None:
                    last_sent_speed = forced_speed
                time.sleep(0.01)
                continue

            failsafe.update_frame()

            current_time = time.time()
            time_diff = current_time - prev_time
            current_fps = 1.0 / time_diff if time_diff > 0 else 30.0
            prev_time = current_time

            # Perform object detection
            results = model(frame, classes=0, verbose=False)
            annotated_frame = results[0].plot()

            # Render zone boundary outlines
            overlay = annotated_frame.copy()
            if zones["green"]:
                cv2.rectangle(overlay, (zones["green"]["x1"], zones["green"]["y1"]), (zones["green"]["x2"], zones["green"]["y2"]), (0, 255, 0), 2)
            if zones["yellow"]:
                cv2.rectangle(overlay, (zones["yellow"]["x1"], zones["yellow"]["y1"]), (zones["yellow"]["x2"], zones["yellow"]["y2"]), (0, 255, 255), 2)
            if zones["red"]:
                cv2.rectangle(overlay, (zones["red"]["x1"], zones["red"]["y1"]), (zones["red"]["x2"], zones["red"]["y2"]), (0, 0, 255), 2)
            cv2.addWeighted(overlay, 0.6, annotated_frame, 0.4, 0, annotated_frame)

            widze_czlowieka = len(results[0].boxes) > 0
            current_acc = 0.0
            
            current_frame_zone = "NONE"
            t_logic_start = time.perf_counter()

            widze_czlowieka = len(results[0].boxes) > 0
            current_acc = 0.0
            
            current_frame_zone = "NONE"
            current_frame_speed = config.NOMINAL_SPEED

            if widze_czlowieka:
                current_acc = float(results[0].boxes.conf[0].item())
                
                for box in results[0].boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()

                    # Determine point overlap strategy
                    if config.DETECTION_POINT_MODE == "feet":
                        px, py = int((x1 + x2) / 2), int(y2)
                        in_red = point_in_zone(px, py, zones["red"])
                        in_yellow = point_in_zone(px, py, zones["yellow"])
                        in_green = point_in_zone(px, py, zones["green"])
                    else:
                        in_red = bbox_overlaps_zone(x1, y1, x2, y2, zones["red"])
                        in_yellow = bbox_overlaps_zone(x1, y1, x2, y2, zones["yellow"])
                        in_green = bbox_overlaps_zone(x1, y1, x2, y2, zones["green"])

                    # Threat level classification logic
                    if in_red:
                        current_frame_zone = "RED"
                        current_frame_speed = config.SPEED_RED
                        break
                    elif in_yellow and current_frame_zone != "RED":
                        current_frame_zone = "YELLOW"
                        current_frame_speed = config.SPEED_YELLOW
                    elif in_green and current_frame_zone not in ["RED", "YELLOW"]:
                        current_frame_zone = "GREEN"
                        current_frame_speed = config.SPEED_GREEN

            # Hysteresis and hold-down logic for speed slider control
            now = time.time()
            if current_frame_zone != "NONE":
                last_violation_time = now
                last_active_zone = current_frame_zone
                target_speed = current_frame_speed
                active_zone_name = current_frame_zone
            else:
                if now - last_violation_time < config.HYSTERESIS_TIME_S:
                    active_zone_name = last_active_zone
                    if active_zone_name == "RED":
                        target_speed = config.SPEED_RED
                    elif active_zone_name == "YELLOW":
                        target_speed = config.SPEED_YELLOW
                    elif active_zone_name == "GREEN":
                        target_speed = config.SPEED_GREEN
                    else:
                        target_speed = config.NOMINAL_SPEED
                else:
                    active_zone_name = "NONE"
                    target_speed = config.NOMINAL_SPEED
                    last_active_zone = "NONE"

            t_logic_ms = (time.perf_counter() - t_logic_start) * 1000
            if session_active:
                profiler.log_logic(t_logic_ms)

            # Speed change command transmission
            if target_speed != last_sent_speed:
                last_sent_speed = target_speed
                if config.ONLINE_MODE and rtde_io_interface is not None:
                    try:
                        t_comm_start = time.perf_counter()
                        rtde_io_interface.setSpeedSlider(target_speed)
                        t_comm_ms = (time.perf_counter() - t_comm_start) * 1000
                        if session_active:
                            profiler.log_comm(t_comm_ms)
                        print(f"[COBOT] Prędkość zmieniona na: {int(target_speed * 100)}% (Strefa: {active_zone_name})")
                    except Exception as e:
                        print(f"[ERROR] RTDE setSpeedSlider: {e}")

            current_inf_time = results[0].speed['inference']
            if session_active:
                profiler.log_yolo(current_inf_time)

            # Read TCP pose and actual speed fraction from cobot
            if config.ONLINE_MODE and rtde_r is not None:
                try:
                    pose = rtde_r.getActualTCPPose()
                    robot_x, robot_y, robot_z = pose[0] * 1000, pose[1] * 1000, pose[2] * 1000
                    slider_percent = int(rtde_r.getTargetSpeedFraction() * 100)
                except Exception:
                    robot_x, robot_y, robot_z = 0.0, 0.0, 0.0
                    slider_percent = int(last_sent_speed * 100)
            else:
                robot_x, robot_y, robot_z = 0.0, 0.0, 0.0
                slider_percent = int(last_sent_speed * 100)

            # Central ID and logging session state management
            is_raw_violation = (current_frame_zone != "NONE")
            if is_raw_violation:
                if not session_active:
                    session_active = True
                    session_id = current_det_id
                active_id = session_id
            else:
                active_id = current_det_id

            # Queue tasks to Excel and MySQL logs
            logger_excel.acquisition(
                detection_bool=is_raw_violation,
                camera_id=config.CAMERA_ID, 
                current_acc=current_acc,
                model_name=config.MODEL_PATH_NAME, 
                hardware_setup=config.HARDWARE_SETUP_STR,
                current_fps=current_fps, 
                current_inf_time=current_inf_time,
                robot_x=robot_x, robot_y=robot_y, robot_z=robot_z, 
                active_zone_name=current_frame_zone,
                frame=annotated_frame,
                det_id=active_id
            )

            logger_mysql.acquisition(
                detection_bool=is_raw_violation, 
                camera_id=config.CAMERA_ID, 
                current_acc=current_acc,
                model_name=config.MODEL_PATH_NAME, 
                hardware_setup=config.HARDWARE_SETUP_STR,
                current_fps=current_fps, 
                current_inf_time=current_inf_time,
                robot_x=robot_x, robot_y=robot_y, robot_z=robot_z,
                active_zone_name=current_frame_zone,
                det_id=active_id
            )

            if not is_raw_violation and session_active:
                session_active = False
                current_det_id += 1
                logger_excel.next_id = current_det_id
                session_id = None
                profiler.print_summary()

            # Render HUD layout
            is_hold = (current_frame_zone == "NONE" and active_zone_name != "NONE")
            annotated_frame = draw_hud(
                annotated_frame, 
                current_fps, 
                current_inf_time, 
                slider_percent, 
                active_zone_name, 
                current_frame_zone, 
                is_hold
            )
            
            cv2.imshow(config.WINDOW_NAME, annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord('q') or key == ord('Q'):
                break

    except KeyboardInterrupt:
        print("\nPrzerwano działanie programu przez użytkownika.")
    
    finally:
        print("\n[ZAMYKANIE] Rozpoczęto bezpieczne zamykanie systemu...")
        if config.ONLINE_MODE and rtde_io_interface is not None:
            try:
                rtde_io_interface.setSpeedSlider(config.NOMINAL_SPEED)
                print("[ZAMYKANIE][COBOT] Przywrócono prędkość nominalną 100%.")
            except Exception as e:
                print(f"[ZAMYKANIE][ERROR] Nie udało się przywrócić prędkości robota: {e}")

        threaded_cap.release()
        print("[ZAMYKANIE][Kamera] Zwolniono zasoby wideo.")

        logger_excel.save_buffer(config.LOG_FILE_NAME)
        logger_mysql.close_connection()

        cv2.destroyAllWindows()
        print("[ZAMYKANIE] Zakończono zwalnianie zasobów.")

if __name__ == "__main__":
    run_camera_robot_test()