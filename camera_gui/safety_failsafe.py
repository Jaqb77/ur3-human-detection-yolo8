import time
import sys
import config

class CameraFailSafe:
    """
    Monitors camera feed and triggers a safe state (forced speed limit / stop)
    if the camera fails to deliver new frames within the defined timeout.
    """
    def __init__(self, timeout_s=1.0):
        self.timeout_s = timeout_s
        self.last_frame_time = time.time()
        self.triggered = False

    def update_frame(self):
        """
        Call this whenever a new frame is successfully read.
        """
        self.last_frame_time = time.time()
        self.triggered = False

    def check(self, rtde_io_interface, current_sent_speed):
        """
        Checks for timeouts and forces the speed slider to safe limit if triggered.
        """
        if time.time() - self.last_frame_time > self.timeout_s:
            if not self.triggered:
                self.triggered = True
                print("[FATAL][COBOT] BRAK SYGNAŁU Z KAMERY PRZEZ PONAD 1.0s! WYZWALAM ZATRZYMANIE AWARYJNE (STOP/RED).")
            
            if current_sent_speed != config.SPEED_RED:
                if config.ONLINE_MODE and rtde_io_interface is not None:
                    try:
                        rtde_io_interface.setSpeedSlider(config.SPEED_RED)
                    except Exception as e:
                        print(f"[FATAL][ERROR] Awaryjne ustawienie prędkości RTDE nie powiodło się: {e}")
                return config.SPEED_RED
        return None



