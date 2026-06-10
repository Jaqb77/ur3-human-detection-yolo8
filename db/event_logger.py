from openpyxl import Workbook
from openpyxl.reader.excel import load_workbook
import os

class excel_logger:
    
    def __init__(self):
        self.headers = [
            "id",
            "status",
            "detection_start_time",
            "detection_end_time",
            "duration_s",
            "average_model_accuracy",
            "average_fps",
            "min_distance_to_robot_mm",
            "actual_robot_speed_scale",
            "camera_id"
        ]

    def init_check(self, filename):
        if os.path.exists(filename):
            wb = load_workbook(filename)
            ws = wb.active 
        else:
            wb = Workbook() 
            ws = wb.active
            ws.append(self.headers)
            wb.save(filename)
    

