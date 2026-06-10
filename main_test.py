import cv2
from ultralytics import YOLO

def run_camera_robot_test():
    window_name = 'Podglad Kamery + YOLOv8 Pose (TRYB OFFLINE)'
    model = YOLO('yolov8n-pose.pt')
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        return

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        results = model(frame, verbose=False)
        annotated_frame = results[0].plot()

        widze_czlowieka = len(results[0].keypoints) > 0

        if widze_czlowieka:
            slider_value = 0.5
            status_txt = "Status: Zmniejszenie predkosci (50%)"
            status_color = (0, 0, 255)
        else:
            slider_value = 1.0
            status_txt = "Status: Predkosc nominalna (100%)"
            status_color = (0, 255, 0)

        cv2.putText(annotated_frame, status_txt, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2, cv2.LINE_AA)

        cv2.imshow(window_name, annotated_frame)

        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_camera_robot_test()