from flask import Flask, render_template, request, jsonify, send_from_directory
import ctypes
import json
import os
import subprocess
import threading
import time
from ctypes import wintypes

import keyboard
import psutil
import webview
import atexit

app = Flask(__name__)

# Получение ID активного окна
user32 = ctypes.windll.user32
GetForegroundWindow = user32.GetForegroundWindow
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
GetWindowThreadProcessId.restype = wintypes.DWORD

class AndroidController:
    def __init__(self):
        self.log_messages = []
        self.config_file = "config.json"
        self.connection_type = "usb"
        self.adb_ip = "192.168.1.1"
        self.adb_port = "5555"
        self.scrcpy_fps = "60"
        self.scrcpy_process = None
        self.hotkeys = {
            'pause': 'num 0',
            'like': 'num 5',
            'pin': 'num 2',
            'scroll_up': 'num 3',
            'scroll_down': 'num 1',
        }

        self.load_hotkeys()
        self.load_connection_settings()
        self.load_coords()
        self.start_scrcpy()
        
        self.keyboard_listener_active = True
        self.start_keyboard_listener()
        self.start_scrcpy_output_thread()

    def load_hotkeys(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    if 'hotkeys' in config:
                        self.hotkeys.update(config['hotkeys'])
        except Exception as e:
            print(f"Ошибка загрузки горячих клавиш: {e}")

    def save_hotkeys(self):
        try:
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            
            config['hotkeys'] = self.hotkeys
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Ошибка сохранения горячих клавиш: {e}")
            return False

    def update_hotkey(self, action, key):
        self.hotkeys[action] = key.lower()
        if self.save_hotkeys():
            self.log_message(f"✅ Горячая клавиша для {action} изменена на {key}", 'success')
            return True
        return False

    def load_connection_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.connection_type = config.get("connection_type", "usb")
                    self.adb_ip = config.get("adb_ip", "192.168.1.1")
                    self.adb_port = config.get("adb_port", "5555")
                    self.scrcpy_fps = config.get("scrcpy_fps", "60")
        except Exception as e:
            print(f"Ошибка загрузки настроек подключения: {e}")
            self.connection_type = "wifi"
            self.adb_ip = "192.168.1.1"
            self.adb_port = "5555"
            self.scrcpy_fps = "60"

    def start_keyboard_listener(self):
        self.keyboard_thread = threading.Thread(target=self.keyboard_listener)
        self.keyboard_thread.daemon = True
        self.keyboard_thread.start()

    def start_scrcpy_output_thread(self):
        self.scrcpy_output_thread = threading.Thread(target=self.read_scrcpy_output)
        self.scrcpy_output_thread.daemon = True
        self.scrcpy_output_thread.start()

    def save_connection_settings(self, connection_type, adb_ip, adb_port, scrcpy_fps):
        try:
            if connection_type == "wifi":
                if not adb_ip or not adb_port:
                    raise ValueError("Для Wi-Fi подключения необходимо указать IP и порт")
                
                test_connect = subprocess.run(
                    ["adb", "connect", f"{adb_ip}:{adb_port}"], 
                    capture_output=True, 
                    text=True
                )
                if "unable to connect" in test_connect.stdout.lower():
                    raise ConnectionError(f"Не удалось подключиться к {adb_ip}:{adb_port}")
                
            self.connection_type = connection_type
            self.adb_ip = adb_ip
            self.adb_port = adb_port
            self.scrcpy_fps = scrcpy_fps
            
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            
            config.update({
                "connection_type": connection_type,
                "adb_ip": adb_ip,
                "adb_port": adb_port,
                "scrcpy_fps": scrcpy_fps
            })
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
                
            self.log_message("✅ Настройки подключения сохранены!", 'success')
            self.restart_scrcpy()
            return True
            
        except Exception as e:
            self.log_message(f"❌ Ошибка сохранения настроек: {str(e)}", 'error')
            return False

    def load_coords(self):
        default_coords = {
            "pause": "630 450",
            "like": "630 1020",
            "pin": "630 1180"
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    coords = json.load(f)
                    self.pause_coords = coords.get("pause", default_coords["pause"])
                    self.like_coords = coords.get("like", default_coords["like"])
                    self.pin_coords = coords.get("pin", default_coords["pin"])
            else:
                self.pause_coords = default_coords["pause"]
                self.like_coords = default_coords["like"]
                self.pin_coords = default_coords["pin"]
                
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            self.pause_coords = default_coords["pause"]
            self.like_coords = default_coords["like"]
            self.pin_coords = default_coords["pin"]
    
    def save_coords_to_file(self):
        try:
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            
            config.update({
                "pause": self.pause_coords,
                "like": self.like_coords,
                "pin": self.pin_coords
            })
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")
            return False

    def set_pointer_location(self, visible):
        value = "1" if visible else "0"
        self.adb_command(f"settings put system pointer_location {value}")

    def adb_command(self, command):
        try:
            if self.connection_type == "wifi":
                subprocess.run(["adb", "connect", f"{self.adb_ip}:{self.adb_port}"], check=True)
            
            subprocess.run(["adb", "shell"] + command.split(), check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Не удалось выполнить команду: {e}")
            return False
        except FileNotFoundError:
            print("ADB не найден. Убедитесь, что Android Debug Bridge установлен и добавлен в PATH.")
            return False
    def adb_screen(self):
        try:
            if self.connection_type == "wifi":
                subprocess.run(["adb", "connect", f"{self.adb_ip}:{self.adb_port}"], check=True)
            # subprocess.run(['adb', 'exec-out', 'screencap', '-p' > 'screen.png'], check=True)
            result = subprocess.run(
                ["adb", "exec-out", "screencap", "-p"],
                capture_output=True,
                check=True
            )

            with open("screen.png", "wb") as f:
                f.write(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            self.log_message(f"Не удалось выполнить команду: {e}", 'error')
            print(f"Не удалось выполнить команду: {e}")
            return False
        except FileNotFoundError:
            print("ADB не найден. Убедитесь, что Android Debug Bridge установлен и добавлен в PATH.")
            return False
    
    def log_message(self, message, tag='info'):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'tag': tag
        }
        self.log_messages.append(log_entry)
        if len(self.log_messages) > 50:
            self.log_messages.pop(0)
    
    def save_coords(self, pause_x, pause_y, like_x, like_y, pin_x, pin_y):
        self.pause_coords = f'{pause_x} {pause_y}'
        self.like_coords = f'{like_x} {like_y}'
        self.pin_coords = f'{pin_x} {pin_y}'
        
        if self.save_coords_to_file():
            self.adb_screen()
            self.log_message("✅ Координаты сохранены!", 'success')
            return True
        else:
            self.log_message("❌ Не удалось сохранить координаты в файл", 'error')
            return False

    def save_texture_info(self, texture_info):
        """Сохраняет информацию о текстуре в texture.json"""
        try:
            texture_data = {
                "texture": texture_info,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            }
            
            with open("texture.json", "w") as f:
                json.dump(texture_data, f, indent=4)
            
            self.log_message(f"✅ Информация о текстуре сохранена: {texture_info}", 'success')
            return True
        except Exception as e:
            self.log_message(f"❌ Ошибка сохранения информации о текстуре: {str(e)}", 'error')
            return False

    def perform_action(self, action):
        if get_active_process_name() == "scrcpy.exe":
            actions = {
                "pause": self.pause_action,
                "like": self.like_action,
                "pin": self.pin_action,
                "scroll_down": self.scroll_down_action,
                "scroll_up": self.scroll_up_action,
                "vol_plus": self.vol_plus_action,
                "vol_min": self.vol_min_action
            }
            action_func = actions.get(action)
            if action_func:
                return action_func()
        return False

    def pause_action(self):
        self.log_message("⏯️ Пауза/плей", 'pause')
        self.load_coords()
        return self.adb_command(f"input tap {self.pause_coords}")
    
    def like_action(self):
        self.load_coords()
        self.log_message("❤ Лайк", 'like')
        return self.adb_command(f"input tap {self.like_coords}")
    
    def pin_action(self):
        self.load_coords()
        self.log_message("⭐ Избранное", 'pin')
        return self.adb_command(f"input tap {self.pin_coords}")
    
    def scroll_up_action(self):
        self.log_message("⏩ Следующее видео", 'scroll')
        return self.adb_command("input swipe 500 1000 500 500 100")
    
    def scroll_down_action(self):
        self.log_message("⏪ Предыдущее видео", 'scroll')
        return self.adb_command("input swipe 500 500 500 1000 100")

    def vol_plus_action(self):
        self.log_message("🔊 Громкость ➕", 'vol')
        return self.adb_command("input keyevent KEYCODE_VOLUME_UP")

    def vol_min_action(self):
        self.log_message("🔈 Громкость ➖", 'vol')
        return self.adb_command("input keyevent KEYCODE_VOLUME_DOWN")

    def home_action(self):
        return self.adb_command("input keyevent KEYCODE_HOME")

    def back_action(self):
        return self.adb_command("input keyevent KEYCODE_BACK")
        
    def recent_action(self):
        return self.adb_command("input keyevent KEYCODE_APP_SWITCH")
    
    def keyboard_listener(self):
        time.sleep(3)
        self.log_message("✅ Служба запущена!", 'success')
        
        while self.keyboard_listener_active:
            try:
                for action, key in self.hotkeys.items():
                    if keyboard.is_pressed(key):
                        self.perform_action(action)
                        time.sleep(0.2)
                time.sleep(0.01)
            except Exception as e:
                self.log_message(f"Ошибка в keyboard_listener: {e}", 'error')

    def read_scrcpy_output(self):
        while hasattr(self, 'scrcpy_process') and self.scrcpy_process:
            output = self.scrcpy_process.stdout.readline() # type: ignore
            if output:
                output_line = output.strip()
                self.log_message(output_line, 'info')
                print(output_line)
                
                # Сохраняем информацию о текстуре
                if "INFO: Texture:" in output_line:
                    texture_info = output_line.split("INFO: Texture:")[1].strip()
                    self.save_texture_info(texture_info)
                    
            time.sleep(0.1)

    def start_scrcpy(self):
        try:
            if self.scrcpy_process and self.scrcpy_process.poll() is None:
                self.log_message("🔄 Scrcpy уже запущен", 'restart')
                return

            if self.connection_type == "usb":
                subprocess.run(["adb", "disconnect"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                command = ["scrcpy", f"--max-fps={self.scrcpy_fps}", "--stay-awake", "--turn-screen-off"]
                self.log_message("🔄 Запуск scrcpy (USB)...", 'restart')
            else:
                subprocess.run(["adb", "connect", f"{self.adb_ip}:{self.adb_port}"], check=True)
                command = ["scrcpy", f"--max-fps={self.scrcpy_fps}", f"--tcpip={self.adb_ip}:{self.adb_port}", "--stay-awake", "--turn-screen-off"]
                self.log_message(f"🔄 Запуск scrcpy (Wi-Fi {self.adb_ip}:{self.adb_port})...", 'restart')
            self.adb_screen()
            self.scrcpy_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
        except FileNotFoundError:
            self.log_message("scrcpy не найден. Убедитесь, что он установлен и добавлен в PATH.", 'error')
        except Exception as e:
            self.log_message(f"Ошибка запуска scrcpy: {str(e)}", 'error')

    def restart_scrcpy(self):
        self.log_message(f"🔄 Попытка перезапуска scrcpy ({self.connection_type})...", 'restart')
        if self.scrcpy_process:
            self.scrcpy_process.terminate()
            self.scrcpy_process.wait(timeout=1)
        
        if self.connection_type == "usb":
            subprocess.run(["adb", "disconnect"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["adb", "connect", f"{self.adb_ip}:{self.adb_port}"], check=True)
        self.start_scrcpy()
        return True

    def cleanup(self):
        self.keyboard_listener_active = False
        if hasattr(self, 'scrcpy_process') and self.scrcpy_process:
            self.scrcpy_process.terminate()

def get_active_process_name():
    hwnd = GetForegroundWindow()
    pid = wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        process = psutil.Process(pid.value)
        return process.name()
    except psutil.NoSuchProcess:
        return None

controller = AndroidController()

@app.route('/')
def index():
    scrcpy_running = controller.scrcpy_process and controller.scrcpy_process.poll() is None
    # По умолчанию выключаем отображение указателя
    controller.set_pointer_location(False)
    
    # Получаем координаты для отображения в центре окна
    pause_x, pause_y = controller.pause_coords.split()
    like_x, like_y = controller.like_coords.split()
    pin_x, pin_y = controller.pin_coords.split()
    
    # Рассчитываем относительные координаты для отображения в центре
    # Предполагаем стандартное разрешение экрана 1260x2240
    screen_width = 1260
    screen_height = 2240
    
    # Центрируем координаты относительно центра экрана
    center_x = 400  # центр окна приложения
    center_y = 270  # центр окна приложения
    
    # Вычисляем относительные координаты
    pause_rel_x = center_x + (int(pause_x) - screen_width // 2) // 3
    pause_rel_y = center_y + (int(pause_y) - screen_height // 2) // 3
    like_rel_x = center_x + (int(like_x) - screen_width // 2) // 3
    like_rel_y = center_y + (int(like_y) - screen_height // 2) // 3
    pin_rel_x = center_x + (int(pin_x) - screen_width // 2) // 3
    pin_rel_y = center_y + (int(pin_y) - screen_height // 2) // 3
    
    return render_template('index.html', 
        pause_coords=controller.pause_coords.split(),
        like_coords=controller.like_coords.split(),
        pin_coords=controller.pin_coords.split(),
        pause_rel_coords=[pause_rel_x, pause_rel_y],
        like_rel_coords=[like_rel_x, like_rel_y],
        pin_rel_coords=[pin_rel_x, pin_rel_y],
        connection_type=controller.connection_type,
        logs=controller.log_messages,
        scrcpy_running=scrcpy_running,
        adb_ip=controller.adb_ip,
        adb_port=controller.adb_port,
        scrcpy_fps=controller.scrcpy_fps,
        hotkeys=controller.hotkeys)

@app.route('/tab_changed', methods=['POST'])
def tab_changed():
    data = request.json
    tab = data.get('tab') # type: ignore
    # Включаем отображение указателя только на вкладке настроек
    # controller.set_pointer_location(tab == "settings")
    return jsonify({'success': True})

@app.route('/action', methods=['POST'])
def handle_action():
    data = request.json
    action = data.get('action') # type: ignore

    if action == "update_hotkey":
        success = controller.update_hotkey(
            data.get('action_name'), # type: ignore
            data.get('key') # type: ignore
        )
    elif action == "save_connection_settings":
        success = controller.save_connection_settings(
            data.get('connection_type'), # type: ignore
            data.get('adb_ip'), # type: ignore
            data.get('adb_port'), # type: ignore
            data.get('scrcpy_fps') # type: ignore
        )
    elif action == "save_coords":
        success = controller.save_coords(
            data.get('pause_x'), # type: ignore
            data.get('pause_y'), # type: ignore
            data.get('like_x'), # type: ignore
            data.get('like_y'), # type: ignore
            data.get('pin_x'), # type: ignore
            data.get('pin_y') # type: ignore
        )
    elif action in [
            "pause", 
            "like", 
            "pin", 
            "scroll_up", "scroll_down", 
            "vol_min", "vol_plus", "home", "back", "recent",
            "restart_scrcpy",
        ]:
        if action == "vol_plus":
            success = controller.vol_plus_action()
        elif action == "vol_min":
            success = controller.vol_min_action()
        elif action == "restart_scrcpy":
            success = controller.restart_scrcpy()
        elif action == "pause":
            success = controller.pause_action()
        elif action == "like":
            success = controller.like_action()
        elif action == "pin":
            success = controller.pin_action()
        elif action == "scroll_down":
            success = controller.scroll_down_action()
        elif action == "scroll_up":
            success = controller.scroll_up_action()
        elif action == "home":
            success = controller.home_action()
        elif action == "back":
            success = controller.back_action()
        elif action == "recent":
            success = controller.recent_action()
        else:
            success = controller.perform_action(action)
    else:
        success = False
    
    return jsonify({
        'success': success,
        'logs': controller.log_messages[-22:],
        'scrcpy_running': controller.scrcpy_process and controller.scrcpy_process.poll() is None
    })

@app.route('/get_logs')
def get_logs():
    return jsonify({
        'logs': controller.log_messages[-22:],
        'scrcpy_running': controller.scrcpy_process and controller.scrcpy_process.poll() is None
    })

# Маршрут для обслуживания файлов из текущей директории
@app.route('/files/<path:filename>')
def serve_files(filename):
    # Безопасная проверка пути
    base_directory = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_directory, filename)
    
    # Проверяем, что файл находится в текущей директории (безопасность)
    if not os.path.commonpath([base_directory, file_path]) == base_directory:
        return "Access denied", 403
    
    if not os.path.exists(file_path):
        return "File not found", 404
        
    return send_from_directory(base_directory, filename)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    controller.cleanup()
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

def run_flask():
    app.run(debug=False, port=56987)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    window = webview.create_window(
        'Android Controller', 
        'http://127.0.0.1:56987/', 
        width=1000, height=580, resizable=False
    )
    
    def on_closed():
        controller.keyboard_listener_active = False
        if hasattr(controller, 'scrcpy_process') and controller.scrcpy_process:
            controller.scrcpy_process.terminate()
            controller.scrcpy_process.wait(timeout=1)
        os._exit(0)
    
    window.events.closed += on_closed # type: ignore
    webview.start()