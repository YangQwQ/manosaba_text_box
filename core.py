"""魔裁文本框核心逻辑"""
from config import ConfigLoader, AppConfig
from clipboard_utils import ClipboardManager
from sentiment_analyzer import SentimentAnalyzer
from load_utils import clear_cache, preload_all_images_async, load_background_safe, load_character_safe
from path_utils import get_resource_path, get_available_fonts
from draw_utils import draw_content_auto, load_font_cached

import os
import time
import random
import psutil
import threading
from pynput.keyboard import Key, Controller
from sys import platform
import keyboard as kb_module
from PIL import Image, ImageDraw
from typing import Dict, Any

if platform.startswith("win"):
    try:
        import win32gui
        import win32process
    except ImportError:
        print("[red]请先安装 Windows 运行库: pip install pywin32[/red]")
        raise

class ManosabaCore:
    """魔裁文本框核心类"""

    def __init__(self):
        # 初始化配置
        self.config = AppConfig(os.path.dirname(os.path.abspath(__file__)))
        self.kbd_controller = Controller()
        self.clipboard_manager = ClipboardManager()

        # 加载配置
        self.config_loader = ConfigLoader()
        self.mahoshojo = {}
        self.text_configs_dict = {}
        self.character_list = []
        self.keymap = {}
        self.process_whitelist = []
        self._load_configs()

        # 图片处理器相关的属性
        self.box_rect = self.config.BOX_RECT
        self.background_count = self._get_background_count()  # 背景图片数量
        
        # 状态变量(为None时为随机选择)
        self.selected_emotion = None
        self.selected_background = None
        
        #预览图当前的索引
        self.preview_emotion = -1
        self.preview_background = -1
        self.current_base_image = None  # 当前预览的基础图片（用于快速生成）
        self.current_character_index = 2
        
        # 状态更新回调
        self.status_callback = None
        self.gui_callback = None

        # GUI设置
        self.gui_settings = self.config_loader.load_config("gui_settings")

        # 初始化情感分析器 - 不在这里初始化，等待特定时机
        self.sentiment_analyzer = SentimentAnalyzer()
        self.sentiment_analyzer_status = {
            'initialized': False,
            'initializing': False,
            'current_config': {}
        }
        
        # 程序启动时开始预加载图片
        self.update_status("正在预加载图片到缓存...")
        self._preload_images_async()

        # 程序启动时检查是否需要初始化
        sentiment_settings = self.gui_settings.get("sentiment_matching", {})
        if sentiment_settings.get("enabled", False):
            self.update_status("检测到启用情感匹配，正在初始化...")
            self._initialize_sentiment_analyzer_async()
        else:
            self.update_status("情感匹配功能未启用")
            self._notify_gui_status_change(False, False)

    def _get_background_count(self) -> int:
        """动态获取背景图片数量"""
        try:
            background_dir = get_resource_path(os.path.join("assets", "background"))
            if os.path.exists(background_dir):
                # 统计所有c开头的背景图片
                bg_files = [f for f in os.listdir(background_dir) 
                           if f.endswith('.png') and f.lower().startswith('c')]
                return len(bg_files)
            else:
                print(f"警告：背景图片目录不存在: {background_dir}")
                return 0
        except Exception as e:
            print(f"获取背景数量失败: {e}")
            return 0

    def _preload_character_images(self, character_name: str):
        """预加载角色图片到内存"""
        if character_name not in self.mahoshojo:
            return

        emotion_count = self.mahoshojo[character_name].get("emotion_count", 0)

        for emotion_index in range(1, emotion_count + 1):
            overlay_path = get_resource_path(os.path.join(
                "assets",
                "chara",
                character_name,
                f"{character_name} ({emotion_index}).png"
            ))
            load_character_safe(overlay_path)

    def _generate_base_image_with_text(
        self, character_name: str, background_index: int, emotion_index: int
    ) -> Image.Image:
        """生成带角色文字的基础图片"""
        background_path = get_resource_path(os.path.join("assets", "background", f"c{background_index}.png"))
        background = load_background_safe(background_path, default_size=(800, 600), default_color=(100, 100, 200))
        
        overlay_path = get_resource_path(os.path.join(
            "assets",
            "chara",
            character_name,
            f"{character_name} ({emotion_index}).png"
        ))
        overlay = load_character_safe(overlay_path, default_size=(800, 600), default_color=(0, 0, 0, 0))

        result = background
        result.paste(overlay, (0, 134), overlay)

        # 添加角色名称文字
        if self.text_configs_dict and character_name in self.text_configs_dict:
            draw = ImageDraw.Draw(result)
            shadow_offset = (2, 2)
            shadow_color = (0, 0, 0)

            for config in self.text_configs_dict[character_name]:
                text = config["text"]
                position = tuple(config["position"])
                font_color = tuple(config["font_color"])
                font_size = config["font_size"]

                font_name = self.mahoshojo[character_name].get("font", "font3.ttf")
                font = load_font_cached(font_name, font_size)

                # 绘制阴影文字
                shadow_position = (
                    position[0] + shadow_offset[0],
                    position[1] + shadow_offset[1],
                )
                draw.text(shadow_position, text, fill=shadow_color, font=font)

                # 绘制主文字
                draw.text(position, text, fill=font_color, font=font)

        return result
    
    def _preload_images_async(self):
        """异步预加载所有图片到缓存"""
        def preload_callback(success, message):
            if success:
                self.update_status("图片预加载完成，所有资源已缓存")
            else:
                self.update_status(f"图片预加载失败: {message}")
        
        # 开始异步预加载
        preload_all_images_async(
            self.config.BASE_PATH,
            self.mahoshojo,
            callback=preload_callback
        )

    def set_gui_callback(self, callback):
        """设置GUI回调函数，用于通知状态变化"""
        self.gui_callback = callback

    def _notify_gui_status_change(self, initialized: bool, enabled: bool = None, initializing: bool = False):
        """通知GUI状态变化"""
        if self.gui_callback:
            if enabled is None:
                # 如果没有指定enabled，则使用当前设置
                sentiment_settings = self.gui_settings.get("sentiment_matching", {})
                enabled = sentiment_settings.get("enabled", False) and initialized
            self.gui_callback(initialized, enabled, initializing)

    def _initialize_sentiment_analyzer_async(self):
        """异步初始化情感分析器"""
        def init_task():
            try:
                self.sentiment_analyzer_status['initializing'] = True
                self._notify_gui_status_change(False, False, True)
                
                sentiment_settings = self.gui_settings.get("sentiment_matching", {})
                if sentiment_settings.get("enabled", False):
                    client_type = sentiment_settings.get("ai_model", "ollama")
                    model_configs = sentiment_settings.get("model_configs", {})
                    config = model_configs.get(client_type, {})
                    
                    # 记录当前配置
                    self.sentiment_analyzer_status['current_config'] = {
                        'client_type': client_type,
                        'config': config.copy()
                    }
                    
                    success = self.sentiment_analyzer.initialize(client_type, config)
                    
                    if success:
                        self.update_status("情感分析器初始化完成，功能已启用")
                        self.sentiment_analyzer_status['initialized'] = True
                        # 通知GUI初始化成功
                        self._notify_gui_status_change(True, True, False)
                    else:
                        self.update_status("情感分析器初始化失败，功能已禁用")
                        self.sentiment_analyzer_status['initialized'] = False
                        # 通知GUI初始化失败，需要禁用情感匹配
                        self._notify_gui_status_change(False, False, False)
                        # 更新设置，禁用情感匹配
                        self._disable_sentiment_matching()
                else:
                    self.update_status("情感匹配功能未启用，跳过初始化")
                    self.sentiment_analyzer_status['initialized'] = False
                    self._notify_gui_status_change(False, False, False)
                    
            except Exception as e:
                self.update_status(f"情感分析器初始化失败: {e}，功能已禁用")
                self.sentiment_analyzer_status['initialized'] = False
                # 通知GUI初始化失败，需要禁用情感匹配
                self._notify_gui_status_change(False, False, False)
                # 更新设置，禁用情感匹配
                self._disable_sentiment_matching()
            finally:
                self.sentiment_analyzer_status['initializing'] = False
        
        # 在后台线程中初始化
        init_thread = threading.Thread(target=init_task, daemon=True)
        init_thread.start()    
    
    def toggle_sentiment_matching(self):
        """切换情感匹配状态"""
        # 如果正在初始化，不处理点击
        if self.sentiment_analyzer_status['initializing']:
            return
            
        sentiment_settings = self.gui_settings.get("sentiment_matching", {})
        current_enabled = sentiment_settings.get("enabled", False)
        
        if not current_enabled:
            # 如果当前未启用，则启用并初始化
            if not self.sentiment_analyzer_status['initialized']:
                # 如果未初始化，则开始初始化
                self.update_status("正在初始化情感分析器...")
                if "sentiment_matching" not in self.gui_settings:
                    self.gui_settings["sentiment_matching"] = {}
                self.gui_settings["sentiment_matching"]["enabled"] = True
                self.config_loader.save_gui_settings(self.gui_settings)
                self._initialize_sentiment_analyzer_async()
            else:
                # 如果已初始化，直接启用
                self.update_status("已启用情感匹配功能")
                self.gui_settings["sentiment_matching"]["enabled"] = True
                self.config_loader.save_gui_settings(self.gui_settings)
                self._notify_gui_status_change(True, True, False)
        else:
            # 如果当前已启用，则禁用
            self.update_status("已禁用情感匹配功能")
            self.gui_settings["sentiment_matching"]["enabled"] = False
            self.config_loader.save_gui_settings(self.gui_settings)
            self._notify_gui_status_change(self.sentiment_analyzer_status['initialized'], False, False)

    def _disable_sentiment_matching(self):
        """禁用情感匹配设置"""
        if "sentiment_matching" in self.gui_settings:
            self.gui_settings["sentiment_matching"]["enabled"] = False
        # 保存设置
        self.config_loader.save_gui_settings(self.gui_settings)
        self.update_status("情感匹配功能已禁用")

    def _reinitialize_sentiment_analyzer_if_needed(self):
        """检查配置是否有变化，如果有变化则重新初始化"""
        sentiment_settings = self.gui_settings.get("sentiment_matching", {})
        if not sentiment_settings.get("enabled", False):
            # 如果功能被禁用，重置状态
            if self.sentiment_analyzer_status['initialized']:
                self.sentiment_analyzer_status['initialized'] = False
                self.update_status("情感匹配已禁用，重置分析器状态")
                self._notify_gui_status_change(False, False, False)
            return
        
        client_type = sentiment_settings.get("ai_model", "ollama")
        model_configs = sentiment_settings.get("model_configs", {})
        config = model_configs.get(client_type, {})
        
        new_config = {
            'client_type': client_type,
            'config': config.copy()
        }
        
        # 检查配置是否有变化
        if new_config != self.sentiment_analyzer_status['current_config']:
            self.update_status("AI配置已更改，重新初始化情感分析器")
            self.sentiment_analyzer_status['initialized'] = False
            self.sentiment_analyzer_status['current_config'] = new_config
            # 通知GUI开始重新初始化
            self._notify_gui_status_change(False, False, False)
            self._initialize_sentiment_analyzer_async()

    def get_ai_models(self) -> Dict[str, Dict[str, Any]]:
        """获取可用的AI模型配置"""
        return self.sentiment_analyzer.client_manager.get_available_models()

    def test_ai_connection(self, client_type: str, config: Dict[str, Any]) -> bool:
        """测试AI连接 - 这会进行模型初始化"""
        try:
            # 使用临时分析器进行测试，不影响主分析器状态
            temp_analyzer = SentimentAnalyzer()
            success = temp_analyzer.initialize(client_type, config)
            if success:
                self.update_status(f"AI连接测试成功: {client_type}")
                # 如果测试成功，可以更新主分析器
                self.sentiment_analyzer.initialize(client_type, config)
                self.sentiment_analyzer_status['initialized'] = True
                # 通知GUI测试成功
                self._notify_gui_status_change(True, True)
            else:
                self.update_status(f"AI连接测试失败: {client_type}")
                self.sentiment_analyzer_status['initialized'] = False
                # 通知GUI测试失败
                self._notify_gui_status_change(False, False)
            return success
        except Exception as e:
            self.update_status(f"连接测试失败: {e}")
            self.sentiment_analyzer_status['initialized'] = False
            # 通知GUI测试失败
            self._notify_gui_status_change(False, False)
            return False

    def _get_emotion_by_sentiment(self, text: str) -> int:
        """根据文本情感获取对应的表情索引"""
        if not text.strip():
            return None
        
        if not self.sentiment_analyzer_status['initialized']:
            return None
    
        try:
            # 分析情感
            sentiment = self.sentiment_analyzer.analyze_sentiment(text)
            if not sentiment:
                return None
                
            current_character = self.get_character()
            character_meta = self.mahoshojo.get(current_character, {})
            
            # 查找对应情感的表情索引列表
            emotion_indices = character_meta.get(sentiment, [])
            if not emotion_indices:
                # 如果没有对应的情感，使用无感情表情
                emotion_indices = character_meta.get("无感情", [])
                if not emotion_indices:
                    return None
                
            # 随机选择一个表情索引
            if emotion_indices:
                import random
                return random.choice(emotion_indices)
            else:
                return None
                
        except Exception as e:
            self.update_status(f"情感分析失败: {e}")
            return None

    def _update_emotion_by_sentiment(self, text: str) -> bool:
        """根据文本情感更新表情，返回是否成功更新"""
        # 检查情感分析器是否已初始化
        if not self.sentiment_analyzer_status['initialized']:
            self.update_status("情感分析器未初始化，跳过情感分析")
            return False
            
        emotion_index = self._get_emotion_by_sentiment(text)
        if emotion_index:
            self.selected_emotion = emotion_index
            return True
        return False

    def _load_configs(self):
        """加载所有配置"""
        self.mahoshojo = self.config_loader.load_config("chara_meta")
        self.character_list = list(self.mahoshojo.keys())
        self.text_configs_dict = self.config_loader.load_config("text_configs")
        self.keymap = self.config_loader.load_config("keymap")
        self.process_whitelist = self.config_loader.load_config("process_whitelist")
        
    def reload_configs(self):
        """重新加载配置（用于热键更新后）"""
        # 重新加载快捷键映射
        self.keymap = self.config_loader.load_config("keymap", platform=platform)
        # 重新加载进程白名单
        self.process_whitelist = self.config_loader.load_config("process_whitelist")
        # 重新加载GUI设置
        self.gui_settings = self.config_loader.load_config("gui_settings")
        self.update_status("配置已重新加载")

    def get_character(self, index: str | None = None, full_name: bool = False) -> str:
        """获取角色名称"""
        if index is not None:
            return self.mahoshojo[index]["full_name"] if full_name else index
        else:
            chara = self.character_list[self.current_character_index - 1]
            return self.mahoshojo[chara]["full_name"] if full_name else chara

    def switch_character(self, index: int) -> bool:
        """切换到指定索引的角色"""
        clear_cache("character")
        if 0 < index <= len(self.character_list):
            self.current_character_index = index
            character_name = self.get_character()
            # 预加载角色图片到内存
            self._preload_character_images(character_name)
            return True
        return False

    def get_current_emotion_count(self) -> int:
        """获取当前角色的表情数量"""
        return self.mahoshojo[self.get_character()]["emotion_count"]

    def get_gui_settings(self):
        """获取GUI设置"""
        return self.gui_settings

    def save_gui_settings(self, settings):
        """保存GUI设置"""
        self.gui_settings = settings
        return self.config_loader.save_gui_settings(settings)

    def _get_random_index(self, index_count: int, exclude_index: int = -1) -> int:
        """随机选择表情（避免连续相同）"""
        if exclude_index == -1:
            final_index = random.randint(1, index_count)
        else:
            # 避免连续相同表情
            available_indices = [i for i in range(1, index_count + 1) if i != exclude_index]
            final_index = (
                random.choice(available_indices)
                if available_indices
                else exclude_index
            )

        return final_index

    def _active_process_allowed(self) -> bool:
        """校验当前前台进程是否在白名单"""
        if not self.process_whitelist:
            return True

        wl = {name.lower() for name in self.process_whitelist}

        if platform.startswith("win"):
            try:
                hwnd = win32gui.GetForegroundWindow()
                if not hwnd:
                    return False
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                name = psutil.Process(pid).name().lower()
                return name in wl
            except (psutil.Error, OSError):
                return False

        elif platform == "darwin":
            try:
                import subprocess

                result = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "System Events" to get name of first process whose frontmost is true',
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                name = result.stdout.strip().lower()
                return name in wl
            except subprocess.SubprocessError:
                return False

        else:
            # Linux 支持
            return True
    
    def set_status_callback(self, callback):
        """设置状态更新回调函数"""
        self.status_callback = callback

    def update_status(self, message: str):
        """更新状态（供外部调用）"""
        if self.status_callback:
            self.status_callback(message)

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """将十六进制颜色转换为RGB元组"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def generate_preview(self) -> tuple:
        """生成预览图片和相关信息"""
        character_name = self.get_character()
        emotion_count = self.get_current_emotion_count()

        # 确定表情和背景
        emotion_index = (
            self._get_random_index(emotion_count, exclude_index=self.preview_emotion)
            if self.selected_emotion is None
            else self.selected_emotion
        )
        background_index = (
            self._get_random_index(self.background_count, exclude_index=self.preview_background)
            if self.selected_background is None
            else self.selected_background
        )

        # 保存预览使用的表情和背景
        self.preview_emotion = emotion_index
        self.preview_background = background_index

        # 生成预览图片
        try:
            self.current_base_image = self._generate_base_image_with_text(
                character_name, background_index, emotion_index
            )
        except:
            self.current_base_image = Image.new("RGB", (400, 300), color="gray")

        # 用于 GUI 预览
        preview_image = self.current_base_image.copy()

        # 构建预览信息 - 显示实际使用的索引值
        emotion_text = (
            f"{emotion_index}" if self.selected_emotion is None else f"{emotion_index}"
        )
        background_text = (
            f"{background_index}"
            if self.selected_background is None
            else f"{background_index}"
        )

        info = f"角色: {character_name}\n表情: {emotion_text}\n背景: {background_text}"

        return preview_image, info

    def generate_image(self) -> str:
        """生成并发送图片"""
        if not self._active_process_allowed():
            return "前台应用不在白名单内"

        base_msg=""

        # 开始计时
        start_time = time.time()
        print(f"[{int((time.time()-start_time)*1000)}] 开始生成图片")

        # 清空剪贴板
        self.clipboard_manager.clear_clipboard()

        time.sleep(0.005)

        if platform.startswith("win"):
            kb_module.send("ctrl+a")
            kb_module.send("ctrl+x")
        else:
            self.kbd_controller.press(Key.cmd)
            self.kbd_controller.press("a")
            self.kbd_controller.release("a")
            self.kbd_controller.press("x")
            self.kbd_controller.release("x")
            self.kbd_controller.release(Key.cmd)

        print(f"[{int((time.time()-start_time)*1000)}] 开始读取剪切板")
        deadline = time.time() + 2.5
        while time.time() < deadline:
            text, image = self.clipboard_manager.get_clipboard_all()
            if (text and text.strip()) or image is not None:
                print(f"[{int((time.time()-start_time)*1000)}] 剪切板内容获取完成")
                break
            time.sleep(0.005)
            
        print("读取到图片" if image is not None else "", "读取到文本" if text.strip() else "")
        # 情感匹配处理：仅当启用且只有文本内容时
        sentiment_settings = self.gui_settings.get("sentiment_matching", {})

        if (sentiment_settings.get("enabled", False) and 
            self.sentiment_analyzer_status['initialized'] and
            text.strip()):
            
            self.update_status("正在分析文本情感...")
            emotion_updated = self._update_emotion_by_sentiment(text)
            
            if emotion_updated:
                self.update_status("情感分析完成，更新表情")
                print(f"[{int((time.time()-start_time)*1000)}] 情感分析完成")
                # 刷新预览以显示新的表情
                base_msg += f"情感: {self.sentiment_analyzer.selected_emotion}  "
                self.generate_preview()
                
            else:
                self.update_status("情感分析失败，使用默认表情")
                self.selected_emotion = None
                print(f"[{int((time.time()-start_time)*1000)}] 情感分析失败")

        if text == "" and image is None:
            return "错误: 没有文本或图像"

        try:
            # 使用GUI中设置的对话框字体，而不是角色专用字体
            font_family = self.gui_settings.get("font_family")

            # 查找匹配的字体文件
            font_name = next(
                (font_file for font_file in get_available_fonts()
                if font_file and font_family == os.path.splitext(os.path.basename(font_file))[0]),
                None
            )

            if not font_name:
                print(f"字体家族 {font_family} 不在可用字体列表中")
                font_name = self.mahoshojo[self.get_character()].get("font", "font3.ttf")

            # 生成图片
            print(f"[{int((time.time()-start_time)*1000)}] 开始合成图片")
            bmp_bytes = draw_content_auto(
                image_source=self.current_base_image,
                top_left=self.config.BOX_RECT[0],
                bottom_right=self.config.BOX_RECT[1],
                text=text,
                content_image=image,
                text_align="left",
                text_valign="top",
                image_align="center",
                image_valign="middle",
                color=self._hex_to_rgb(self.gui_settings.get("text_color", "#FFFFFF")),
                bracket_color=self._hex_to_rgb(self.gui_settings.get("bracket_color", "#89B1FB")),
                max_font_height=self.gui_settings.get("font_size", 120),
                font_name=font_name,
                image_padding=12,
                compression_settings=self.gui_settings.get("image_compression", None),
            )

            print(f"[{int((time.time()-start_time)*1000)}] 图片合成完成")

        except Exception as e:
            return f"生成图像失败: {e}"

        # 复制到剪贴板
        if not self.clipboard_manager.copy_image_to_clipboard(bmp_bytes):
            return "复制到剪贴板失败"
        
        print(f"[{int((time.time()-start_time)*1000)}] 图片复制到剪切板完成")

        # 等待剪贴板确认（最多等待2.5秒）
        wait = 0.01
        total = 0
        while total < 0.5:
            if self.clipboard_manager.has_image_in_clipboard():
                break
            time.sleep(wait)
            total += wait
            wait = min(wait * 1.5, 0.08)
        print(f"[{int((time.time()-start_time)*1000)}] 剪切板确认完成")

        # 自动粘贴和发送
        if self.config.AUTO_PASTE_IMAGE:
            self.kbd_controller.press(Key.ctrl if platform != "darwin" else Key.cmd)
            self.kbd_controller.press("v")
            self.kbd_controller.release("v")
            self.kbd_controller.release(Key.ctrl if platform != "darwin" else Key.cmd)

            time.sleep(0.05)
            if not self._active_process_allowed():
                return "前台应用不在白名单内"
            if self.config.AUTO_SEND_IMAGE:
                self.kbd_controller.press(Key.enter)
                self.kbd_controller.release(Key.enter)

                print(f"[{int((time.time()-start_time)*1000)}] 自动发送完成")
        
        # 构建状态消息
        base_msg += f"角色: {self.get_character()}, 表情: {self.preview_emotion}, 背景: {self.preview_background}, 用时: {int((time.time() - start_time) * 1000)}ms"
        
        return base_msg
