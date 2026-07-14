import cv2
import json
import config

# Global variables for mouse drawing logic
zones = {"green": None, "yellow": None, "red": None}
current_zone = "green"
drawing = False
ix, iy = -1, -1
current_x, current_y = -1, -1

def draw_rectangle(event, x, y, flags, param):
    """
    Mouse callback function to draw safety zone rectangles.
    """
    global ix, iy, current_x, current_y, drawing, current_zone, zones

    if event == cv2.EVENT_LBUTTONDOWN:
        if current_zone in zones:
            drawing = True
            ix, iy = x, y
            current_x, current_y = x, y

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            current_x, current_y = x, y

    elif event == cv2.EVENT_LBUTTONUP:
        if drawing:
            drawing = False
            current_x, current_y = x, y
            
            # Save coordinates min/max to ensure x1 < x2 and y1 < y2
            zones[current_zone] = {
                "x1": min(ix, current_x), "y1": min(iy, current_y),
                "x2": max(ix, current_x), "y2": max(iy, current_y)
            }

            # State transition to configure next zone
            if current_zone == "green":
                current_zone = "yellow"
            elif current_zone == "yellow":
                current_zone = "red"
            else:
                current_zone = "done"

def run():
    """
    Starts the zone configuration GUI.
    """
    global current_zone, zones, drawing

    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[ERROR] Konfigurator: Nie można uruchomić kamery.")
        return

    cv2.namedWindow('Konfigurator Stref')
    cv2.setMouseCallback('Konfigurator Stref', draw_rectangle)

    print("\n--- KONFIGURATOR STREF BEZPIECZEŃSTWA ---")
    print("1. Narysuj ZIELONĄ strefę (lewy przycisk myszy).")
    print("2. Narysuj ŻÓŁTĄ strefę.")
    print("3. Narysuj CZERWONĄ strefę.")
    print("4. Wciśnij 's', aby zapisać strefy.")
    print("5. Wciśnij 'r', aby zresetować rysowanie.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Draw already configured zones
        if zones["green"]:
            cv2.rectangle(frame, (zones["green"]["x1"], zones["green"]["y1"]), (zones["green"]["x2"], zones["green"]["y2"]), (0, 255, 0), 2)
        if zones["yellow"]:
            cv2.rectangle(frame, (zones["yellow"]["x1"], zones["yellow"]["y1"]), (zones["yellow"]["x2"], zones["yellow"]["y2"]), (0, 255, 255), 2)
        if zones["red"]:
            cv2.rectangle(frame, (zones["red"]["x1"], zones["red"]["y1"]), (zones["red"]["x2"], zones["red"]["y2"]), (0, 0, 255), 2)

        # Draw current active drawing rectangle
        if drawing:
            if current_zone == "green":
                color = (0, 255, 0)
            elif current_zone == "yellow":
                color = (0, 255, 255)
            else:
                color = (0, 0, 255)
            cv2.rectangle(frame, (ix, iy), (current_x, current_y), color, 2)

        # Top status panel overlay
        height, width, _ = frame.shape
        cv2.rectangle(frame, (0, 0), (width, 40), (0, 0, 0), -1)

        # Status text (displayed in Polish as requested)
        status_text = f"Rysujesz: {current_zone.upper()}" if current_zone != "done" else "GOTOWE! Wcisnij 's' aby zapisac."
        cv2.putText(frame, status_text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow('Konfigurator Stref', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s') or key == ord('S'):
            with open('zones.json', 'w') as f:
                json.dump(zones, f)
            print("[INFO] Strefy zostały pomyślnie zapisane do pliku 'zones.json'.")
            break
        elif key == ord('r') or key == ord('R'):
            current_zone = "green"
            zones = {"green": None, "yellow": None, "red": None}
            drawing = False
            print("[INFO] Zresetowano obszary.")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()
