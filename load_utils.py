"""文件加载工具"""
import os
import threading
import queue
from PIL import ImageFont, Image
from typing import Callable, Dict, Any, Optional

from path_utils import get_resource_path
from config import CONFIGS

# 字体缓存
_font_cache = {}

# 图片缓存
_background_cache = {}  # 背景图片缓存（长期缓存）
_character_cache = {}   # 角色图片缓存（可释放）
_general_image_cache = {}  # 通用图片缓存


# 预加载状态管理类
class PreloadManager:
    """预加载管理器"""
    def __init__(self):
        self._preload_status = {
            'total_items': 0,
            'loaded_items': 0,
            'is_complete': False
        }
        self._update_callback = None
        self._lock = threading.Lock()
        self._current_character = None       # 当前预加载的角色
        self._should_stop = threading.Event()  # 停止信号
        self._has_work = threading.Event()    # 有工作需要处理的信号
        self._task_queue = queue.Queue(maxsize=1)  # 任务队列，最多存储1个任务
        
        # 启动工作线程
        self._worker_thread = threading.Thread(
            target=self._preload_worker, 
            daemon=True,
            name="PreloadWorker"
        )
        self._worker_thread.start()
    
    def set_update_callback(self, callback: Callable[[str], None]):
        """设置状态更新回调"""
        self._update_callback = callback
    
    def update_status(self, message: str):
        """更新状态"""
        if self._update_callback:
            self._update_callback(message)

    def _preload_worker(self):
        """工作线程，持续处理预加载任务"""
        while not self._should_stop.is_set():
            try:
                # 等待有任务需要处理
                character_name = self._task_queue.get(timeout=0.1)
                
                # 处理任务
                self._preload_character_task(character_name)
                
                # 标记任务完成
                self._task_queue.task_done()
                
            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                self.update_status(f"预加载工作线程异常: {str(e)}")
        
    def _preload_character_task(self, character_name: str):
        """实际的预加载任务"""
        try:
            with self._lock:
                self._current_character = character_name
                self._preload_status['is_complete'] = False
            
            if character_name not in CONFIGS.mahoshojo:
                self.update_status(f"角色 {character_name} 配置不存在")
                return
            
            emotion_count = CONFIGS.mahoshojo[character_name]["emotion_count"]
            
            # 更新总项目数
            with self._lock:
                self._preload_status['total_items'] = emotion_count
                self._preload_status['loaded_items'] = 0
            
            self.update_status(f"开始预加载角色 {character_name}")
            
            # 预加载所有表情图片
            for emotion_index in range(1, emotion_count + 1):
                # 检查是否需要停止（有新的任务到来）
                if not self._task_queue.empty():
                    self.update_status(f"角色 {character_name} 预加载被新任务中断")
                    return
                
                # 支持多种图片格式
                supported_formats = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp']
                overlay_path = None
                
                for ext in supported_formats:
                    test_path = get_resource_path(os.path.join(
                        "assets",
                        "chara",
                        character_name,
                        f"{character_name} ({emotion_index}){ext}"
                    ))
                    if os.path.exists(test_path):
                        overlay_path = test_path
                        break
                
                # 如果所有格式都不存在，使用默认png格式（保持向后兼容）
                if overlay_path is None:
                    overlay_path = get_resource_path(os.path.join(
                        "assets",
                        "chara",
                        character_name,
                        f"{character_name} ({emotion_index}).png"
                    ))
                
                # 预加载到缓存
                load_character_safe(overlay_path, emotion_index=emotion_index)
                
                # 更新已加载项目数
                with self._lock:
                    self._preload_status['loaded_items'] = emotion_index
                
                # 实时更新进度
                progress = emotion_index / emotion_count
                if self._update_callback:
                    self.update_status(f"预加载角色 {character_name}: {emotion_index}/{emotion_count} ({progress:.0%})")
            
            with self._lock:
                self._preload_status['is_complete'] = True
            
            self.update_status(f"角色 {character_name} 预加载完成")
            
        except Exception as e:
            self.update_status(f"角色 {character_name} 预加载失败: {str(e)}")
            with self._lock:
                self._preload_status['is_complete'] = True
    
    def preload_character_images_async(self, character_name: str) -> bool:
        """异步预加载指定角色的所有表情图片"""
        try:
            # 清空队列中的旧任务（如果有）
            while not self._task_queue.empty():
                try:
                    self._task_queue.get_nowait()
                    self._task_queue.task_done()
                except queue.Empty:
                    break
            
            # 放入新任务
            self._task_queue.put_nowait(character_name)
            self.update_status(f"已提交角色 {character_name} 预加载任务")
            return True
            
        except queue.Full:
            self.update_status(f"预加载任务队列已满，无法提交 {character_name}")
            return False

    def preload_backgrounds_async(self):
        """异步预加载所有背景图片"""
        def preload_task():
            try:
                self.update_status("正在预加载背景图片...")
                background_count = CONFIGS.background_count
                
                for background_index in range(1, background_count + 1):
                    # 尝试加载多种格式的背景图片
                    background_path = None
                    
                    # 支持的图片格式列表
                    supported_formats = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp']
                    
                    for ext in supported_formats:
                        # 尝试构建不同格式的路径
                        test_path = get_resource_path(os.path.join("assets", "background", f"c{background_index}{ext}"))
                        if os.path.exists(test_path):
                            background_path = test_path
                            break
                    
                    if background_path:
                        load_background_safe(background_path)
                    else:
                        # 如果所有格式都不存在，尝试默认png格式（保持向后兼容）
                        default_path = get_resource_path(os.path.join("assets", "background", f"c{background_index}.png"))
                        load_background_safe(default_path)
                    
                    # 实时更新进度
                    progress = background_index / background_count
                    if background_index % 5 == 0 or background_index == background_count:
                        self.update_status(f"预加载背景: {background_index}/{background_count} ({progress:.0%})")
                
                self.update_status("背景图片预加载完成")
            except Exception as e:
                self.update_status(f"背景图片预加载失败: {str(e)}")
        
        # 在后台线程中执行预加载
        preload_thread = threading.Thread(target=preload_task, daemon=True)
        preload_thread.start()
    
    def get_preload_progress(self) -> float:
        """获取预加载进度"""
        with self._lock:
            if self._preload_status['total_items'] == 0:
                return 0.0
            
            progress = self._preload_status['loaded_items'] / self._preload_status['total_items']
            return min(progress, 1.0)
    
    def get_preload_status(self) -> Dict[str, Any]:
        """获取预加载状态"""
        with self._lock:
            return {
                'loaded_items': self._preload_status['loaded_items'],
                'total_items': self._preload_status['total_items'],
                'is_complete': self._preload_status['is_complete'],
                'current_character': self._current_character
            }
    
    def reset_status(self):
        """重置预加载状态"""
        with self._lock:
            self._preload_status = {
                'total_items': 0,
                'loaded_items': 0,
                'is_complete': False
            }
            self._current_character = None
    
    def stop_worker(self):
        """停止工作线程（通常在程序退出时调用）"""
        self._should_stop.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

# 创建全局预加载管理器实例
_preload_manager = PreloadManager()

# 简化后的函数定义
def get_preload_manager() -> PreloadManager:
    """获取预加载管理器实例"""
    return _preload_manager


#缓存字体
def load_font_cached(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """使用字体名称加载字体，支持打包环境"""
    cache_key = f"{font_name}_{size}"
    if cache_key not in _font_cache:
        # 构建字体路径
        font_path = os.path.join("assets", "fonts", font_name)
        resolved_font_path = get_resource_path(font_path)
        
        if os.path.exists(resolved_font_path):
            _font_cache[cache_key] = ImageFont.truetype(resolved_font_path, size=size)
        else:
            # 如果字体文件不存在，尝试使用默认字体
            default_font_path = get_resource_path(os.path.join("assets", "fonts", "font3.ttf"))
            if os.path.exists(default_font_path):
                _font_cache[cache_key] = ImageFont.truetype(default_font_path, size=size)
                print(f"警告：字体文件不存在，使用默认字体: {font_name}")
            else:
                # 如果默认字体也不存在，使用系统默认字体
                _font_cache[cache_key] = ImageFont.load_default()
                print(f"警告：字体文件不存在，使用系统默认字体: {font_name}")
    return _font_cache[cache_key]



def load_image_cached(image_path: str) -> Image.Image:
    """通用图片缓存加载，支持透明通道"""
    cache_key = image_path
    if cache_key not in _general_image_cache:
        if image_path and os.path.exists(image_path):
            _general_image_cache[cache_key] = Image.open(image_path).convert("RGBA")
        else:
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
    return _general_image_cache[cache_key].copy()



# 安全加载背景图片（文件不存在时返回默认值）
def load_background_safe(image_path: str, default_size: tuple = (800, 600), default_color: tuple = (100, 100, 200)) -> Image.Image:
    """安全加载背景图片，文件不存在时返回默认图片，加载后等比缩放到宽度2560"""
    try:
        # 直接从缓存加载
        cache_key = image_path
        if cache_key not in _background_cache:
            if image_path and os.path.exists(image_path):
                img = Image.open(image_path).convert("RGBA")
                
                # 等比缩放到宽度2560
                target_width = 2560
                if img.width != target_width:
                    # 计算缩放比例和新高度
                    width_ratio = target_width / img.width
                    new_height = int(img.height * width_ratio)
                    img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)
                
                _background_cache[cache_key] = img
            else:
                raise FileNotFoundError(f"背景图片文件不存在: {image_path}")
        return _background_cache[cache_key].copy()
    except FileNotFoundError:
        # 创建默认图片，并缩放到宽度2560
        default_img = Image.new("RGBA", default_size, default_color)
        
        # 等比缩放到宽度2560
        target_width = 2560
        if default_img.width != target_width:
            width_ratio = target_width / default_img.width
            new_height = int(default_img.height * width_ratio)
            default_img = default_img.resize((target_width, new_height), Image.Resampling.LANCZOS)
        
        return default_img

# 安全加载角色图片（文件不存在时返回默认值）
def load_character_safe(image_path: str, default_size: tuple = (800, 600), default_color: tuple = (0, 0, 0, 0), emotion_index: int = 0) -> Image.Image:
    """安全加载角色图片，文件不存在时返回默认图片"""
    try:
        # 生成不区分格式的缓存键（移除文件扩展名）
        cache_key = image_path.rsplit('.', 1)[0]  # 移除扩展名
        if cache_key not in _character_cache:
            if image_path and os.path.exists(image_path):
                img = Image.open(image_path).convert("RGBA")
                
                # 应用缩放
                scale = CONFIGS.current_character.get("scale", 1.0)
                offset = CONFIGS.current_character.get("offset", (0, 0))
                
                if scale != 1.0:
                    original_width, original_height = img.size
                    new_width = int(original_width * scale)
                    new_height = int(original_height * scale)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # 图片尺寸
                img_width, img_height = img.size
                
                # 创建800x800的透明背景图片
                result = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
                
                # 应用额外偏移（如果有）
                offsetX = CONFIGS.current_character.get(f"offsetX", {}).get(f"{emotion_index}", 0)
                offsetY = CONFIGS.current_character.get(f"offsetY", {}).get(f"{emotion_index}", 0)
                
                # 计算粘贴位置（水平居中对齐 + 偏移）
                paste_x = offset[0] + 500 - img_width//2 + offsetX
                paste_y = offset[1] + offsetY
                
                # 将缩放后的图片粘贴到透明背景上
                result.paste(img, (paste_x, paste_y), img)
                    
                _character_cache[cache_key] = result
            else:
                raise FileNotFoundError(f"角色图片文件不存在: {image_path}")
        return _character_cache[cache_key].copy()
    except FileNotFoundError:
        # 创建默认透明图片
        return Image.new("RGBA", default_size, default_color)

def load_image_safe(image_path: str, default_size: tuple = (800, 600), default_color: tuple = (100, 100, 200)) -> Image.Image:
    """安全加载图片，文件不存在时返回默认图片"""
    try:
        return load_image_cached(image_path)
    except FileNotFoundError:
        # 创建默认图片
        return Image.new("RGBA", default_size, default_color)

def load_resource_image(relative_path: str) -> Image.Image:
    """获取资源路径并加载图片"""
    image_path = get_resource_path(relative_path)
    return load_image_cached(image_path)

def clear_all_cache():
    """清理所有缓存以释放内存"""
    global _font_cache, _background_cache, _character_cache, _general_image_cache
    _font_cache.clear()
    _background_cache.clear()
    _character_cache.clear()
    _general_image_cache.clear()

def clear_character_cache():
    """清理角色图片缓存以释放内存"""
    global _character_cache
    _character_cache.clear()

def clear_cache(cache_type: str = "all"):
    """清理特定类型的缓存"""
    global _font_cache, _background_cache, _character_cache, _general_image_cache
    
    if cache_type in ("font", "all"):
        _font_cache.clear()
    if cache_type in ("background", "all"):
        _background_cache.clear()
    if cache_type in ("character", "all"):
        _character_cache.clear()
    if cache_type in ("image", "all"):
        _general_image_cache.clear()