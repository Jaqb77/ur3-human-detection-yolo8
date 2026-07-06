import time
import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.reader.excel import load_workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
import cv2  
import pickle  

class excel_logger:
    
    def __init__(self):
        self.headers = [
            "id_detection",
            "id_camera",
            "status",
            "violated_zone",
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
        self.image_buffer = {}          
        self.detection_frame = None     

        self.is_active = False          
        self.start_time = 0.0           
        self.start_timestamp_str = ""  
        self.next_id = 1
        
        self.session_accuracies = []    
        self.session_fps = []           
        self.session_inference_times = [] 
        
        self.zone_priority = {"NONE": 0, "GREEN": 1, "YELLOW": 2, "RED": 3}
        self.highest_zone = "NONE"
        
        self.db_dir = os.path.dirname(os.path.abspath(__file__))

    def _get_absolute_path(self, filename):
        if not os.path.isabs(filename) and os.path.basename(filename) == filename:
            return os.path.join(self.db_dir, filename)
        return filename

    def init_check(self, filename):
        filename = self._get_absolute_path(filename)
        cache_path = filename + ".cache"
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                
                if os.path.exists(filename):
                    wb = load_workbook(filename)
                    ws = wb.active
                else:
                    wb = Workbook()
                    ws = wb.active
                    ws.title = "datalogs"
                    ws.append(self.headers)
                    self._apply_formatting(ws)

                for row in cached_data['buffer']:
                    ws.append(row)
                    
                self._apply_formatting(ws)
                wb.save(filename)
                
                if cached_data['image_buffer']:
                    base_dir = os.path.dirname(filename)
                    folder_name, _ = os.path.splitext(os.path.basename(filename))
                    target_folder = os.path.join(base_dir, folder_name)
                    os.makedirs(target_folder, exist_ok=True)
                    for det_id, (frame, safe_timestamp) in cached_data['image_buffer'].items():
                        img_filename = f"{det_id} {safe_timestamp}.jpg"
                        img_path = os.path.join(target_folder, img_filename)
                        cv2.imwrite(img_path, frame)
                
                os.remove(cache_path)
                print("[Excel] Pomyślnie przywrócono i zapisano zaległe dane z pliku cache.")
            except PermissionError:
                print("\n[Excel][WARNING] Główny plik Excel jest nadal otwarty. Dane z poprzedniej sesji pozostają zabezpieczone w pliku cache.\n")
            except Exception as e:
                print(f"[Excel][ERROR] Nie udało się odzyskać danych z pliku cache: {e}")

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
        
        filename = self._get_absolute_path(filename)
        cache_path = filename + ".cache"
        
        try:
            wb = load_workbook(filename)
            ws = wb.active

            for row in self.buffer:
                ws.append(row)
                
            self._apply_formatting(ws)
            wb.save(filename)   
            print(f"Pomyślnie zapisano dane do głównego pliku: {filename}")
            
            if self.image_buffer:
                base_dir = os.path.dirname(filename)
                folder_name, _ = os.path.splitext(os.path.basename(filename))
                target_folder = os.path.join(base_dir, folder_name)
                os.makedirs(target_folder, exist_ok=True)
                
                for det_id, (frame, safe_timestamp) in self.image_buffer.items():
                    img_filename = f"{det_id} {safe_timestamp}.jpg"
                    img_path = os.path.join(target_folder, img_filename)
                    cv2.imwrite(img_path, frame)

            self.buffer.clear()
            self.image_buffer.clear()

        except PermissionError:
            print(f"\n[ALERT] Zapis zablokowany. Plik {os.path.basename(filename)} jest otwarty w innym programie!")
            try:
                existing_buffer = []
                existing_images = {}
                if os.path.exists(cache_path):
                    with open(cache_path, 'rb') as f:
                        old_cache = pickle.load(f)
                        existing_buffer = old_cache.get('buffer', [])
                        existing_images = old_cache.get('image_buffer', {})
                
                combined_buffer = existing_buffer + self.buffer
                existing_images.update(self.image_buffer)
                with open(cache_path, 'wb') as f:
                    pickle.dump({'buffer': combined_buffer, 'image_buffer': existing_images}, f)
            except Exception as e:
                pass
        
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
    
    def acquisition(self, detection_bool, camera_id, current_acc, model_name, hardware_setup, current_fps, current_inf_time, robot_x, robot_y, robot_z, active_zone_name="NONE", frame=None):

        if detection_bool and not self.is_active:
            self.is_active = True
            self.start_timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.start_time = time.time()
            self.highest_zone = active_zone_name
            if frame is not None:
                self.detection_frame = frame.copy() 
            self.session_accuracies.append(current_acc)
            self.session_fps.append(current_fps)
            self.session_inference_times.append(current_inf_time)

        elif detection_bool and self.is_active:
            if self.zone_priority.get(active_zone_name, 0) > self.zone_priority.get(self.highest_zone, 0):
                self.highest_zone = active_zone_name
                if frame is not None:
                    self.detection_frame = frame.copy() 
            
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

            if self.detection_frame is not None:
                safe_timestamp = self.start_timestamp_str.replace(":", "-")
                self.image_buffer[self.next_id] = (self.detection_frame, safe_timestamp)

            row = [
                self.next_id,
                camera_id,
                status,
                self.highest_zone,
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
            self.highest_zone = "NONE"
            self.detection_frame = None 
            self.session_accuracies.clear()
            self.session_fps.clear()
            self.session_inference_times.clear()