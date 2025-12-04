"""配置管理模块"""
import os
from sys import platform
from typing import Dict, Any, Optional
import yaml
from path_utils import get_base_path, get_resource_path, ensure_path_exists


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, base_path=None):
        # 如果没有提供base_path，使用自动检测的路径
        self.base_path = base_path if base_path else get_base_path()
        self.config_path = get_resource_path("config")
        self.ai_config = AIConfig()

        # 规范化平台键
        if platform.startswith('win'):
            self.platform_key = 'win32'
        elif platform == 'darwin':
            self.platform_key = 'darwin'
        else:
            self.platform_key = 'win32'

    def load_config(self, config_type: str, platform: Optional[str] = None, *args) -> Any:
        """
        通用配置加载函数
        
        Args:
            config_type: 配置类型，支持: 'model_configs', 'chara_meta', 'text_configs', 
                        'keymap', 'process_whitelist', 'gui_settings'
            *args: 额外参数，如平台类型或配置键名
        
        Returns:
            配置数据
        """
        config_handlers = {
            'model_configs': self._load_model_configs,
            'chara_meta': self._load_chara_meta,
            'text_configs': self._load_text_configs,
            'keymap': self._load_keymap,
            'process_whitelist': self._load_process_whitelist,
            'gui_settings': self._load_gui_settings,
        }
        
        if config_type not in config_handlers:
            raise ValueError(f"不支持的配置类型: {config_type}")
        
        return config_handlers[config_type](*args)
    
    def _load_model_configs(self) -> Dict[str, Any]:
        """加载模型配置"""
        settings = self._load_gui_settings()
        return settings.get("sentiment_matching", {}).get("model_configs", {})
    
    def _load_chara_meta(self):
        """加载角色元数据"""
        config = self._load_yaml_file("chara_meta.yml")
        return config.get("mahoshojo") if config else None
    
    def _load_text_configs(self):
        """加载文本配置"""
        config = self._load_yaml_file("text_configs.yml")
        return config.get("text_configs") if config else None
    
    def _load_keymap(self, platform=None):
        """加载快捷键映射"""
        platform_key = platform or self.platform_key
        
        # 尝试加载配置文件
        config = self._load_yaml_file("keymap.yml")
        
        # 如果文件不存在或加载失败，使用默认配置并保存
        if config is None:
            default_config = self._get_default_keymap()
            self._save_yaml_file("keymap.yml", default_config)
            return default_config.get(platform_key, {})
        
        return config.get(platform_key, {})
    
    def _load_process_whitelist(self):
        """加载进程白名单"""
        config = self._load_yaml_file("process_whitelist.yml")
        return config.get(self.platform_key, []) if config else []
    
    def _load_gui_settings(self):
        """加载GUI设置"""
        default_settings = self._get_default_gui_settings()
        
        # 尝试加载配置文件
        config = self._load_yaml_file("settings.yml")
        if config is None:
            return default_settings
        
        # 合并默认设置和加载的设置
        merged_settings = default_settings.copy()
        if config:
            merged_settings.update(config)
            
            # 合并嵌套配置
            for key in ["sentiment_matching", "image_compression"]:
                if key in config:
                    merged_settings[key].update(config[key])
        
        return merged_settings
    
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
                "toggle_listener": "alt+ctrl+p",
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
                "toggle_listener": "alt+cmd+p",
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
                "enabled": False
            },
            "image_compression": {
                "pixel_reduction_enabled": True,
                "pixel_reduction_ratio": 50
            }
        }
    
    # 以下是保存和辅助函数
    def save_model_configs(self, model_configs: Dict[str, Any]) -> bool:
        """保存模型配置到settings.yml"""
        try:
            settings = self._load_gui_settings()
            
            # 确保sentiment_matching部分存在
            if "sentiment_matching" not in settings:
                settings["sentiment_matching"] = {"enabled": False}
            
            # 更新模型配置
            settings["sentiment_matching"]["model_configs"] = model_configs
            
            # 保存更新后的设置
            return self.save_gui_settings(settings)
        except Exception as e:
            print(f"保存模型配置失败: {e}")
            return False
    
    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """获取可用模型配置"""
        # 从配置文件读取模型配置
        model_configs = self._load_model_configs()
        
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
        
    def save_keymap(self, platform_key=None, new_hotkeys=None):
        """保存快捷键设置到keymap.yml"""
        platform_key = platform_key or self.platform_key
        
        if new_hotkeys is None:
            return False
            
        # 加载现有配置
        keymap_data = self._load_yaml_file("keymap.yml") or self._get_default_keymap()
        
        # 合并新的快捷键设置到当前平台
        if platform_key not in keymap_data:
            keymap_data[platform_key] = {}
        keymap_data[platform_key].update(new_hotkeys)

        # 保存回文件
        return self._save_yaml_file("keymap.yml", keymap_data)
    
    def save_process_whitelist(self, processes):
        """保存进程白名单"""
        # 加载现有配置
        existing_data = self._load_yaml_file("process_whitelist.yml") or {}
        
        # 更新当前平台的白名单
        existing_data[self.platform_key] = processes
        
        # 保存回文件
        return self._save_yaml_file("process_whitelist.yml", existing_data)
        
    def save_gui_settings(self, settings):
        """保存GUI设置到settings.yml"""
        # 如果文件已存在，则先加载现有配置，然后合并
        existing_settings = self._load_yaml_file("settings.yml") or {}
        
        # 合并设置，新的设置覆盖旧的
        merged_settings = existing_settings.copy()
        merged_settings.update(settings)
        
        # 保存回文件
        return self._save_yaml_file("settings.yml", merged_settings)

    @staticmethod
    def validate_hotkey_format(hotkey):
        """验证快捷键格式的有效性"""
        valid_modifiers = ['ctrl', 'alt', 'shift', 'win', 'cmd']
        valid_keys = [
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 
            'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
            'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            'space', 'tab', 'enter', 'esc', 'backspace', 'delete', 'insert', 'home', 'end',
            'pageup', 'pagedown', 'up', 'down', 'left', 'right'
        ]
        
        if not hotkey:
            return True  # 空快捷键允许
        
        hotkey = hotkey.strip().lower()
        
        # 检查格式：modifier+key 或 modifier+modifier+key
        parts = hotkey.split('+')
        if len(parts) < 2 or len(parts) > 3:
            return False, f"快捷键 '{hotkey}' 格式无效，应为：修饰键+按键"
        
        # 检查修饰键
        for modifier in parts[:-1]:
            if modifier not in valid_modifiers:
                return False, f"快捷键 '{hotkey}' 包含无效修饰键 '{modifier}'"
        
        # 检查主按键
        main_key = parts[-1]
        if main_key not in valid_keys:
            return False, f"快捷键 '{hotkey}' 包含无效按键 '{main_key}'"
        
        return True, ""

class AIConfig:
    """AI配置类"""
    def __init__(self):
        self.ollama = {
            "base_url": "http://localhost:11434/v1/",
            "api_key": "",
            "model": "qwen2.5"
        }
        self.deepseek = {
            "base_url": "https://api.deepseek.com",
            "api_key": "",
            "model": "deepseek-chat"
        }

class AppConfig:
    """应用配置类"""
    
    def __init__(self, base_path=None):
        self.BOX_RECT = ((728, 355), (2339, 800))  # 文本框区域坐标
        self.KEY_DELAY = 0.05  # 按键延迟
        self.AUTO_PASTE_IMAGE = True
        self.AUTO_SEND_IMAGE = True
        # 使用自动检测的基础路径
        self.BASE_PATH = base_path if base_path else get_base_path()
        self.ASSETS_PATH = get_resource_path("assets")