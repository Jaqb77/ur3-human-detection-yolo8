import cv2
import time
from datetime import datetime
from ultralytics import YOLO
from db.event_logger import excel_logger  

def run_camera_robot_test():
    window_name = 'Podglad Kamery + YOLOv8 Pose (TRYB OFFLINE)'
    model_path_name = 'yolov8n-pose.pt'
    model = YOLO(model_path_name)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        return

    logger = excel_logger()
    file_name = "logs_detection_ur3.xlsx"
    logger.init_check(file_name)
    
    camera_id = 0
    prev_time = time.time()

    print("Skrypt uruchomiony w trybie offline.")

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        current_time = time.time()
        time_diff = current_time - prev_time
        current_fps = 1.0 / time_diff if time_diff > 0 else 30.0
        prev_time = current_time

        results = model(frame, verbose=False)
        annotated_frame = results[0].plot()

        widze_czlowieka = len(results[0].keypoints) > 0

        current_acc = 0.0
        if widze_czlowieka:
            slider_value = 0.5
            if len(results[0].boxes) > 0:
                current_acc = float(results[0].boxes.conf[0].item())
        else:
            slider_value = 1.0

        current_inf_time = results[0].speed['inference']

        simulated_tcp_x = 0.0
        simulated_tcp_y = 0.0
        simulated_tcp_z = 0.0

        logger.acquisition(
            detection_bool=widze_czlowieka,
            current_acc=current_acc,
            current_fps=current_fps,
            current_inf_time=current_inf_time,
            robot_x=simulated_tcp_x,
            robot_y=simulated_tcp_y,
            robot_z=simulated_tcp_z,
            camera_id=camera_id,
            model_name=model_path_name
        )

        height, width, _ = annotated_frame.shape
        cv2.rectangle(annotated_frame, (0, 0), (width, 40), (0, 0, 0), -1)

        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fps_str = f"FPS: {round(current_fps, 1)}"
        speed_str = f"Robot Speed: {int(slider_value * 100)}%"
        
        hud_text = f"{time_str}  |  {fps_str}  |  {speed_str}"

        cv2.putText(annotated_frame, hud_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.imshow(window_name, annotated_frame)

        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    print("Zamykanie programu. Zapisywanie zebranego bufora do Excela...")
    logger.save_buffer(file_name)

    cap.release()
    cv2.destroyAllWindows()
    print("Skrypt wyłączony.")

if __name__ == "__main__":
    run_camera_robot_test()