import os, time, math, ctypes, threading
import numpy as np
import tkinter as tk
from ctypes import wintypes
from enum import Enum

SHOW_MAX_HITS = 5
BASE_WINDOW_RESOLUTION = (1768, 992)
BASE_METER_2_PIXEL = 2.271
GRAVITY = 9.81

global_source = None
global_target = None
global_mid = None
best_hit = None
offx = 500
offy = 500
global_tp = None
global_rect = None

global_hits = []
current_index = 0
handle = None
mirror_mode = False

class Mode(Enum):
    ANGLE = 1
    VELOCITY = 2

class Hit:
    def __init__(self, velocity, angle):
        self.velocity = velocity
        self.angle = angle
    def get_velocity(self):
        return self.velocity
    def get_angle(self):
        return self.angle
    def __str__(self):
        return f"({self.velocity},{self.angle})"

def get_fraction(val):
    frac = abs(val - int(val))
    if frac > 0.5:
        return 1.0 - frac
    return frac

def calc_launch_angle(v, x, y):
    v = float(v)
    x = x / BASE_METER_2_PIXEL
    y = y / BASE_METER_2_PIXEL
    s = (v**4) - GRAVITY*(GRAVITY*(x**2) + 2*y*(v**2))
    if s < 0:
        return None
    try:
        o = math.atan((v**2 + math.sqrt(s)) / (GRAVITY*x))
    except:
        return None
    if math.isnan(o):
        return None
    return math.degrees(o)

def calc_launch_velocity(o, x, y):
    x = x / BASE_METER_2_PIXEL
    y = y / BASE_METER_2_PIXEL
    t = math.tan(math.radians(o))
    a = -GRAVITY*(x**2)*(1 + t*t)
    b = 2*(y - x*t)
    if b == 0:
        return None
    try:
        v = math.sqrt(a / b)
    except:
        return None
    if math.isnan(v) or v > 100:
        return None
    return v

def calc_launch_angles(x, y):
    angles = []
    for v in range(1, 101):
        o = calc_launch_angle(v, x, y)
        if o is not None:
            angles.append((v, o))
    angles.sort(key=lambda a: get_fraction(a[1]))
    return [Hit(int(v), int(round(o))) for v, o in angles]

def calc_launch_velocities(x, y):
    velocities = []
    for o in range(-90, 91):
        v = calc_launch_velocity(o, x, y)
        if v is not None:
            velocities.append((v, float(o)))
    velocities.sort(key=lambda a: get_fraction(a[0]))
    return [Hit(int(round(v)), int(round(o))) for v, o in velocities]

class VK(Enum):
    Key1 = 1
    Key2 = 2
    Key3 = 3
    Key4 = 4
    Key5 = 5
    KeyR = 6
    KeyT = 7

class Rect:
    def __init__(self, width, height):
        self.width = width
        self.height = height
    def get_width(self):
        return self.width
    def get_height(self):
        return self.height

class Cursor:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def get_x(self):
        return self.x
    def get_y(self):
        return self.y

class Handle:
    def is_key_pressed(self, vk):
        raise NotImplementedError
    def get_window_rect(self):
        raise NotImplementedError
    def get_mouse_position_in_window(self):
        raise NotImplementedError

class WinHandle(Handle):
    def __init__(self, hwnd):
        self.hwnd = hwnd
    def is_key_pressed(self, vk):
        if vk == VK.Key1:
            key_code = 0x31
        elif vk == VK.Key2:
            key_code = 0x32
        elif vk == VK.Key3:
            key_code = 0x33
        elif vk == VK.Key4:
            key_code = 0x34
        elif vk == VK.Key5:
            key_code = 0x35
        elif vk == VK.KeyR:
            key_code = 0x52
        elif vk == VK.KeyT:
            key_code = 0x54
        else:
            return False
        state = ctypes.windll.user32.GetAsyncKeyState(key_code)
        return (state & 0x8000) != 0
    def get_window_rect(self):
        rect = wintypes.RECT()
        ctypes.windll.user32.GetClientRect(self.hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        return Rect(width, height)
    def get_mouse_position_in_window(self):
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        ctypes.windll.user32.ScreenToClient(self.hwnd, ctypes.byref(pt))
        return Cursor(pt.x, pt.y)

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", ctypes.c_ulong)
    ]

def get_primary_monitor_rect():
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    hmonitor = ctypes.windll.user32.MonitorFromPoint(wintypes.POINT(0, 0), 1)
    ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(mi))
    width = mi.rcMonitor.right - mi.rcMonitor.left
    height = mi.rcMonitor.bottom - mi.rcMonitor.top
    return Rect(width, height)

class PrimaryScreenHandle(Handle):
    def is_key_pressed(self, vk):
        if vk == VK.Key1:
            key_code = 0x31
        elif vk == VK.Key2:
            key_code = 0x32
        elif vk == VK.Key3:
            key_code = 0x33
        elif vk == VK.Key4:
            key_code = 0x34
        elif vk == VK.Key5:
            key_code = 0x35
        elif vk == VK.KeyR:
            key_code = 0x52
        elif vk == VK.KeyT:
            key_code = 0x54
        else:
            return False
        state = ctypes.windll.user32.GetAsyncKeyState(key_code)
        return (state & 0x8000) != 0
    def get_window_rect(self):
        return get_primary_monitor_rect()
    def get_mouse_position_in_window(self):
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return Cursor(pt.x, pt.y)

def get_handle_by_title(title):
    buf = ctypes.create_unicode_buffer(title)
    hwnd = ctypes.windll.user32.FindWindowW(None, buf)
    if hwnd == 0:
        return None
    return WinHandle(hwnd)

def find_shellshock_handle():
    if os.name != "nt":
        raise NotImplementedError("Linux/macOS not implemented")
    monitors = ctypes.windll.user32.GetSystemMetrics(80)
    if monitors > 1:
        return PrimaryScreenHandle()
    else:
        while True:
            time.sleep(0.1)
            h = get_handle_by_title("ShellShock Live")
            if h:
                return h

def scale_position(rect, cursor):
    ww = rect.get_width()
    wh = rect.get_height()
    if ww == 0 or wh == 0:
        return (0, 0)
    sx = BASE_WINDOW_RESOLUTION[0] / ww
    sy = BASE_WINDOW_RESOLUTION[1] / wh
    cx = cursor.get_x() * sx
    cy = (wh - cursor.get_y()) * sy
    return (cx, cy)

def translate_target_position_relativ_to_origin(rect, f, t):
    fs = scale_position(rect, f)
    ts = scale_position(rect, t)
    x = abs(fs[0] - ts[0])
    y = ts[1] - fs[1]
    return (x, y)

def into_angle_categories(hits):
    cats = {}
    for h in hits:
        cat = (h.get_angle() // 10) * 10
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(h)
    return cats

def format_hits(hits):
    return " ".join(str(hit) for hit in hits)

def print_hits(hits):
    print("[INFO] Results:")
    print("Best -> {}".format(format_hits(hits)))
    cats = into_angle_categories(hits)
    for c in sorted(cats.keys()):
        print("{} -> {}".format(c, format_hits(cats[c])))

def compute_trajectory(power, angle, horizontal_distance_base, vertical_distance_base, num_points=1000):
    g = GRAVITY
    theta = math.radians(angle)
    x_target_m = horizontal_distance_base / BASE_METER_2_PIXEL
    y_target_m = vertical_distance_base / BASE_METER_2_PIXEL
    a_coef = 0.5 * g
    b_coef = -power * math.sin(theta)
    c_coef = y_target_m
    discriminant = b_coef**2 - 4*a_coef*c_coef
    if discriminant < 0:
        t_end = x_target_m / (power * math.cos(theta))
    else:
        t1 = (-b_coef + math.sqrt(discriminant)) / (2*a_coef)
        t2 = (-b_coef - math.sqrt(discriminant)) / (2*a_coef)
        t_end = max(t1, t2)
        if t_end < 0:
            t_end = x_target_m / (power * math.cos(theta))
    t = np.linspace(0, t_end, num_points)
    x_m = power * math.cos(theta) * t
    y_m = power * math.sin(theta) * t - 0.5 * g * (t**2)
    x_pixels = x_m * BASE_METER_2_PIXEL
    y_pixels = y_m * BASE_METER_2_PIXEL
    return x_pixels, y_pixels

def recalc_from_mid():
    global best_hit, global_mid, global_source, global_target, global_tp, global_rect, global_hits, handle
    if handle is None:
        return
    if global_source is None or global_target is None or global_mid is None:
        return
    r = handle.get_window_rect()
    global_rect = r
    y0_metric = (r.get_height() - global_source.get_y()) / BASE_METER_2_PIXEL
    yT_metric = (r.get_height() - global_target.get_y()) / BASE_METER_2_PIXEL
    Q_metric = (r.get_height() - global_mid.get_y()) / BASE_METER_2_PIXEL
    best_candidate = None
    best_diff = float('inf')
    for hit in global_hits:
        v = hit.velocity
        theta = hit.angle
        sin_theta = math.sin(math.radians(theta))
        disc = (v*sin_theta)**2 - 2*GRAVITY*(y0_metric - yT_metric)
        if disc < 0:
            continue
        T = (v*sin_theta + math.sqrt(disc)) / GRAVITY
        y_mid_candidate = y0_metric + v*sin_theta*(T/2) - 0.5*GRAVITY*(T/2)**2
        diff = abs(y_mid_candidate - Q_metric)
        if diff < best_diff:
            best_diff = diff
            best_candidate = hit
    if best_candidate:
        best_hit = best_candidate
        print_hits([best_hit])

def recalc(mode, source, target):
    global global_tp, global_rect, global_hits, current_index, best_hit, global_mid, handle
    if handle is None:
        return
    r = handle.get_window_rect()
    tp = translate_target_position_relativ_to_origin(r, source, target)
    global_tp = tp
    global_rect = r
    if global_mid is not None:
        recalc_from_mid()
        return
    if mode == Mode.ANGLE:
        raw_hits = calc_launch_angles(tp[0], tp[1])
    else:
        raw_hits = calc_launch_velocities(tp[0], tp[1])
    if raw_hits:
        global_hits.clear()
        global_hits.extend(raw_hits)
        best_hit = global_hits[0]
        print_hits(global_hits)

def start_event_loop(h):
    global handle, mirror_mode
    handle = h
    global global_source, global_target, best_hit, offx, offy, global_tp, global_rect, global_mid
    global global_hits, current_index
    mode = Mode.VELOCITY
    s1 = s2 = s3 = s4 = s5 = False
    src = None
    tgt = None
    while True:
        time.sleep(0.01)
        k1 = handle.is_key_pressed(VK.Key1)
        k2 = handle.is_key_pressed(VK.Key2)
        k3 = handle.is_key_pressed(VK.Key3)
        k4 = handle.is_key_pressed(VK.Key4)
        k5 = handle.is_key_pressed(VK.Key5)
        if k1 and not s1:
            s1 = True
            src = handle.get_mouse_position_in_window()
            global_source = src
            offx = src.get_x()
            offy = src.get_y()
            global_mid = None
            print("[INFO] Position 1 set.")
            if src and global_target:
                recalc(mode, src, global_target)
        elif not k1:
            s1 = False
        if k2 and not s2:
            s2 = True
            tgt = handle.get_mouse_position_in_window()
            global_target = tgt
            global_mid = None
            print("[INFO] Position 2 set.")
            if global_source and tgt:
                recalc(mode, global_source, tgt)
        elif not k2:
            s2 = False
        if k3 and not s3:
            s3 = True
            mirror_mode = not mirror_mode
            print("[INFO] Mirror mode toggled to {}.".format(mirror_mode))
        elif not k3:
            s3 = False
        if k4 and not s4:
            s4 = True
            src = None
            tgt = None
            global_source = None
            global_target = None
            best_hit = None
            global_mid = None
            global_tp = None
            global_rect = None
            global_hits.clear()
            print("[INFO] Positions cleared.")
        elif not k4:
            s4 = False
        if k5 and not s5:
            s5 = True
            mode = Mode.VELOCITY if mode == Mode.ANGLE else Mode.ANGLE
            print("[INFO] Mode changed to '{}'.".format(mode.name))
        elif not k5:
            s5 = False

def run_visualization():
    global offx, offy, global_source, global_target, best_hit, global_tp, global_rect, global_mid
    global global_hits, current_index
    root = tk.Tk()
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", "white")
    root.state('zoomed')
    root.attributes("-fullscreen", True)
    canvas = tk.Canvas(root, bg='white', width=1920, height=1080)
    canvas.pack()
    dragging_circle = False
    drag_offset = 0
    center_circle = None
    def on_mouse_down(event):
        nonlocal dragging_circle, drag_offset, center_circle
        if center_circle is not None:
            cx, cy = center_circle
            radius = 8
            displayed_cy = cy + 50
            if (event.x - cx)**2 + (event.y - displayed_cy)**2 <= radius**2:
                dragging_circle = True
                drag_offset = event.y - displayed_cy
    def on_mouse_move(event):
        global global_mid
        nonlocal dragging_circle, drag_offset, center_circle
        if dragging_circle and global_source and global_target:
            new_displayed_y = event.y - drag_offset
            new_y = new_displayed_y - 50
            new_mid_x = (global_source.get_x() + global_target.get_x()) / 2
            if global_mid is not None:
                current_displayed_y = global_mid.get_y() + 50
                if new_displayed_y < current_displayed_y:
                    delta = current_displayed_y - new_displayed_y
                    new_displayed_y = current_displayed_y - delta * 0.5
                    new_y = new_displayed_y - 50
            global_mid = Cursor(new_mid_x, new_y)
            recalc_from_mid()
    def on_mouse_up(event):
        nonlocal dragging_circle
        dragging_circle = False
    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    def update_canvas():
        global global_mid
        nonlocal center_circle
        canvas.delete("all")
        if global_source:
            x1, y1 = global_source.get_x(), global_source.get_y()
            canvas.create_oval(x1 - 3, y1 - 3, x1 + 3, y1 + 3, fill="green")
        if global_target:
            x2, y2 = global_target.get_x(), global_target.get_y()
            canvas.create_oval(x2 - 3, y2 - 3, x2 + 3, y2 + 3, fill="orange")
        if global_source and global_target and best_hit and global_tp and global_rect:
            w = global_rect.get_width()
            h = global_rect.get_height()
            dx = global_target.get_x() - global_source.get_x()
            direction = 1 if dx >= 0 else -1
            tx, ty = compute_trajectory(best_hit.velocity, best_hit.angle, global_tp[0], global_tp[1])
            pts = []
            for i in range(len(tx)):
                ox = tx[i] * (w / BASE_WINDOW_RESOLUTION[0])
                oy = ty[i] * (h / BASE_WINDOW_RESOLUTION[1])
                xd = global_source.get_x() + direction * ox
                yd = global_source.get_y() - oy
                pts.append((xd, yd))
            if mirror_mode and global_source is not None:
                sy = global_source.get_y()
                pts = [(x, 2 * sy - y) for (x, y) in pts]
            if pts:
                if mirror_mode and global_source is not None:
                    sy = global_source.get_y()
                    pts[-1] = (global_target.get_x(), 2 * sy - global_target.get_y())
                else:
                    pts[-1] = (global_target.get_x(), global_target.get_y())
                fp = [c for p in pts for c in p]
                canvas.create_line(fp, width=2, fill='red')
                if global_mid is None:
                    mid_i = len(pts) // 2
                    mx, my = pts[mid_i]
                    mid_x = (global_source.get_x() + global_target.get_x()) / 2
                    global_mid = Cursor(mid_x, my)
                    center_circle = (mid_x, my)
                else:
                    mid_x = (global_source.get_x() + global_target.get_x()) / 2
                    mid_y = global_mid.get_y()
                    center_circle = (mid_x, mid_y)
                radius = 8
                canvas.create_oval(center_circle[0] - radius, (center_circle[1] + 50) - radius,
                                   center_circle[0] + radius, (center_circle[1] + 50) + radius,
                                   fill='blue')
                local_hit = best_hit
                if local_hit is not None:
                    angle_disp = -local_hit.angle if mirror_mode else local_hit.angle
                    tid = canvas.create_text(center_circle[0], center_circle[1] - 15,
                                             text=f"{local_hit.velocity}, {angle_disp}",
                                             fill="red",
                                             font=("Arial", 12))
                    b3 = canvas.bbox(tid)
                    if b3:
                        r3 = canvas.create_rectangle(b3, fill="black", outline="")
                        canvas.tag_raise(tid, r3)
                    tid2 = canvas.create_text(50, 30, anchor="w",
                                              text=f"{local_hit.velocity}, {angle_disp}",
                                              fill="red", font=("Arial", 20))
                    b4 = canvas.bbox(tid2)
                    if b4:
                        r4 = canvas.create_rectangle(b4, fill="black", outline="")
                        canvas.tag_raise(tid2, r4)
                    if global_hits:
                        cats = into_angle_categories(global_hits)
                        max_cat = max(cats.keys())
                        cat_text = "{} -> {}".format(max_cat, format_hits(cats[max_cat]))
                        tid3 = canvas.create_text(50, 60, anchor="w", text=cat_text, fill="red",
                                                  font=("Arial", 20))
                        b5 = canvas.bbox(tid3)
                        if b5:
                            r5 = canvas.create_rectangle(b5, fill="black", outline="")
                            canvas.tag_raise(tid3, r5)
        root.after(50, update_canvas)
    update_canvas()
    root.mainloop()

def main():
    print("[INFO] Searching ...")
    if os.name == "nt":
        h = find_shellshock_handle()
    else:
        raise NotImplementedError("Linux/macOS not implemented")
    print("[INFO] ShellShock found. Waiting for input ...")
    t = threading.Thread(target=start_event_loop, args=(h,), daemon=True)
    t.start()
    run_visualization()

if __name__ == "__main__":
    main()
