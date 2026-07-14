import cv2
import time
import json
import os
import sys
import threading
from datetime import datetime
from ultralytics import YOLO
from db.event_logger import excel_logger  
from db.mysql_logger import mysql_logger 
import config
import config_zones

if config.TRYB_ONLINE:
    import rtde_io
    import rtde_receive

class ThreadedCamera:
    """
    Wątek czytający klatki z kamery w tle w celu wyeliminowania buforowania w OpenCV
    i zagwarantowania zerowego opóźnienia w czasie rzeczywistym.
    """
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self):
        while not self.stopped:
            if not self.cap.isOpened():
                break
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.ret = ret
                    self.frame = frame
            else:
                time.sleep(0.005)

    def read(self):
        with self.lock:
            return self.ret, self.frame.copy() if self.frame is not None else None

    def release(self):
        self.stopped = True
        self.thread.join(timeout=1.0)
        self.cap.release()


def show_saved_zones():
    if not os.path.exists('zones.json'):
        print("\n[ERROR] Brak zapisanego pliku zones.json. Wyznacz strefy.")
        return

    with open('zones.json', 'r') as f:
        zones = json.load(f)

    # Do podglądu stref używamy zwykłego przechwytywania (nie potrzebujemy wysokiej wydajności)
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

        height, width, _ = frame.shape
        cv2.rectangle(frame, (0, 0), (width, 40), (0, 0, 0), -1)

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


def point_in_zone(px, py, zone):
    if not zone:
        return False
    return zone["x1"] <= px <= zone["x2"] and zone["y1"] <= py <= zone["y2"]


def bbox_overlaps_zone(x1, y1, x2, y2, zone):
    if not zone:
        return False
    return x1 <= zone["x2"] and x2 >= zone["x1"] and y1 <= zone["y2"] and y2 >= zone["y1"]


def run_camera_robot_test():
    while True:
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

    # MAIN
    print("Trwa ladowanie modelu YOLO do pamieci VRAM")
    model = YOLO(config.MODEL_PATH_NAME)

    zones = {"green": None, "yellow": None, "red": None}
    if os.path.exists('zones.json'):
        with open('zones.json', 'r') as f:
            zones = json.load(f)
        print("Strefy wczytane poprawnie do glownego programu.")
    else:
        print("[ERROR] Brak pliku zones.json. Zabezpieczenie strefowe nieaktywne")

    # Inicjalizacja asynchronicznej kamery w osobnym wątku
    print("[Kamera] Inicjalizacja wątku kamery...")
    threaded_cap = ThreadedCamera(config.CAMERA_INDEX)
    ret, initial_frame = threaded_cap.read()
    if not ret or initial_frame is None:
        print("[ERROR] Nie można zainicjalizować kamery.")
        threaded_cap.release()
        return

    rtde_io_interface = None
    rtde_r = None

    if config.TRYB_ONLINE:
        print(f"[COBOT] Nawiazywanie polaczenia z {config.IP_ROBOTA}...")
        try:
            rtde_io_interface = rtde_io.RTDEIOInterface(config.IP_ROBOTA)
            rtde_r = rtde_receive.RTDEReceiveInterface(config.IP_ROBOTA)
            rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
            print("[COBOT] Polaczono z RTDE pomyślnie.")
        except Exception as e:
            print(f"[ERROR] RTDE: {e}")
            threaded_cap.release()
            return
    else:
        print("Skrypt uruchomiony w trybie offline.")

    # Inicjalizacja loggerów (obsługujących zapis asynchroniczny)
    logger_excel = excel_logger()
    logger_excel.init_check(config.LOG_FILE_NAME)
    
    logger_mysql = mysql_logger()
    logger_mysql.init_check()

    prev_time = time.time()
    last_sent_speed = config.PREDKOSC_NOMINALNA 

    # Zmienne obsługujące histerezę czasową i centralną synchronizację ID
    last_violation_time = 0.0
    last_active_zone = "NONE"
    current_det_id = logger_excel.next_id
    session_active = False
    session_id = None

    print("\n[INFO] Główna pętla detekcji uruchomiona. Wciśnij 'q', aby wyjść.")

    try:
        while True:
            ret, frame = threaded_cap.read()
            if not ret or frame is None:
                # Oczekiwanie na klatkę z wątku
                time.sleep(0.01)
                continue

            current_time = time.time()
            time_diff = current_time - prev_time
            current_fps = 1.0 / time_diff if time_diff > 0 else 30.0
            prev_time = current_time

            # Inference YOLO
            results = model(frame, classes=0, verbose=False)
            annotated_frame = results[0].plot()

            # Rysowanie przezroczystych stref nakładki
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
            
            # Wartości w tej klatce
            current_frame_zone = "NONE"
            current_frame_speed = config.PREDKOSC_NOMINALNA

            if widze_czlowieka:
                current_acc = float(results[0].boxes.conf[0].item())
                
                for box in results[0].boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()

                    # Sprawdzenie naruszenia według punktu stóp (feet) lub całego bboxa (bbox)
                    if config.DETECTION_POINT_MODE == "feet":
                        px, py = int((x1 + x2) / 2), int(y2)
                        in_red = point_in_zone(px, py, zones["red"])
                        in_yellow = point_in_zone(px, py, zones["yellow"])
                        in_green = point_in_zone(px, py, zones["green"])
                    else:
                        in_red = bbox_overlaps_zone(x1, y1, x2, y2, zones["red"])
                        in_yellow = bbox_overlaps_zone(x1, y1, x2, y2, zones["yellow"])
                        in_green = bbox_overlaps_zone(x1, y1, x2, y2, zones["green"])

                    # Priorytetyzacja stref (RED > YELLOW > GREEN)
                    if in_red:
                        current_frame_zone = "RED"
                        current_frame_speed = config.SPEED_RED
                        break  # RED to najwyższe zagrożenie, przerywamy sprawdzanie kolejnych boxów
                    elif in_yellow and current_frame_zone != "RED":
                        current_frame_zone = "YELLOW"
                        current_frame_speed = config.SPEED_YELLOW
                    elif in_green and current_frame_zone not in ["RED", "YELLOW"]:
                        current_frame_zone = "GREEN"
                        current_frame_speed = config.SPEED_GREEN

            # Zastosowanie mechanizmu histerezy czasowej (podtrzymania redukcji prędkości)
            now = time.time()
            if current_frame_zone != "NONE":
                last_violation_time = now
                last_active_zone = current_frame_zone
                target_speed = current_frame_speed
                active_zone_name = current_frame_zone
            else:
                # Jeśli brak naruszenia w tej klatce, sprawdź czy upłynął czas podtrzymania
                if now - last_violation_time < config.HYSTERESIS_TIME_S:
                    active_zone_name = last_active_zone
                    # Pobranie prędkości dla podtrzymywanej strefy
                    if active_zone_name == "RED":
                        target_speed = config.SPEED_RED
                    elif active_zone_name == "YELLOW":
                        target_speed = config.SPEED_YELLOW
                    elif active_zone_name == "GREEN":
                        target_speed = config.SPEED_GREEN
                    else:
                        target_speed = config.PREDKOSC_NOMINALNA
                else:
                    active_zone_name = "NONE"
                    target_speed = config.PREDKOSC_NOMINALNA
                    last_active_zone = "NONE"

            # Wysłanie komendy prędkości do RTDE tylko przy zmianie stanu
            if target_speed != last_sent_speed:
                last_sent_speed = target_speed
                if config.TRYB_ONLINE and rtde_io_interface is not None:
                    try:
                        rtde_io_interface.setSpeedSlider(target_speed)
                        print(f"[COBOT] Prędkość zmieniona na: {int(target_speed * 100)}% (Strefa: {active_zone_name})")
                    except Exception as e:
                        print(f"[ERROR] RTDE setSpeedSlider: {e}")

            current_inf_time = results[0].speed['inference']

            # Pobranie pozycji rzeczywistej robota (RTDE Receive)
            if config.TRYB_ONLINE and rtde_r is not None:
                try:
                    pose = rtde_r.getActualTCPPose()
                    robot_x = pose[0] * 1000
                    robot_y = pose[1] * 1000
                    robot_z = pose[2] * 1000
                    slider_fraction = rtde_r.getTargetSpeedFraction()
                    slider_percent = int(slider_fraction * 100)
                except Exception:
                    robot_x, robot_y, robot_z = 0.0, 0.0, 0.0
                    slider_percent = int(last_sent_speed * 100)
            else:
                robot_x, robot_y, robot_z = 0.0, 0.0, 0.0
                slider_percent = int(last_sent_speed * 100)

            is_raw_violation = (current_frame_zone != "NONE")

            # Zarządzanie stanem i ID sesji detekcji (na podstawie surowego naruszenia)
            if is_raw_violation:
                if not session_active:
                    session_active = True
                    session_id = current_det_id
                active_id = session_id
            else:
                active_id = current_det_id

            # Przekazanie danych do logowania (korzysta z surowej detekcji, aby poprawnie mierzyć czas rzeczywisty)
            logger_excel.acquisition(
                detection_bool=is_raw_violation,
                camera_id=config.CAMERA_ID, 
                current_acc=current_acc,
                model_name=config.MODEL_PATH_NAME, 
                hardware_setup=config.HARDWARE_SETUP_STR,
                current_fps=current_fps, 
                current_inf_time=current_inf_time,
                robot_x=robot_x, 
                robot_y=robot_y, 
                robot_z=robot_z, 
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
                robot_x=robot_x, 
                robot_y=robot_y, 
                robot_z=robot_z,
                active_zone_name=current_frame_zone,
                det_id=active_id
            )

            # Zamknięcie sesji i inkrementacja ID po wykonaniu logowania w ramce kończącej
            if not is_raw_violation and session_active:
                session_active = False
                current_det_id += 1
                logger_excel.next_id = current_det_id
                session_id = None

            # Rysowanie HUD na ekranie
            height, width, _ = annotated_frame.shape
            cv2.rectangle(annotated_frame, (0, 0), (width, 40), (0, 0, 0), -1)

            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fps_str = f"FPS: {round(current_fps, 1)}"
            speed_str = f"Robot Speed: {slider_percent}%"
            zone_str = f"Zone: {active_zone_name}"
            # Wizualny wskaźnik histerezy
            if current_frame_zone == "NONE" and active_zone_name != "NONE":
                zone_str += " (HOLD)"

            hud_text = f"{time_str}  |  {fps_str}  |  {speed_str}  |  {zone_str}"
            cv2.putText(annotated_frame, hud_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            
            cv2.imshow(config.WINDOW_NAME, annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord('q') or key == ord('Q'):
                break

    except KeyboardInterrupt:
        print("\nPrzerwano działanie programu przez użytkownika.")
    
    finally:
        # Gwarancja przywrócenia pełnej prędkości robota i bezpiecznego zamknięcia
        print("\n[ZAMYKANIE] Rozpoczęto bezpieczne zamykanie systemu...")
        
        if config.TRYB_ONLINE and rtde_io_interface is not None:
            try:
                rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
                print("[ZAMYKANIE][COBOT] Przywrócono prędkość nominalną 100%.")
            except Exception as e:
                print(f"[ZAMYKANIE][ERROR] Nie udało się przywrócić prędkości robota: {e}")

        # Zamykanie wątku kamery
        threaded_cap.release()
        print("[ZAMYKANIE][Kamera] Zwolniono zasoby wideo.")

        # Zamykanie i zapis loggerów (oczekiwanie na opróżnienie kolejek zapisu)
        logger_excel.save_buffer(config.LOG_FILE_NAME)
        logger_mysql.close_connection()

        cv2.destroyAllWindows()
        print("[ZAMYKANIE] Wszystkie zasoby zostały pomyślnie zwolnione. Program zakończony.")

if __name__ == "__main__":
    run_camera_robot_test()