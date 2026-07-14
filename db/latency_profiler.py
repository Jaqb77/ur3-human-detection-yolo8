import time
import config

class LatencyProfiler:
    """
    Measures and logs system latency components (YOLO inference, stefy logic,
    and RTDE Ethernet communication) to analyze reaction times for master's thesis.
    """
    def __init__(self):
        self.yolo_times = []
        self.logic_times = []
        self.comm_times = []
        
    def log_yolo(self, t_ms):
        self.yolo_times.append(t_ms)
        
    def log_logic(self, t_ms):
        self.logic_times.append(t_ms)
        
    def log_comm(self, t_ms):
        self.comm_times.append(t_ms)
        
    def print_summary(self):
        """
        Prints the average reaction times measured during the active session.
        """
        if not self.yolo_times:
            return
        avg_yolo = sum(self.yolo_times) / len(self.yolo_times)
        avg_logic = sum(self.logic_times) / len(self.logic_times)
        avg_comm = sum(self.comm_times) / len(self.comm_times) if self.comm_times else 0.0
        total = avg_yolo + avg_logic + avg_comm
        
        if getattr(config, "SHOW_LATENCY_PROFILER", True):
            print(f"\n[LOG] ŚREDNIE CZASY REAKCJI SYSTEMU (sesja ID zakończona):")
            print(f"  - Detekcja modelu:       {round(avg_yolo, 2)} ms")
            print(f"  - Logika (CPU):  {round(avg_logic, 2)} ms")
            print(f"  - Transmisja RTDE (LAN):  {round(avg_comm, 2)} ms")
            print(f"  - Łączny czas opoznienia:   {round(total, 2)} ms")
        
        self.yolo_times.clear()
        self.logic_times.clear()
        self.comm_times.clear()
