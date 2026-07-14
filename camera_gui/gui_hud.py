import cv2
import numpy as np
from datetime import datetime

# HUD interface styling dictionary
HUD_STYLE = {
    "panel_opacity": 0.55,           
    "panel_height": 62,              
    
    # BGR Colors for safety zones
    "color_none": (76, 209, 55),     
    "color_green": (76, 209, 55),    
    "color_yellow": (0, 204, 255),   
    "color_red": (46, 46, 255),      
    
    # Fonts and text styling
    "font_face": cv2.FONT_HERSHEY_SIMPLEX,
    "font_scale_main": 0.5,
    "font_scale_badge": 0.55,
    "font_thickness": 2,
    
    # Robot speed progress bar dimensions
    "speed_bar_width": 180,
    "speed_bar_height": 10,
}

def draw_hud(frame, current_fps, current_inf_time, robot_speed_percent, active_zone_name, current_frame_zone, is_hold):
    """
    Renders a professional, semi-transparent dashboard HUD on the video frame.
    """
    h, w, _ = frame.shape
    p_h = HUD_STYLE["panel_height"]
    opacity = HUD_STYLE["panel_opacity"]
    
    # 1. Semi-transparent upper glassmorphism panel
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, p_h), (25, 25, 25), -1)
    cv2.addWeighted(overlay, opacity, frame, 1.0 - opacity, 0, frame)
    
    # 2. Get active zone color for the indicators
    zone_colors = {
        "NONE": HUD_STYLE["color_none"],
        "GREEN": HUD_STYLE["color_green"],
        "YELLOW": HUD_STYLE["color_yellow"],
        "RED": HUD_STYLE["color_red"]
    }
    current_color = zone_colors.get(active_zone_name, HUD_STYLE["color_none"])
    
    # Colored bottom panel border
    cv2.line(frame, (0, p_h), (w, p_h), current_color, 2)
    
    # 3. Status Badge (Safety Status Tag)
    badge_x1, badge_y1 = 15, 14
    badge_x2, badge_y2 = 135, 48
    cv2.rectangle(frame, (badge_x1, badge_y1), (badge_x2, badge_y2), current_color, -1)
    
    # Define status text label
    if is_hold and active_zone_name != "NONE":
        status_str = "HOLD"
    else:
        status_texts = {
            "NONE": "SAFE",
            "GREEN": "ZONE (G)",
            "YELLOW": "ZONE (Y)",
            "RED": "ZONE (R)"
        }
        status_str = status_texts.get(active_zone_name, "SAFE")
        
    # Align and center text inside the badge box
    text_size = cv2.getTextSize(status_str, HUD_STYLE["font_face"], HUD_STYLE["font_scale_badge"], HUD_STYLE["font_thickness"])[0]
    tx = badge_x1 + int((badge_x2 - badge_x1 - text_size[0]) / 2)
    ty = badge_y1 + int((badge_y2 - badge_y1 + text_size[1]) / 2)
    
    # Contrast color adjustment (dark text on yellow, white text on green/red)
    text_color = (0, 0, 0) if active_zone_name == "YELLOW" else (255, 255, 255)
    cv2.putText(frame, status_str, (tx, ty), HUD_STYLE["font_face"], HUD_STYLE["font_scale_badge"], text_color, HUD_STYLE["font_thickness"], cv2.LINE_AA)
    
    # 4. Cobot speed progress bar
    bar_x = 165
    bar_y = 34
    bar_w = HUD_STYLE["speed_bar_width"]
    bar_h = HUD_STYLE["speed_bar_height"]
    
    # Progress bar background
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
    
    # Progress bar speed fill
    fill_w = int(bar_w * (robot_speed_percent / 100.0))
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), current_color, -1)
    
    # Text above the progress bar
    speed_text = f"COBOT SPEED: {robot_speed_percent}%"
    cv2.putText(frame, speed_text, (bar_x, bar_y - 7), HUD_STYLE["font_face"], 0.4, (235, 235, 235), 1, cv2.LINE_AA)
    
    # 5. Technical system metrics (right side of the panel)
    metrics_x = w - 195
    metrics_y_top = 26
    metrics_y_bottom = 46
    
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fps_str = f"FPS: {round(current_fps, 1)}"
    yolo_str = f"YOLO: {round(current_inf_time, 1)} ms"
    
    cv2.putText(frame, time_str, (metrics_x, metrics_y_top), HUD_STYLE["font_face"], 0.4, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{fps_str}  |  {yolo_str}", (metrics_x, metrics_y_bottom), HUD_STYLE["font_face"], 0.4, (200, 200, 200), 1, cv2.LINE_AA)
    
    return frame
