"""配置管理模块"""
import os
from typing import Dict, Any, Optional
import yaml
from sys import platform
from path_utils import get_base_path, get_resource_path, ensure_path_exists


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, base_path=None):
        # 如果没有提供base_path，使用自动检测的路径
        self.base_path = base_path if base_path else get_base_path()
        self.config_path = get_resource_path("config")

        self.config = AppConfig(os.path.dirname(os.path.abspath(__file__)))

        # 规范化平台键
        self.platform = platform
        if platform.startswith('win'):
            self.platform = 'win32'
        elif platform == 'darwin':
            self.platform = 'darwin'
        else:
            self.platform = 'win32'

        #当前预览相关
        self.current_character_index = 2

        # 状态变量(为None时为随机选择,否则为手动选择)
        self.selected_emotion = None
        self.selected_background = None

        #配置加载
        self.mahoshojo = {}
        self.text_configs_dict = {}
        self.character_list = []
        self.current_character = {}
        self.keymap = {}
        self.process_whitelist = []
        self._load_configs()

        self.background_count = self._get_background_count()  # 背景图片数量
    
    def _get_background_count(self) -> int:
        """动态获取背景图片数量"""
        try:
            background_dir = get_resource_path(os.path.join("assets", "background"))
            if os.path.exists(background_dir):
                # 统计所有c开头的背景图片
                bg_files = [f for f in os.listdir(background_dir) if f.lower().startswith('c')]
                return len(bg_files)
            else:
                print(f"警告：背景图片目录不存在: {background_dir}")
                return 0
        except Exception as e:
            print(f"获取背景数量失败: {e}")
            return 0
            
    def _load_configs(self):
        """加载所有配置"""
        self.mahoshojo = self.load_config("chara_meta")
        self.character_list = list(self.mahoshojo.keys())
        self.current_character = self.mahoshojo[self.character_list[self.current_character_index - 1]]

        self.text_configs_dict = self.load_config("text_configs")
        self.keymap = self.load_config("keymap")
        self.process_whitelist = self.load_config("process_whitelist")

        self.gui_settings = self.load_config("settings")

        # 设置 display 默认值为 False
        if "display" not in self.gui_settings["sentiment_matching"]:
            self.gui_settings["sentiment_matching"]["display"] = False
        self.ai_models = self.gui_settings.get("sentiment_matching", {}).get("model_configs", {})
        
        self.gui_settings["sentiment_matching"]["enabled"] &= self.gui_settings["sentiment_matching"]["display"]
        
    def reload_configs(self):
        """重新加载配置（用于热键更新后）"""
        # 重新加载快捷键映射
        self.keymap = self.load_config("keymap")
        # 重新加载进程白名单
        self.process_whitelist = self.load_config("process_whitelist")
        # 重新加载GUI设置
        self.gui_settings = self.load_config("settings")

    def load_config(self, config_type: str, *args) -> Any:
        """
        通用配置加载函数
        
        Args:
            config_type: 配置类型，支持: 'chara_meta', 'text_configs', 
                        'keymap', 'process_whitelist', 'settings'
            *args: 额外参数，如平台类型或配置键名
        
        Returns:
            配置数据
        """
        config_list = ["chara_meta", "text_configs", "keymap", "process_whitelist", "settings"]
        if config_type not in config_list:
            raise ValueError(f"不支持的配置类型: {config_type}")
        
        # 加载配置文件
        config = self._load_yaml_file(f"{config_type}.yml")
        if config_type in ["keymap", "process_whitelist"]:
            config = config.get(self.platform, {})

        if config is None:
            # 获取默认配置（gui和keymap）
            if config_type in ["settings", "keymap"]:
                print(f"警告：{config_type}.yml 不存在，使用默认配置")
                return self._get_default_gui_settings() if config_type == "settings" else self._get_default_keymap()
        else:
            return config

    def _load_yaml_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """通用YAML文件加载函数"""
        filepath = get_resource_path(os.path.join("config", filename))
        
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, 'r', encoding="utf-8") as fp:
                return yaml.safe_load(fp) or {}
        except Exception as e:
            print(f"加载配置文件 {filename} 失败: {e}")
            return None
    
    def _save_yaml_file(self, filename: str, data: Dict[str, Any]) -> bool:
        """通用YAML文件保存函数"""
        try:
            filepath = ensure_path_exists(get_resource_path(os.path.join("config", filename)))
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception as e:
            print(f"保存配置文件 {filename} 失败: {e}")
            return False
    
    def _get_default_keymap(self) -> Dict[str, Any]:
        """获取默认快捷键配置"""
        return {
            "win32": {
                "start_generate": "ctrl+e",
                "next_character": "ctrl+shift+l",
                "prev_character": "ctrl+shift+j",
                "next_emotion": "ctrl+shift+o",
                "prev_emotion": "ctrl+shift+u",
                "next_background": "ctrl+shift+k",
                "prev_background": "ctrl+shift+i",
                "toggle_listener": "ctrl+alt+p",
                "character_1": "ctrl+1",
                "character_2": "ctrl+2",
                "character_3": "ctrl+3",
                "character_4": "ctrl+4",
                "character_5": "ctrl+5",
                "character_6": "ctrl+6"
            },
            "darwin": {
                "start_generate": "cmd+e",
                "next_character": "cmd+shift+l",
                "prev_character": "cmd+shift+j",
                "next_emotion": "cmd+shift+o",
                "prev_emotion": "cmd+shift+u",
                "next_background": "cmd+shift+k",
                "prev_background": "cmd+shift+i",
                "toggle_listener": "cmd+alt+p",
                "character_1": "cmd+1",
                "character_2": "cmd+2",
                "character_3": "cmd+3",
                "character_4": "cmd+4",
                "character_5": "cmd+5",
                "character_6": "cmd+6"
            }
        }
    
    def _get_default_gui_settings(self) -> Dict[str, Any]:
        """获取默认GUI设置"""
        return {
            "font_family": "font3",
            "font_size": 110,
            "quick_characters": {},
            "sentiment_matching": {
                "display": False,
                "enabled": False
            },
            "image_compression": {
                "pixel_reduction_enabled": True,
                "pixel_reduction_ratio": 50
            }
        }

    def get_character(self, index: str | None = None, full_name: bool = False) -> str:
        """获取角色名称"""
        if index is not None:
            return self.mahoshojo[index]["full_name"] if full_name else index
        else:
            chara = self.character_list[self.current_character_index - 1]
            return self.mahoshojo[chara]["full_name"] if full_name else chara
    
    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """获取可用模型配置"""
        # 从配置文件读取模型配置
        model_configs = self.gui_settings.get("sentiment_matching", {}).get("model_configs", {})
        
        # 构建模型信息字典
        available_models = {}
        model_descriptions = {
            "ollama": "本地运行的Ollama服务",
            "deepseek": "DeepSeek在线API", 
            "chatGPT": "OpenAI ChatGPT服务"
        }
        
        for model_type, model_config in model_configs.items():
            available_models[model_type] = {
                "name": model_type.capitalize(),
                "base_url": model_config.get("base_url", ""),
                "api_key": model_config.get("api_key", ""),
                "model": model_config.get("model", ""),
                "description": model_config.get("description", model_descriptions.get(model_type, f"{model_type} AI服务"))
            }
        
        # 如果没有从配置文件读取到模型，使用默认配置
        if not available_models:
            available_models = {
                "ollama": {
                    "name": "Ollama",
                    "base_url": "http://localhost:11434/v1/",
                    "api_key": "",
                    "model": "qwen2.5",
                    "description": "本地运行的Ollama服务"
                },
                "deepseek": {
                    "name": "DeepSeek",
                    "base_url": "https://api.deepseek.com", 
                    "api_key": "",
                    "model": "deepseek-chat",
                    "description": "DeepSeek在线API"
                }
            }
        
        return available_models
        
    def save_keymap(self,new_hotkeys=None):
        """保存快捷键设置到keymap.yml"""
        if new_hotkeys is None:
            return False
            
        # 加载现有配置
        keymap_data = self._load_yaml_file("keymap.yml") or self._get_default_keymap()
        
        # 合并新的快捷键设置到当前平台
        if self.platform not in keymap_data:
            keymap_data[self.platform] = {}
        keymap_data[self.platform].update(new_hotkeys)

        # 保存回文件
        return self._save_yaml_file("keymap.yml", keymap_data)
    
    def save_process_whitelist(self, processes):
        """保存进程白名单"""
        # 加载现有配置
        existing_data = self._load_yaml_file("process_whitelist.yml") or {}
        
        # 更新当前平台的白名单
        existing_data[self.platform] = processes
        
        # 保存回文件
        return self._save_yaml_file("process_whitelist.yml", existing_data)
        
    def save_gui_settings(self):
        """保存GUI设置到settings.yml"""
        # 如果文件已存在，则先加载现有配置，然后合并
        existing_settings = self._load_yaml_file("settings.yml") or {}
        
        # 合并设置，新的设置覆盖旧的
        merged_settings = existing_settings.copy()
        merged_settings.update(self.gui_settings)
        
        # 保存回文件
        return self._save_yaml_file("settings.yml", merged_settings)

class AppConfig:
    """应用配置类"""
    
    def __init__(self, base_path=None):
        # self.BOX_RECT = ((728, 355), (2339, 800))  # 文本框区域坐标
        self.BOX_RECT = ((760, 355), (2339, 800))
        self.KEY_DELAY = 0.05  # 按键延迟
        self.AUTO_PASTE_IMAGE = True
        self.AUTO_SEND_IMAGE = True
        # 使用自动检测的基础路径
        self.BASE_PATH = base_path if base_path else get_base_path()
        self.ASSETS_PATH = get_resource_path("assets")


CONFIGS = ConfigLoader()