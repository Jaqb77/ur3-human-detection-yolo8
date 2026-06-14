import cv2
import time
from datetime import datetime
from ultralytics import YOLO
from db.event_logger import excel_logger  
import config

if config.TRYB_ONLINE:
    import rtde_io
    import rtde_receive

def run_camera_robot_test():
    model = YOLO(config.MODEL_PATH_NAME)
    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)

    if not cap.isOpened():
        return

    rtde_io_interface = None
    rtde_r = None

    if config.TRYB_ONLINE:
        print(f"Próba nawiązania połączenia z {config.IP_ROBOTA}...")
        try:
            rtde_io_interface = rtde_io.RTDEIOInterface(config.IP_ROBOTA)
            rtde_r = rtde_receive.RTDEReceiveInterface(config.IP_ROBOTA)
            rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
            print("Połączono z RTDE")
        except Exception as e:
            print(f"Error RTDE: {e}")
            cap.release()
            return
    else:
        print("Skrypt uruchomiony w trybie offline.")

    logger = excel_logger()
    logger.init_check(config.LOG_FILE_NAME)
    
    prev_time = time.time()
    czy_byl_czlowiek = False
 
    detection_start_timer = None

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        current_time = time.time()
        time_diff = current_time - prev_time
        current_fps = 1.0 / time_diff if time_diff > 0 else 30.0
        prev_time = current_time

        results = model(frame, verbose=False, device=0)
        annotated_frame = results[0].plot()

        widze_czlowieka = len(results[0].keypoints) > 0

        current_acc = 0.0
        slider_value = config.PREDKOSC_NOMINALNA

        if widze_czlowieka:
            if len(results[0].boxes) > 0:
                current_acc = float(results[0].boxes.conf[0].item())
            

            if detection_start_timer is None:
                detection_start_timer = current_time
            
            elapsed_detection_time = current_time - detection_start_timer
            
            if elapsed_detection_time >= config.MIN_DETECTION_TIME_S:
                slider_value = config.PREDKOSC_ZREDUKOWANA
                if config.TRYB_ONLINE and not czy_byl_czlowiek:
                    try:
                        rtde_io_interface.setSpeedSlider(config.PREDKOSC_ZREDUKOWANA)
                    except Exception as e:
                        print(f"Błąd zapisu do RTDE: {e}")
                    czy_byl_czlowiek = True
        else:
            detection_start_timer = None
            slider_value = config.PREDKOSC_NOMINALNA
            if config.TRYB_ONLINE and czy_byl_czlowiek:
                try:
                    rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
                except Exception as e:
                    print(f"Błąd zapisu do RTDE: {e}")
                czy_byl_czlowiek = False

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
                slider_percent = int(slider_value * 100)
        else:
            robot_x = 0.0
            robot_y = 0.0
            robot_z = 0.0
            slider_percent = int(slider_value * 100)


        logger.acquisition(
            detection_bool=widze_czlowieka,
            camera_id=config.CAMERA_ID,
            current_acc=current_acc,
            model_name=config.MODEL_PATH_NAME,
            hardware_setup=config.HARDWARE_SETUP_STR,
            current_fps=current_fps,
            current_inf_time=current_inf_time,
            robot_x=robot_x,
            robot_y=robot_y,
            robot_z=robot_z,
            frame=annotated_frame
        )

        height, width, _ = annotated_frame.shape
        cv2.rectangle(annotated_frame, (0, 0), (width, 40), (0, 0, 0), -1)

        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fps_str = f"FPS: {round(current_fps, 1)}"
        speed_str = f"Robot Speed: {slider_percent}%"
        
        hud_text = f"{time_str}  |  {fps_str}  |  {speed_str}"

        cv2.putText(annotated_frame, hud_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.imshow(config.WINDOW_NAME, annotated_frame)

        key = cv2.waitKey(1) & 0xFF

        if cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            break

        if key == ord('q') or key == ord('Q'):
            break

    print("Zamykanie programu. Zapisywanie zebranego bufora do Excela...")
    logger.save_buffer(config.LOG_FILE_NAME)

    if config.TRYB_ONLINE and rtde_io_interface is not None:
        try:
            rtde_io_interface.setSpeedSlider(config.PREDKOSC_NOMINALNA)
        except:
            pass

    cap.release()
    cv2.destroyAllWindows()
    print("Skrypt wyłączony.")

if __name__ == "__main__":
    run_camera_robot_test()