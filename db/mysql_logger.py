import time
from datetime import datetime
import mysql.connector
import config

class mysql_logger:
    
    def __init__(self):
        self.is_active = False          
        self.start_time = 0.0           
        self.start_timestamp_str = ""  
        
        self.session_accuracies = []    
        self.session_fps = []           
        self.session_inference_times = [] 
        
        self.zone_priority = {"NONE": 0, "GREEN": 1, "YELLOW": 2, "RED": 3}
        self.highest_zone = "NONE"
        
        self.db_conn = None
        self.cursor = None

    def init_check(self):
        try:
            temp_conn = mysql.connector.connect(
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD
            )
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.DB_NAME}")
            temp_cursor.close()
            temp_conn.close()

            self.db_conn = mysql.connector.connect(
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME
            )
            self.cursor = self.db_conn.cursor()

            create_table_query = """
            CREATE TABLE IF NOT EXISTS detections_v2 (
                id_detection INT AUTO_INCREMENT PRIMARY KEY,
                id_camera INT,
                status VARCHAR(50),
                violated_zone VARCHAR(50),
                ai_model VARCHAR(50),
                hardware_setup VARCHAR(50),
                detection_start_time DATETIME,
                detection_end_time DATETIME,
                duration_s DOUBLE,
                average_fps DOUBLE,
                average_model_accuracy DOUBLE,
                average_inference_time_ms DOUBLE,
                tcp_x DOUBLE,
                tcp_y DOUBLE,
                tcp_z DOUBLE
            );
            """
            self.cursor.execute(create_table_query)
            self.db_conn.commit()
            print("[MySQL] Połączenie stabilne. Tabela 'detections_v2' gotowa.")
        except Exception as e:
            print(f"[MySQL][ERROR] Błąd inicjalizacji bazy danych: {e}")
            self.db_conn = None

    def acquisition(self, detection_bool, camera_id, current_acc, model_name, hardware_setup, current_fps, current_inf_time, robot_x, robot_y, robot_z, active_zone_name="NONE"):
        
        if detection_bool and not self.is_active:
            self.is_active = True
            self.start_timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.start_time = time.time()
            self.highest_zone = active_zone_name  
            self.session_accuracies.append(current_acc)
            self.session_fps.append(current_fps)
            self.session_inference_times.append(current_inf_time)

        elif detection_bool and self.is_active:
            if self.zone_priority.get(active_zone_name, 0) > self.zone_priority.get(self.highest_zone, 0):
                self.highest_zone = active_zone_name
                
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

            if self.db_conn and self.db_conn.is_connected():
                try:
                    sql_query = """
                    INSERT INTO detections_v2 (
                        id_camera, status, violated_zone, ai_model, hardware_setup, 
                        detection_start_time, detection_end_time, duration_s, 
                        average_fps, average_model_accuracy, average_inference_time_ms, 
                        tcp_x, tcp_y, tcp_z
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    values = (
                        camera_id, status, self.highest_zone, model_name, hardware_setup,
                        self.start_timestamp_str, end_timestamp_str, round(duration_s, 2),
                        round(avg_fps, 1), round(avg_accuracy, 2), round(avg_inference, 1),
                        robot_x, robot_y, robot_z
                    )
                    self.cursor.execute(sql_query, values)
                    self.db_conn.commit()
                    print(f"[MySQL] Zapisano incydent w strefie {self.highest_zone}. ID: {self.cursor.lastrowid}")
                except Exception as e:
                    print(f"[MySQL][ERROR] Błąd instrukcji INSERT: {e}")

            self.is_active = False
            self.highest_zone = "NONE"
            self.session_accuracies.clear()
            self.session_fps.clear()
            self.session_inference_times.clear()

    def close_connection(self):
        if self.db_conn and self.db_conn.is_connected():
            self.cursor.close()
            self.db_conn.close()
            print("[MySQL] Połączenie z bazą danych zamknięte bezpiecznie.")