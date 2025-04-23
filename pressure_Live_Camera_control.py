import serial
import cv2
import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import random
import pandas as pd
from datetime import datetime
import os
from pathlib import Path

# تحديد مجلد التنزيلات كمسار الحفظ
downloads_folder = str(Path.home() / "Downloads")
excel_filename = os.path.join(downloads_folder, "arduino_data_log.xlsx")
last_save_time = time.time()
buffer = []

# الاتصال بالأردوينو
arduino = serial.Serial('COM3', 9600, timeout=1)
time.sleep(2)

# الكاميرا
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("فشل في فتح الكاميرا!")
    exit()

# إعدادات الرسومات
plt.style.use('ggplot')
fig = plt.figure(figsize=(16, 9))
gs = fig.add_gridspec(3, 4)

# بث الفيديو
ax_cam = fig.add_subplot(gs[:, :2])
ax_cam.axis('off')
cam_im = ax_cam.imshow(np.zeros((480, 640, 3), dtype=np.uint8))

# رسم الفولت
ax_volt = fig.add_subplot(gs[0, 2:])
ax_volt.set_title("Voltage (Live)")
ax_volt.set_ylim(0, 50)
volt_line, = ax_volt.plot([], [], color='orange')
volt_data = deque(maxlen=100)

# رسم الخطوات
ax_steps = fig.add_subplot(gs[1, 2:])
ax_steps.set_title("Steps Over Time")
ax_steps.set_ylim(0, 200)
step_line, = ax_steps.plot([], [], color='blue')
step_data = deque(maxlen=100)

# أفضل المناطق
ax_zones = fig.add_subplot(gs[2, 2:])
ax_zones.set_title("Top Activity Zones")
ax_zones.axis('off')
zone_texts = [ax_zones.text(0.1, 0.8 - i * 0.2, '', fontsize=12) for i in range(3)]

# نقاط النشاط
activity_points = deque(maxlen=1000)
use_camera_background = True

# حالة الخروج
exit_flag = [False]  # نستخدم قائمة عشان نقدر نغيرها من داخل الدالة

def parse_arduino_line(line):
    parts = line.split(',')
    step = int(parts[0].split(':')[1])
    volt = float(parts[1].split(':')[1])
    direction = parts[2].split(':')[1]
    return step, volt, direction

def map_direction_to_point(direction, width, height):
    offset = 40
    if direction == "LEFT":
        return (random.randint(0, width // 3), height // 2 + random.randint(-offset, offset))
    elif direction == "RIGHT":
        return (random.randint(2 * width // 3, width), height // 2 + random.randint(-offset, offset))
    elif direction == "FORWARD":
        return (width // 2 + random.randint(-offset, offset), random.randint(0, height // 3))
    elif direction == "BACKWARD":
        return (width // 2 + random.randint(-offset, offset), random.randint(2 * height // 3, height))
    elif direction == "DOWN":
        return (width // 2 + random.randint(-offset, offset), height // 2 + random.randint(-offset, offset))
    else:
        return None

def create_apl_layer(points, shape):
    apl = np.zeros((shape[0], shape[1]), dtype=np.float32)
    for x, y, _ in points:
        cv2.circle(apl, (x, y), 30, 1.0, -1)
    apl = cv2.GaussianBlur(apl, (0, 0), sigmaX=12, sigmaY=12)
    apl_uint8 = np.uint8(np.clip(apl * 255, 0, 255))
    apl_colored = cv2.applyColorMap(apl_uint8, cv2.COLORMAP_JET)
    apl_colored = cv2.cvtColor(apl_colored, cv2.COLOR_BGR2RGB)
    apl_alpha = (apl * 0.6).clip(0, 1)
    apl_colored_float = apl_colored.astype(np.float32) / 255.0
    apl_masked = (apl_colored_float * apl_alpha[..., None]) * 255
    apl_masked = apl_masked.astype(np.uint8)
    return apl_masked, apl

def get_top_zones(apl_gray, count=3):
    _, maxVal, _, _ = cv2.minMaxLoc(apl_gray)
    threshold = maxVal * 0.6
    _, thresh = cv2.threshold(apl_gray, threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    centers = []
    for cnt in contours:
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            centers.append((cx, cy))
    centers = sorted(centers, key=lambda c: apl_gray[c[1], c[0]], reverse=True)
    return centers[:count]

step = 0
volt = 0
frame = np.zeros((480, 640, 3), dtype=np.uint8)

def update(_):
    global step, volt, frame, last_save_time, buffer

    if exit_flag[0]:  # تحقق من طلب الخروج
        plt.close()
        return

    now = time.time()

    if arduino.in_waiting:
        try:
            line = arduino.readline().decode('utf-8').strip()
            step, volt, direction = parse_arduino_line(line)

            print(f"الخطوات: {step}, الفولت: {volt:.2f}, الاتجاه: {direction}")

            buffer.append([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), step, volt, direction])

            if volt > 5:
                _, frame = cap.read()
                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    point = map_direction_to_point(direction, frame.shape[1], frame.shape[0])
                    if point:
                        activity_points.append((point[0], point[1], now))
        except Exception as e:
            print(f"خطأ أثناء قراءة البيانات: {e}")

    # حفظ البيانات في Excel كل دقيقة
    if time.time() - last_save_time >= 60 and buffer:
        try:
            df = pd.DataFrame(buffer, columns=["Time", "Steps", "Voltage", "Direction"])
            if not os.path.isfile(excel_filename):
                df.to_excel(excel_filename, index=False)
            else:
                with pd.ExcelWriter(excel_filename, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                    start_row = pd.read_excel(excel_filename).shape[0]
                    df.to_excel(writer, index=False, header=False, startrow=start_row)
            print(">> تم حفظ البيانات في ملف Excel.")
            buffer.clear()
            last_save_time = time.time()
        except Exception as e:
            print(f"خطأ أثناء حفظ Excel: {e}")

    recent = deque([pt for pt in activity_points if now - pt[2] <= 5], maxlen=1000)
    activity_points.clear()
    activity_points.extend(recent)

    apl_layer, apl_gray = create_apl_layer(activity_points, frame.shape[:2])
    background = frame if use_camera_background else np.full_like(frame, (144, 238, 144), dtype=np.uint8)
    blended = cv2.addWeighted(background, 0.7, apl_layer, 0.8, 0)
    cam_im.set_data(blended)

    volt_data.append(volt)
    volt_line.set_data(range(len(volt_data)), volt_data)
    ax_volt.set_xlim(0, len(volt_data))

    step_data.append(step)
    step_line.set_data(range(len(step_data)), step_data)
    ax_steps.set_xlim(0, len(step_data))

    zones = get_top_zones(apl_gray)
    for i in range(3):
        if i < len(zones):
            x, y = zones[i]
            zone_texts[i].set_text(f"Zone {i+1}: x={x}, y={y}")
        else:
            zone_texts[i].set_text("")

def on_key(event):
    global use_camera_background

    if event.key == 'c':
        use_camera_background = not use_camera_background
        print(f"الوضع: {'كاميرا' if use_camera_background else 'خلفية موحدة'}")

    elif event.key == 'q':
        print("جاري إنهاء البرنامج...")

        # حفظ أي بيانات متبقية قبل الخروج
        if buffer:
            try:
                df = pd.DataFrame(buffer, columns=["Time", "Steps", "Voltage", "Direction"])
                if not os.path.isfile(excel_filename):
                    df.to_excel(excel_filename, index=False)
                else:
                    with pd.ExcelWriter(excel_filename, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                        start_row = pd.read_excel(excel_filename).shape[0]
                        df.to_excel(writer, index=False, header=False, startrow=start_row)
                print(">> تم حفظ البيانات الأخيرة.")
            except Exception as e:
                print(f"خطأ أثناء حفظ البيانات الأخيرة: {e}")

        # إغلاق الكاميرا والأردوينو
        cap.release()
        arduino.close()
        exit_flag[0] = True  # استخدم العلم لإغلاق الرسوم المتحركة

fig.canvas.mpl_connect('key_press_event', on_key)

ani = animation.FuncAnimation(fig, update, interval=500)
plt.tight_layout()

print(f"يتم حفظ ملف Excel هنا: {excel_filename}")

plt.show()