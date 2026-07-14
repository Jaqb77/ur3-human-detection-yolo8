import time
import os
import queue
import threading
import pickle
from datetime import datetime
import mysql.connector
import config

class mysql_logger:
    
    def __init__(self):
        self.log_queue = queue.Queue()
        
        self.is_active = False          
        self.start_time = 0.0           
        self.start_timestamp_str = ""  
        self.current_det_id = 1
        
        self.session_accuracies = []    
        self.session_fps = []           
        self.session_inference_times = [] 
        
        self.zone_priority = {"NONE": 0, "GREEN": 1, "YELLOW": 2, "RED": 3}
        self.highest_zone = "NONE"
        
        self.db_conn = None
        self.cursor = None
        
        self.db_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_path = os.path.join(self.db_dir, "mysql_logger.cache")
        
        # Wątek tła do asynchronicznego zapisu do MySQL
        self.worker_thread = threading.Thread(target=self._async_db_writer, daemon=True)
        self.worker_running = True
        self.worker_thread.start()

    def _connect_db(self):
        """
        Nawiązuje połączenie z bazą danych MySQL.
        """
        try:
            temp_conn = mysql.connector.connect(
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                connect_timeout=3
            )
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.DB_NAME}")
            temp_cursor.close()
            temp_conn.close()

            self.db_conn = mysql.connector.connect(
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                connect_timeout=3
            )
            self.cursor = self.db_conn.cursor()
            
            # Tworzenie tabeli jeśli nie istnieje (ze wsparciem dla ręcznie wstawianego id_detection)
            create_table_query = """
            CREATE TABLE IF NOT EXISTS detections_v2 (
                id_detection INT PRIMARY KEY,
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
            
            # Usunięcie AUTO_INCREMENT z istniejącej tabeli, jeśli została utworzona we wcześniejszej wersji skryptu
            try:
                self.cursor.execute("ALTER TABLE detections_v2 MODIFY id_detection INT;")
            except Exception:
                pass
                
            self.db_conn.commit()
            return True
        except Exception as e:
            print(f"[MySQL][ERROR] Błąd połączenia z bazą: {e}")
            self.db_conn = None
            self.cursor = None
            return False

    def init_check(self):
        # Inicjalizacja połączenia w wątku tła
        self.log_queue.put({"type": "init"})

    def acquisition(self, detection_bool, camera_id, current_acc, model_name, hardware_setup, current_fps, current_inf_time, robot_x, robot_y, robot_z, active_zone_name="NONE", det_id=1):
        """
        Zarządzanie stanem sesji detekcji.
        """
        if detection_bool and not self.is_active:
            self.is_active = True
            self.current_det_id = det_id
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
            
            if duration_s < config.MIN_DETECTION_TIME_S:
                status = "requires checking"
            else:
                status = "detection"

            # Wartości zawierają zsynchronizowany id_detection (det_id) jako pierwszy element
            values = (
                det_id, camera_id, status, self.highest_zone, model_name, hardware_setup,
                self.start_timestamp_str, end_timestamp_str, round(duration_s, 2),
                round(avg_fps, 1), round(avg_accuracy, 2), round(avg_inference, 1),
                robot_x, robot_y, robot_z
            )

            # Wrzucenie rekordu do zapisu asynchronicznego
            self.log_queue.put({
                "type": "insert",
                "values": values
            })

            self.is_active = False
            self.highest_zone = "NONE"
            self.session_accuracies.clear()
            self.session_fps.clear()
            self.session_inference_times.clear()

    def _save_to_local_cache(self, values):
        """
        Zapisuje rekordy do pliku cache, jeśli baza danych MySQL jest niedostępna.
        """
        cached_records = []
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'rb') as f:
                    cached_records = pickle.load(f)
            except:
                pass
        
        cached_records.append(values)
        
        try:
            with open(self.cache_path, 'wb') as f:
                pickle.dump(cached_records, f)
            print(f"[MySQL][CACHE] Zapisano rekord ID {values[0]} awaryjnie w lokalnym cache.")
        except Exception as e:
            print(f"[MySQL][ERROR] Nie udało się zapisać do pliku cache: {e}")

    def _process_cached_records(self):
        """
        Próbuje wstawić zaległe rekordy z cache do bazy MySQL po odzyskaniu połączenia.
        """
        if not os.path.exists(self.cache_path):
            return
        
        try:
            with open(self.cache_path, 'rb') as f:
                cached_records = pickle.load(f)
        except Exception as e:
            print(f"[MySQL][ERROR] Błąd odczytu cache: {e}")
            return

        if not cached_records:
            return

        print(f"[MySQL] Wykryto {len(cached_records)} zaległych rekordów w cache. Rozpoczynam synchronizację...")
        remaining_records = []
        
        for record in cached_records:
            try:
                sql_query = """
                INSERT INTO detections_v2 (
                    id_detection, id_camera, status, violated_zone, ai_model, hardware_setup, 
                    detection_start_time, detection_end_time, duration_s, 
                    average_fps, average_model_accuracy, average_inference_time_ms, 
                    tcp_x, tcp_y, tcp_z
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                # Sprawdzenie czy rekord już istnieje (zabezpieczenie przed kluczem głównym)
                check_query = "SELECT 1 FROM detections_v2 WHERE id_detection = %s"
                self.cursor.execute(check_query, (record[0],))
                if self.cursor.fetchone():
                    # Rekord już istnieje, ignorujemy
                    continue

                sql_insert = """
                INSERT INTO detections_v2 (
                    id_detection, id_camera, status, violated_zone, ai_model, hardware_setup, 
                    detection_start_time, detection_end_time, duration_s, 
                    average_fps, average_model_accuracy, average_inference_time_ms, 
                    tcp_x, tcp_y, tcp_z
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                self.cursor.execute(sql_insert, record)
                self.db_conn.commit()
                print(f"[MySQL][CACHE] Pomyślnie zsynchronizowano zaległy rekord ID: {record[0]}")
            except Exception as e:
                # Jeśli się nie uda, zachowujemy w cache
                remaining_records.append(record)
        
        if remaining_records:
            try:
                with open(self.cache_path, 'wb') as f:
                    pickle.dump(remaining_records, f)
            except:
                pass
        else:
            try:
                os.remove(self.cache_path)
                print("[MySQL][CACHE] Wszystkie zaległe rekordy zostały zsynchronizowane i plik cache został usunięty.")
            except:
                pass

    def _async_db_writer(self):
        """
        Główna pętla wątku tła.
        """
        while self.worker_running or not self.log_queue.empty():
            try:
                item = self.log_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if item is None:
                self.log_queue.task_done()
                break

            task_type = item["type"]

            if task_type == "init":
                if self._connect_db():
                    self._process_cached_records()
                self.log_queue.task_done()
                continue

            if task_type == "insert":
                values = item["values"]
                success = False
                
                # Próba zapisu z automatycznym ponownym łączeniem (max 2 próby)
                for attempt in range(2):
                    if not self.db_conn or not self.db_conn.is_connected():
                        if self._connect_db():
                            self._process_cached_records()

                    if self.db_conn and self.db_conn.is_connected():
                        try:
                            sql_query = """
                            INSERT IGNORE INTO detections_v2 (
                                id_detection, id_camera, status, violated_zone, ai_model, hardware_setup, 
                                detection_start_time, detection_end_time, duration_s, 
                                average_fps, average_model_accuracy, average_inference_time_ms, 
                                tcp_x, tcp_y, tcp_z
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            self.cursor.execute(sql_query, values)
                            self.db_conn.commit()
                            print(f"[MySQL] Zapisano incydent w strefie {values[3]}. ID: {values[0]}")
                            success = True
                            break
                        except Exception as e:
                            print(f"[MySQL][ERROR] Błąd instrukcji INSERT (próba {attempt+1}): {e}")
                            self.db_conn = None
                    time.sleep(0.5)

                if not success:
                    # Zapisujemy do lokalnego cache
                    self._save_to_local_cache(values)
                
                self.log_queue.task_done()

    def close_connection(self):
        if self.is_active:
            print("[MySQL][ZAMYKANIE] Wykryto aktywną detekcję. Wymuszam zapis rekordu...")
            avg_acc = sum(self.session_accuracies) / len(self.session_accuracies) if self.session_accuracies else 0.0
            avg_fps = sum(self.session_fps) / len(self.session_fps) if self.session_fps else 30.0
            avg_inf = sum(self.session_inference_times) / len(self.session_inference_times) if self.session_inference_times else 0.0
            self.acquisition(
                detection_bool=False,
                camera_id=config.CAMERA_ID,
                current_acc=avg_acc,
                model_name=config.MODEL_PATH_NAME,
                hardware_setup=config.HARDWARE_SETUP_STR,
                current_fps=avg_fps,
                current_inf_time=avg_inf,
                robot_x=0.0,
                robot_y=0.0,
                robot_z=0.0,
                active_zone_name=self.highest_zone,
                det_id=self.current_det_id
            )
        print("[MySQL] Zamykanie połączenia asynchronicznego...")
        self.worker_running = False
        self.log_queue.put(None)
        self.worker_thread.join()
        
        if self.db_conn and self.db_conn.is_connected():
            try:
                self.cursor.close()
                self.db_conn.close()
                print("[MySQL] Połączenie zamknięte bezpiecznie.")
            except Exception as e:
                print(f"[MySQL][ERROR] Błąd podczas zamykania połączenia: {e}")