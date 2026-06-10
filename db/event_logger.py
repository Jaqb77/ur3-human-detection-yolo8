import time
import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.reader.excel import load_workbook

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
        self.buffer = []
        self.next_id = 1

    def init_check(self, filename):
        if os.path.exists(filename):
            wb = load_workbook(filename)
            ws = wb.active

            if ws.max_row > 1:
                last_id = ws.cell(row=ws.max_row, column=1).value
                self.next_id = int(last_id) + 1
            else:
                self.next_id = 1

        else:
            wb = Workbook() 
            ws = wb.active
            ws.append(self.headers)
            wb.save(filename)
            self.next_id = 1

    def add_to_buffer(self, row):
        self.buffer.append(row)

    def save_buffer(self, filename):
        if not self.buffer:
            return

        if os.path.exists(filename):
            wb = load_workbook(filename)
            ws = wb.active 

            for row in self.buffer:
                ws.append(row)
                
            wb.save(filename)
            self.buffer.clear() 