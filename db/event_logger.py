import time
import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.reader.excel import load_workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

class excel_logger:
    
    def __init__(self):
        self.headers = [
            "id_detection",
            "id_camera",
            "status",
            "ai_model",
            "hardware_setup",
            "detection_start_time",
            "detection_end_time",
            "duration_s",
            "average_fps",
            "average_model_accuracy",
            "average_inference_time_ms",
            "tcp_x",
            "tcp_y",
            "tcp_z"
        ]

        self.buffer = []

        self.is_active = False          
        self.start_time = 0.0           
        self.start_timestamp_str = ""  
        self.next_id = 1
        
        self.session_accuracies = []    
        self.session_fps = []           
        self.session_inference_times = [] 

    def init_check(self, filename):
        if os.path.exists(filename):
            wb = load_workbook(filename)
            ws = wb.active

            if ws.max_row > 1:
                last_id = ws.cell(row = ws.max_row, column = 1).value
                self.next_id = int(last_id) + 1
            else:
                self.next_id = 1
        else:
            wb = Workbook() 
            ws = wb.active
            ws.title = "datalogs"
            ws.append(self.headers)
            self._apply_formatting(ws)

            wb.save(filename)
            self.next_id = 1

    def add_to_buffer(self, row):
        self.buffer.append(row)
    
    def save_buffer(self, filename):
        if not self.buffer:
            return
        
        wb = load_workbook(filename)
        ws = wb.active

        for row in self.buffer:
            ws.append(row)
            
        self._apply_formatting(ws)
            
        try:
            wb.save(filename)   
            print(f"Pomyślnie zapisano dane do głównego pliku: {filename}")
        except PermissionError:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base, ext = os.path.splitext(filename)
            backup_filename = f"{base}_BACKUP_{timestamp}{ext}"
            
            print(f"\n[ALERT] Plik {filename} jest otwarty w innym programie!")
            print(f"[ZABEZPIECZENIE] Dane zostały uratowane i zapisane w: {backup_filename}\n")
            
            wb.save(backup_filename)
            
        self.buffer.clear()
        
    def _apply_formatting(self, ws):
        font_naglowek = Font(name="Calibri", size=11, bold=True)
        wyrownanie_srodek = Alignment(horizontal="center", vertical="center")

        for cell in ws[1]:
            cell.font = font_naglowek
            cell.alignment = wyrownanie_srodek

        if ws.max_row > 1:
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(self.headers)):
                for cell in row:
                    cell.alignment = wyrownanie_srodek

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
    
    def acquisition(self, detection_bool, camera_id, current_acc, model_name, hardware_setup, current_fps, current_inf_time, robot_x, robot_y, robot_z):

        if detection_bool and not self.is_active:
            self.is_active = True
            self.start_timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.start_time = time.time()
            self.session_accuracies.append(current_acc)
            self.session_fps.append(current_fps)
            self.session_inference_times.append(current_inf_time)

        elif detection_bool and self.is_active:
            self.session_accuracies.append(current_acc)
            self.session_fps.append(current_fps)
            self.session_inference_times.append(current_inf_time)

        elif not detection_bool and self.is_active:
            duration_s = time.time() - self.start_time
            end_timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")              
            
            avg_accuracy = sum(self.session_accuracies) / len(self.session_accuracies) if self.session_accuracies else current_acc
            avg_fps = sum(self.session_fps) / len(self.session_fps) if self.session_fps else current_fps
            avg_inference = sum(self.session_inference_times) / len(self.session_inference_times) if self.session_inference_times else current_inf_time
            
            if duration_s < 1.0:
                status = "requires checking"
            else:
                status = "detection"

            row = [
                self.next_id,
                camera_id,
                status,
                model_name,
                hardware_setup,
                self.start_timestamp_str,
                end_timestamp_str,
                round(duration_s, 2),
                round(avg_fps, 1),
                round(avg_accuracy, 2),
                round(avg_inference, 1),
                robot_x,
                robot_y,
                robot_z
            ]
            
            self.add_to_buffer(row)
            self.next_id += 1
            
            self.is_active = False
            self.session_accuracies.clear()
            self.session_fps.clear()
            self.session_inference_times.clear()