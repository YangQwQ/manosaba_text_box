"""热键管理模块"""

import threading
import time
from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Controller, HotKey
from load_utils import clear_cache
from config import CONFIGS


class HotkeyManager:
    """热键管理器"""

    def __init__(self, gui):
        self.gui = gui
        self.core = gui.core
        
        self._listener = None  # 全局热键监听器
        self._hotkey_handlers = {}  # 存储热键处理函数
        self._active = True  # 是否启用热键监听
        self._keyboard = Controller()  # 用于模拟按键
        
        # 特殊键映射
        self._special_keys = {
            Key.ctrl: "<ctrl>",
            Key.ctrl_l: "<ctrl>",
            Key.ctrl_r: "<ctrl>",
            Key.alt: "<alt>",
            Key.alt_l: "<alt>", 
            Key.alt_r: "<alt>",
            Key.shift: "<shift>",
            Key.shift_l: "<shift>",
            Key.shift_r: "<shift>",
            Key.cmd: "<cmd>",
            Key.cmd_l: "<cmd>",
            Key.cmd_r: "<cmd>",
            Key.space: "<space>",
            Key.enter: "<enter>",
            Key.esc: "<esc>",
            Key.tab: "<tab>",
        }

    def setup_hotkeys(self):
        """设置热键监听"""
        if self._listener is not None:
            return
        
        # 重新加载配置
        try:
            hotkey_configs = CONFIGS.keymap
            quick_chars = CONFIGS.gui_settings.get("quick_characters", {})
        except Exception as e:
            print(f"加载热键配置失败: {e}")
            return
        
        # 创建热键处理函数字典
        self._hotkey_handlers = {}
        
        # 为每个热键创建处理函数
        for action, hotkey_str in hotkey_configs.items():
            # 转换为pynput格式的热键字符串
            pynput_hotkey = self._convert_to_pynput_format(hotkey_str)
            if not pynput_hotkey:
                print(f"无法转换热键: {hotkey_str}")
                continue
            
            # 创建处理函数
            if action == "toggle_listener":
                # 切换监听状态的热键总是可用
                self._hotkey_handlers[pynput_hotkey] = self._handle_toggle_listener
            else:
                # 其他热键受_active状态控制
                self._hotkey_handlers[pynput_hotkey] = self._create_hotkey_handler(action, quick_chars)
        
        # 启动热键监听器
        self._start_listener()
        print(f"热键监听器已启动，平台: {CONFIGS.platform}")

    def _convert_to_pynput_format(self, hotkey_str):
        """将热键字符串转换为pynput格式"""
        if not hotkey_str:
            return None
        
        try:
            parts = []
            for part in hotkey_str.lower().split('+'):
                part = part.strip()
                
                # 根据平台处理修饰键
                if part in ['ctrl', 'control']:
                    parts.append('<ctrl>')
                elif part in ['alt', 'menu']:
                    parts.append('<alt>')
                elif part in ['shift']:
                    parts.append('<shift>')
                elif part in ['win', 'windows', 'cmd', 'command']:
                    # Windows键/Mac Command键
                    if CONFIGS.platform == 'darwin':  # macOS
                        parts.append('<cmd>')
                    else:  # Windows/Linux
                        parts.append('<win>')
                elif part.startswith('f') and part[1:].isdigit():
                    # 功能键 F1-F12
                    parts.append(f'<{part}>')
                elif len(part) == 1 and part.isalnum():
                    # 字母或数字键
                    parts.append(part)
                elif part in ['space', 'enter', 'esc', 'tab', 'backspace', 'delete', 'insert', 
                            'pageup', 'pagedown', 'home', 'end', 'left', 'right', 'up', 'down']:
                    # 添加方向键支持
                    parts.append(f'<{part}>')
                else:
                    print(f"未知热键部分: {part}")
                    return None
            
            # 组合成pynput格式的热键字符串
            return '+'.join(parts)
        except Exception as e:
            print(f"转换热键格式失败 {hotkey_str}: {e}")
            return None

    def _create_hotkey_handler(self, action, quick_chars):
        """创建热键处理函数"""
        def handler():
            # 如果热键监听未激活，不处理
            if not self._active:
                return
            
            # 执行相应的动作
            if action == "start_generate":
                self.gui.root.after(0, self.gui.generate_image)
            elif action == "next_character":
                self.gui.root.after(0, lambda: self.switch_character(1))
            elif action == "prev_character":
                self.gui.root.after(0, lambda: self.switch_character(-1))
            elif action == "next_emotion":
                self.gui.root.after(0, lambda: self.switch_emotion(1))
            elif action == "prev_emotion":
                self.gui.root.after(0, lambda: self.switch_emotion(-1))
            elif action == "next_background":
                self.gui.root.after(0, lambda: self.switch_background(1))
            elif action == "prev_background":
                self.gui.root.after(0, lambda: self.switch_background(-1))
            elif action.startswith("character_") and action in quick_chars:
                char_id = quick_chars.get(action)
                self.gui.root.after(0, lambda c=char_id: self.switch_to_character_by_id(c))
            
            print(f"触发热键: {action}")
        
        return handler

    def _handle_toggle_listener(self):
        """处理切换监听器状态的热键"""
        self.gui.root.after(0, self.toggle_hotkey_listener)

    def _start_listener(self):
        """启动热键监听器"""
        if self._listener is not None:
            return
        
        # 检查是否有热键需要监听
        if not self._hotkey_handlers:
            print("没有热键需要监听")
            return
        
        try:
            # 启动全局热键监听器
            self._listener = keyboard.GlobalHotKeys(self._hotkey_handlers)
            self._listener.daemon = True
            self._listener.start()
            print(f"已注册热键: {list(self._hotkey_handlers.keys())}")
        except Exception as e:
            print(f"启动热键监听器失败: {e}")
            self._listener = None

    def toggle_hotkey_listener(self):
        """切换热键监听状态"""
        self._active = not self._active
        status = "启用" if self._active else "禁用"
        self.gui.update_status(f"热键监听已{status}")
        print(f"热键监听状态已切换为: {status}")

    def reload_hotkeys(self):
        """重新加载热键配置"""
        try:
            # 停止当前监听器
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
            
            # 重新设置热键
            self.setup_hotkeys()
            print("热键配置已重新加载")
        except Exception as e:
            print(f"重新加载热键失败: {e}")

    # 以下方法保持不变...
    def switch_character(self, direction):
        """切换角色"""
        current_index = CONFIGS.current_character_index
        total_chars = len(CONFIGS.character_list)
    
        new_index = current_index + direction
        if new_index > total_chars:
            new_index = 1
        elif new_index < 1:
            new_index = total_chars
    
        if self.core.switch_character(new_index):
            self._handle_character_switch_success()
    
    def switch_to_character_by_id(self, char_id):
        """通过角色ID切换到指定角色"""
        if char_id and char_id in CONFIGS.character_list:
            if char_id == CONFIGS.character_list[CONFIGS.current_character_index - 1]:
                return
            char_index = CONFIGS.character_list.index(char_id) + 1
            if self.core.switch_character(char_index):
                self._handle_character_switch_success()
    
    def switch_emotion(self, direction):
        """切换表情"""
        self._cancel_sentiment_matching()
        
        if self.gui.emotion_random_var.get():
            self.gui.emotion_random_var.set(False)
            self.gui.on_emotion_random_changed()
    
        emotion_count = CONFIGS.current_character["emotion_count"]
        current_emotion = CONFIGS.selected_emotion or 1
    
        new_emotion = current_emotion + direction
        if new_emotion > emotion_count:
            new_emotion = 1
        elif new_emotion < 1:
            new_emotion = emotion_count
    
        CONFIGS.selected_emotion = new_emotion
        self.gui.emotion_combo.set(f"表情 {new_emotion}")
        self.gui.update_preview()
        self.gui.update_status(f"已切换到表情: {new_emotion}")

    def _handle_character_switch_success(self):
        """处理角色切换成功后的通用操作"""
        clear_cache("character")
        self.gui.character_var.set(
            f"{CONFIGS.get_character(full_name=True)} ({CONFIGS.get_character()})"
        )
        self.gui.update_emotion_options()
        
        self.gui.emotion_combo.set("表情 1")
        if self.gui.emotion_random_var.get():
            CONFIGS.selected_emotion = None
        else:
            CONFIGS.selected_emotion = 1
        
        self.gui.update_preview()
        self.gui.update_status(
            f"已切换到角色: {CONFIGS.get_character(full_name=True)}"
        )
    
    def _cancel_sentiment_matching(self):
        """取消情感匹配"""
        if self.gui.sentiment_matching_var.get():
            self.gui.sentiment_matching_var.set(False)
            self.gui.on_sentiment_matching_changed()
            self.gui.update_status("已取消情感匹配（手动切换表情）")

    def switch_background(self, direction):
        """切换背景"""
        if self.gui.background_random_var.get():
            self.gui.background_random_var.set(False)
            self.gui.on_background_random_changed()

        current_bg = CONFIGS.selected_background or 1
        total_bgs = CONFIGS.background_count

        new_bg = current_bg + direction
        if new_bg > total_bgs:
            new_bg = 1
        elif new_bg < 1:
            new_bg = total_bgs

        CONFIGS.selected_background = new_bg
        self.gui.background_combo.set(f"背景 {new_bg}")
        self.gui.update_preview()
        self.gui.update_status(f"已切换到背景: {new_bg}")
    
    def stop_hotkey_listener(self):
        """停止热键监听器"""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            print("热键监听器已停止")