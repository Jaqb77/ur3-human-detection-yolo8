import cv2
import time
import json
import os
import threading
import config

class ThreadedCamera:
    """
    Spawns a separate thread to continuously capture camera frames,
    eliminating OpenCV's internal frame buffering to guarantee real-time latency.
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


def point_in_zone(px, py, zone):
    """
    Checks if point (px, py) is inside the rectangular zone coordinates.
    """
    if not zone:
        return False
    return zone["x1"] <= px <= zone["x2"] and zone["y1"] <= py <= zone["y2"]


def bbox_overlaps_zone(x1, y1, x2, y2, zone):
    """
    Checks if a bounding box (x1, y1, x2, y2) overlaps a rectangular zone.
    """
    if not zone:
        return False
    return x1 <= zone["x2"] and x2 >= zone["x1"] and y1 <= zone["y2"] and y2 >= zone["y1"]


def show_saved_zones():
    """
    Displays a live video window showing the static zones loaded from zones.json.
    """
    if not os.path.exists('zones.json'):
        print("\n[ERROR] Brak zapisanego pliku zones.json. Wyznacz strefy.")
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
