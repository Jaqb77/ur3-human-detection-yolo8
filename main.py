import cv2
import time
import json
import os
import sys
from datetime import datetime
from ultralytics import YOLO
from db.event_logger import excel_logger  
from db.mysql_logger import mysql_logger 
import config
import config_zones

if config.TRYB_ONLINE:
    import rtde_io
    import rtde_receive

def show_saved_zones():
    if not os.path.exists('zones.json'):
        print("\n[WARNING] Brak zapisanego pliku zones.json. Najpierw wyznacz strefy (Opcja 1).")
        return

    with open('zones.json', 'r') as f:
        zones = json.load(f)

    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[ERROR] Nie można uruchomić kamery.")
        return

    print("\n[INFO] Uruchomiono podgląd stref. Wciśnij 'q', aby zamknąć okno i wrócić do menu.")
    cv2.namedWindow('Podglad Stref')

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Tło pod tekst
        height, width, _ = frame.shape
        cv2.rectangle(frame, (0, 0), (width, 40), (0, 0, 0), -1)

        # Rysowanie stref
        if zones.get("green") and zones["green"] is not None:
            cv2.rectangle(frame, (zones["green"]["x1"], zones["green"]["y1"]), (zones["green"]["x2"], zones["green"]["y2"]), (0, 255, 0), 2)
        if zones.get("yellow") and zones["yellow"] is not None:
            cv2.rectangle(frame, (zones["yellow"]["x1"], zones["yellow"]["y1"]), (zones["yellow"]["x2"], zones["yellow"]["y2"]), (0, 255, 255), 2)
        if zones.get("red") and zones["red"] is not None:
            cv2.rectangle(frame, (zones["red"]["x1"], zones["red"]["y1"]), (zones["red"]["x2"], zones["red"]["y2"]), (0, 0, 255), 2)

        cv2.putText(frame, "Podglad stref. Wcisnij 'q' aby wyjsc do menu.", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow('Podglad Stref', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q') or cv2.getWindowProperty('Podglad Stref', cv2.WND_PROP_VISIBLE) < 1:
            break

    cap.release()
    cv2.destroyAllWindows()


def run_camera_robot_test():
    while True:
        print("\n" + "="*45)
        print("       SYSTEM WIZYJNY BEZPIECZEŃSTWA UR3")
        print("="*45)
        print("1. Wyznacz nowe strefy (Konfigurator)")
        print("2. Pokaz aktualnie zapisane strefy")
        print("3. Uruchom glowny program detekcji")
        print("0. Wyjdz z programu")
        print("="*45)
        
        wybor = input("Wybierz opcje: ").strip()
        
        if wybor == '1':
            config_zones.run()
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

    # ========
    #  START 
    # ========

    print("[AI] Trwa ladowanie modelu YOLO do pamieci VRAM...")
    model = YOLO(config.MODEL_PATH_NAME)

    zones = {"green": None, "yellow": None, "red": None}
    if os.path.exists('zones.json'):
        with open('zones.json', 'r') as f:
            zones = json.load(f)
        print("[INFO] Strefy wczytane poprawnie do glownego programu.")
    else:
        print("[WARNING] Brak pliku zones.json. Zabezpieczenie strefowe bedzie nieaktywne!")

    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)

    if not cap.isOpened():
        return

    rtde_io_interface = None
    rtde_r = None

    if config.TRYB_ONLINE:
        print(f"Proba nawiazania polaczenia z {config.IP_ROBOTA}...")
        try:
            rtde_io_interface = rtde_io.RTDEIOInterface(config.IP_ROBOTA)
            rtde_r = rtde_receive.RTDEReceiveInterface(config.IP_ROBOTA)
            rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
            print("[COBOT] Polaczono z RTDE")
        except Exception as e:
            print(f"[COBOT] Error RTDE: {e}")
            cap.release()
            return
    else:
        print("Skrypt uruchomiony w trybie offline.")

    logger_excel = excel_logger()
    logger_excel.init_check(config.LOG_FILE_NAME)
    
    logger_mysql = mysql_logger()
    logger_mysql.init_check()

    prev_time = time.time()
    
    last_sent_speed = config.PREDKOSC_NOMINALNA 

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_time = time.time()
        time_diff = current_time - prev_time
        current_fps = 1.0 / time_diff if time_diff > 0 else 30.0
        prev_time = current_time

        results = model(frame, classes=0, verbose=False)
        annotated_frame = results[0].plot()

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
        
        target_speed = config.PREDKOSC_NOMINALNA
        active_zone_name = "NONE"

        if widze_czlowieka:
            current_acc = float(results[0].boxes.conf[0].item())
            
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                if zones["red"] and (x1 <= zones["red"]["x2"] and x2 >= zones["red"]["x1"] and y1 <= zones["red"]["y2"] and y2 >= zones["red"]["y1"]):
                    target_speed = config.SPEED_RED
                    active_zone_name = "RED"
                elif active_zone_name != "RED" and zones["yellow"] and (x1 <= zones["yellow"]["x2"] and x2 >= zones["yellow"]["x1"] and y1 <= zones["yellow"]["y2"] and y2 >= zones["yellow"]["y1"]):
                    target_speed = config.SPEED_YELLOW
                    active_zone_name = "YELLOW"
                elif active_zone_name not in ["RED", "YELLOW"] and zones["green"] and (x1 <= zones["green"]["x2"] and x2 >= zones["green"]["x1"] and y1 <= zones["green"]["y2"] and y2 >= zones["green"]["y1"]):
                    target_speed = config.SPEED_GREEN
                    active_zone_name = "GREEN"

            if active_zone_name != "NONE":
                if target_speed != last_sent_speed:
                    last_sent_speed = target_speed
                    
                    if config.TRYB_ONLINE:
                        try:
                            rtde_io_interface.setSpeedSlider(target_speed)
                        except Exception as e:
                            print(f"[COBOT] Błąd zapisu do RTDE: {e}")
            else:
                if last_sent_speed != config.PREDKOSC_NOMINALNA:
                    last_sent_speed = config.PREDKOSC_NOMINALNA
                    
                    if config.TRYB_ONLINE:
                        try:
                            rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
                        except Exception as e:
                            print(f"[COBOT] Błąd zapisu do RTDE: {e}")

        else:
            if last_sent_speed != config.PREDKOSC_NOMINALNA:
                last_sent_speed = config.PREDKOSC_NOMINALNA
                
                if config.TRYB_ONLINE:
                    try:
                        rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
                    except Exception as e:
                        print(f"[COBOT] Błąd zapisu do RTDE: {e}")

        current_inf_time = results[0].speed['inference']

        if config.TRYB_ONLINE:
            try:
                pose = rtde_r.getActualTCPPose()
                robot_x = pose[0] * 1000
                robot_y = pose[1] * 1000
                robot_z = pose[2] * 1000
                slider_fraction = rtde_r.getTargetSpeedFraction()
                slider_percent = int(slider_fraction * 100)
            except:
                robot_x = 0.0
                robot_y = 0.0
                robot_z = 0.0
                slider_percent = int(last_sent_speed * 100)
        else:
            robot_x = 0.0
            robot_y = 0.0
            robot_z = 0.0
            slider_percent = int(last_sent_speed * 100)

        is_violation = widze_czlowieka and active_zone_name != "NONE"

        logger_excel.acquisition(
            detection_bool=is_violation,
            camera_id=config.CAMERA_ID, 
            current_acc=current_acc,
            model_name=config.MODEL_PATH_NAME, 
            hardware_setup=config.HARDWARE_SETUP_STR,
            current_fps=current_fps, 
            current_inf_time=current_inf_time,
            robot_x=robot_x, 
            robot_y=robot_y, 
            robot_z=robot_z, 
            active_zone_name=active_zone_name,
            frame=annotated_frame
        )

        logger_mysql.acquisition(
            detection_bool=is_violation, 
            camera_id=config.CAMERA_ID, 
            current_acc=current_acc,
            model_name=config.MODEL_PATH_NAME, 
            hardware_setup=config.HARDWARE_SETUP_STR,
            current_fps=current_fps, 
            current_inf_time=current_inf_time,
            robot_x=robot_x, 
            robot_y=robot_y, 
            robot_z=robot_z,
            active_zone_name=active_zone_name
        )

        height, width, _ = annotated_frame.shape
        cv2.rectangle(annotated_frame, (0, 0), (width, 40), (0, 0, 0), -1)

        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fps_str = f"FPS: {round(current_fps, 1)}"
        speed_str = f"Robot Speed: {slider_percent}%"
        zone_str = f"Zone: {active_zone_name}"
        hud_text = f"{time_str}  |  {fps_str}  |  {speed_str}  |  {zone_str}"

        cv2.putText(annotated_frame, hud_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(config.WINDOW_NAME, annotated_frame)

        key = cv2.waitKey(1) & 0xFF
        if cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            break
        if key == ord('q') or key == ord('Q'):
            break
        
    print("Zamykanie skryptu. Zapisywanie bufora Excel...")
    logger_excel.save_buffer(config.LOG_FILE_NAME)
    logger_mysql.close_connection()

    if config.TRYB_ONLINE and rtde_io_interface is not None:
        try:
            rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
        except:
            pass

    cap.release()
    cv2.destroyAllWindows()
    print("Skrypt wylaczony.")

if __name__ == "__main__":
    run_camera_robot_test()