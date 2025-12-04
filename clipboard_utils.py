"""剪贴板工具模块"""

import io
import os
import tempfile
import subprocess
import re
from sys import platform
import base64

from urllib.parse import urlparse, unquote
from urllib.request import url2pathname

from PIL import Image

from bs4 import BeautifulSoup

# import pyperclip
# import pyclip


PLATFORM = platform.lower()

if PLATFORM.startswith("win"):
    try:
        import win32clipboard
        import win32con
    except ImportError:
        print("[red]请先安装 Windows 运行库: pip install pywin32[/red]")
        raise


class ClipboardManager:
    """剪贴板管理器"""

    def __init__(self):
        self.platform = PLATFORM

    def copy_image_to_clipboard(self, bmp_bytes: bytes) -> bool:
        """将BMP字节数据复制到剪贴板"""
        try:
            if self.platform == "darwin":
                return self._copy_image_macos(bmp_bytes)
            if self.platform.startswith("win"):
                return self._copy_image_windows(bmp_bytes)
            return self._copy_image_linux(bmp_bytes)
        except Exception as e:
            print(f"复制图片到剪贴板失败: {e}")
            return False

    def _copy_image_macos(self, png_bytes: bytes) -> bool:
        """macOS 复制图片到剪贴板"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(png_bytes)
            tmp_path = tmp.name

        cmd = f"""osascript -e 'set the clipboard to (read (POSIX file "{tmp_path}") as «class PNGf»)'"""
        result = subprocess.run(cmd, shell=True, capture_output=True, check=False)

        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        return result.returncode == 0

    def _copy_image_windows(self, bmp_bytes: bytes) -> bool:
        """Windows 复制图片到剪贴板"""
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_bytes)
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            print(f"Windows 复制图片失败: {e}")
            return False
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def _copy_image_linux(self, png_bytes: bytes) -> bool:
        """Linux 复制图片到剪贴板"""
        print("Linux 剪贴板支持尚未实现")
        return False

    def has_image_in_clipboard(self) -> bool:
        """检查剪贴板中是否有图片"""
        try:
            if platform.startswith("win"):
                win32clipboard.OpenClipboard()
                try:
                    # 尝试获取剪贴板中的图片数据
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                        return True
                    return False
                finally:
                    win32clipboard.CloseClipboard()
            if platform == "darwin":
                # macOS 的实现
                from AppKit import NSPasteboard, NSPasteboardTypePNG

                pasteboard = NSPasteboard.generalPasteboard()
                return (
                    pasteboard.availableTypeFromArray_([NSPasteboardTypePNG])
                    is not None
                )
            # Linux 的实现
            return False  # 需要根据具体实现补充
        except Exception:
            return False
    
    def clear_clipboard(self):
        """清空剪贴板"""
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"清空剪贴板失败: {e}")
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def get_clipboard_all(self):
        text = ""
        image = None
        
        
        try:
            win32clipboard.OpenClipboard()
            # 1️⃣ 优先直接取位图（真正的图片）
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                header = (
                    b"BM"
                    + (len(data) + 14).to_bytes(4, "little")
                    + b"\x00\x00\x00\x00\x36\x00\x00\x00"
                )
                image = Image.open(io.BytesIO(header + data))
                image.load()

            # 2️⃣ 取纯文本
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)

            # 3️⃣ 如果没有真正的位图，但有 HTML → 从 HTML 解析图片
            if image is None:
                html = self._get_clipboard_html()
                if html:
                    html_text, html_image = self.parse_html_clipboard(html)

                    if not text:
                        text = html_text

                    if html_image is not None:
                        image = html_image
        except Exception as e:
            return "", None
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

        return text, image

    def _get_clipboard_html(self):
        html_format = win32clipboard.RegisterClipboardFormat("HTML Format")

        if not win32clipboard.IsClipboardFormatAvailable(html_format):
            return None

        html_bytes = win32clipboard.GetClipboardData(html_format)

        if isinstance(html_bytes, bytes):
            html = html_bytes.decode("utf-8", errors="ignore")
        else:
            html = html_bytes

        return html

    def _extract_img_src_from_html(self, html: str) -> str | None:
        soup = BeautifulSoup(html, 'html.parser')
        img_tag = soup.find('img')
        return img_tag.get('src') if img_tag else None

    def _file_uri_to_path(self, uri: str) -> str | None:
        # 把 file:// URI 转成本地路径。
        # 兼容：
        # - file:///C:/path/to/x.jpg
        # - file:///E:\path\to\x.jpg
        # - file://E:/path...
        # - C:\\path\\to\\x.jpg (如果传入的是本地路径也直接返回)
        # 返回 None 表示转换失败

        if not uri:
            return None

        # 已经是本地路径（包含盘符或 UNC），直接返回规范化路径
        # 例如: C:\... 或 \\server\share\...
        if re.match(r'^[a-zA-Z]:[\\/]', uri) or uri.startswith('\\\\'):
            return os.path.normpath(uri)

        # 如果是 file URI
        parsed = urlparse(uri)
        if parsed.scheme and parsed.scheme.lower() == 'file':
            # parsed.path 在 windows 上通常是 '/C:/path...'，需要转换
            # 使用 url2pathname 处理转义和驱动器前导斜杠
            try:
                path = url2pathname(parsed.path)
                # url2pathname 在 windows 上通常返回 r'C:\...'
                return os.path.normpath(path)
            except Exception:
                # 兜底：手工 decode 并去掉可能的前导 '/'
                p = unquote(parsed.path)
                if p.startswith('/') and re.match(r'^/[A-Za-z]:', p):
                    p = p[1:]
                p = p.replace('/', os.sep)
                return os.path.normpath(p)

        # 有些实现会把 file URI 写成 file:///E:\...（反斜杠混合），尝试把 file:// 前缀去掉再处理
        if uri.startswith('file://'):
            rest = uri[7:]
            # 如果以 /E: 开头则去掉前导 /
            if rest.startswith('/') and re.match(r'^/[A-Za-z]:', rest):
                rest = rest[1:]
            rest = unquote(rest)
            return os.path.normpath(rest)

        # 如果包含 file:/// 但不合常规，尝试简单替换
        if uri.startswith('file:'):
            rest = uri[len('file:'):]
            rest = rest.lstrip('/')
            rest = unquote(rest)
            return os.path.normpath(rest)

        # 不是 file URI，也不是本地路径
        return None

    def parse_html_clipboard(self, html: str):
        """
        返回 (text, image)：
        - text: html 去标签的纯文本（简单清理）
        - image: PIL.Image or None（如果能从 img src 读取到文件）
        """
        text = None
        image = None

        # 提取 img src
        src = self._extract_img_src_from_html(html)
        if src:
            # src 可能是 file:// URI、绝对路径、也可能是 http(s)（少见）
            # 处理 file:// 或本地路径
            path = self._file_uri_to_path(src)
            if path:
                try:
                    # 尝试打开文件（注意微信临时文件可能会被占用/有权限问题）
                    # 先检查文件是否存在
                    if os.path.exists(path):
                        with Image.open(path) as im:
                            image = im.copy()  # 复制到内存，避免后续文件被删除导致问题
                    else:
                        print(f"HTML图片文件不存在: {path}")
                except Exception as e:
                    # 记录错误，继续尝试其它方式或返回 None
                    print(f"HTML图片加载失败（open file）: {e}, path: {path}")

            else:
                # src 不是本地 path（可能是 data: URI 或 http(s)）
                # 处理 data: URI 的情况
                if src.startswith('data:'):
                    # data:[<mediatype>][;base64],<data>
                    try:
                        # 找到 base64 数据的起始位置
                        if ';base64,' in src:
                            header, b64 = src.split(';base64,', 1)
                            raw = base64.b64decode(b64)
                            image = Image.open(io.BytesIO(raw)).copy()
                        else:
                            # 如果没有明确的 base64 标记，尝试直接解码
                            comma_idx = src.find(',')
                            if comma_idx != -1:
                                b64 = src[comma_idx+1:]
                                raw = base64.b64decode(b64)
                                image = Image.open(io.BytesIO(raw)).copy()
                    except Exception as e:
                        print(f"HTML图片加载失败（data URI）: {e}")
                elif src.startswith('http://') or src.startswith('https://'):
                    # 如果想支持远程抓取，可以在此处 requests.get(src) 然后 Image.open(BytesIO(...))
                    # 但注意网络依赖和超时策略
                    print(f"HTML 图片为远程 URL，未下载。URL: {src}")
                else:
                    # 尝试直接作为路径处理
                    try:
                        if os.path.exists(src):
                            with Image.open(src) as im:
                                image = im.copy()
                        else:
                            print(f"HTML 图片 src 无法识别或不可访问: {src}")
                    except Exception as e:
                        print(f"HTML图片加载失败（直接路径）: {e}")

        # 提取文本：移除注释和标签，解 html 实体等（这里使用简单方法）
        try:
            # 取 StartFragment-EndFragment 间的内容优先（许多程序会包含）
            # 使用非贪婪匹配，并正确处理换行
            frag_match = re.search(r'<!--StartFragment-->(.*?)<!--EndFragment-->', html, flags=re.DOTALL)
            if frag_match:
                fragment = frag_match.group(1)
            else:
                # 如果没有找到片段标记，使用整个HTML
                fragment = html
                
            # 去标签，但保留文本内容
            # 使用更稳健的方法：先移除脚本和样式标签
            fragment = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', fragment, flags=re.DOTALL)
            
            # 移除HTML标签
            text = re.sub(r'<[^>]+>', '', fragment)
            
            # 解常见 HTML 实体
            html_entities = {
                '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
                '&quot;': '"', '&#39;': "'", '&nbsp': ' '
            }
            
            for entity, char in html_entities.items():
                text = text.replace(entity, char)
            
            # 移除多余空白字符
            text = re.sub(r'\s+', ' ', text).strip()
            
            # 如果文本为空但HTML不为空，可能还有嵌套结构
            if not text and html:
                # 尝试更激进的方法：提取所有可见文本
                text_only = re.sub(r'<[^>]+>', ' ', html)
                text_only = re.sub(r'\s+', ' ', text_only).strip()
                if text_only:
                    text = text_only
                    
        except Exception as e:
            print(f"提取文本失败: {e}")
            text = html

        return text, image