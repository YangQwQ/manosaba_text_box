# filename: draw_utils.py
from io import BytesIO
from typing import Tuple, Union, Literal, Optional
from PIL import Image, ImageDraw, ImageFont
import os
import time
import emoji

from load_utils import load_font_cached
from path_utils import get_resource_path

# 类型别名定义
Align = Literal["left", "center", "right"]
VAlign = Literal["top", "middle", "bottom"]

# 保留括号定义
bracket_pairs = {
    "[": "]",
    "【": "】",
    "〔": "〕",
    "‘": "’",
    "「": "」",
    "｢": "｣",
    "『": "』",
    "〖": "〗",
    "<": ">",
    "《": "》",
    "〈": "〉",
    "「": "」",
    "｢": "｣",
    "『": "』",
    "〖": "〗",
    "<": ">",
    "《": "》",
    "〈": "〉",
    "“": "”",
    '"': '"',
}

def draw_content_auto(
    image_source: Union[str, Image.Image],
    top_left: Tuple[int, int],
    bottom_right: Tuple[int, int],
    text: Optional[str] = None,
    content_image: Optional[Image.Image] = None,
    text_align: Align = "left",
    text_valign: VAlign = "top",
    image_align: Align = "center",
    image_valign: VAlign = "middle",
    color: Tuple[int, int, int] = (255, 255, 255),
    bracket_color: Tuple[int, int, int] = (137, 177, 251),
    max_font_height: Optional[int] = None,
    font_name: Optional[str] = None,
    line_spacing: float = 0.15,
    image_padding: int = 12,
    compression_settings: Optional[dict] = None,
    min_image_ratio: float = 0.2,  # 图片区域最小比例
) -> bytes:
    # 在指定矩形内自适应绘制文本和/或图片
    # 图片放置在右侧，文字放置在左侧
    
    # 参数:
    #     image_source: 背景图片或路径
    #     top_left: 区域左上角坐标
    #     bottom_right: 区域右下角坐标
    #     text: 要绘制的文本
    #     content_image: 要绘制的图片
    #     text_align: 文本水平对齐方式
    #     text_valign: 文本垂直对齐方式
    #     image_align: 图片水平对齐方式
    #     image_valign: 图片垂直对齐方式
    #     color: 文本颜色
    #     bracket_color: 括号颜色
    #     max_font_height: 最大字体高度
    #     font_name: 字体名称
    #     line_spacing: 行间距比例
    #     image_padding: 图片内边距
    #     compression_settings: 压缩设置
    #     min_image_ratio: 图片区域最小比例

    PLACEHOLDER_CHAR = "□"  # 用来占位 emoji 的字符
    EMOJI_FALLBACK_CHAR = "□"  # emoji 加载失败时使用的替代字符

    # 字体加载函数
    def load_font(size: int) -> ImageFont.FreeTypeFont:
        font_to_use = font_name if font_name else "font3.ttf"
        return load_font_cached(font_to_use, size)

    # --- 辅助函数：提取emoji并替换为占位符 ---
    def extract_emojis_and_replace(src: str, placeholder: str = PLACEHOLDER_CHAR):
        emoji_infos = emoji.emoji_list(src)
        if not emoji_infos:
            return src, []
        out_chars = []
        emojis = []
        last = 0
        for info in emoji_infos:
            s = info['match_start']
            e = info['match_end']
            if s > last:
                out_chars.append(src[last:s])
            out_chars.append(placeholder)
            emojis.append(src[s:e])
            last = e
        if last < len(src):
            out_chars.append(src[last:])
        placeholder_text = "".join(out_chars)
        return placeholder_text, emojis

    def get_emoji_filename(seq: str) -> str:
        return "emoji_u" + "_".join(f"{ord(c):x}" for c in seq) + ".png"

    def load_emoji_image(emoji_char_or_seq: str, emoji_size: int) -> Optional[Image.Image]:
        try:
            filename = get_emoji_filename(emoji_char_or_seq)
            emoji_path = get_resource_path(os.path.join("assets", "emoji", filename))

            if not os.path.exists(emoji_path):
                base_char = emoji_char_or_seq[0]
                base_filename = get_emoji_filename(base_char)
                base_path = get_resource_path(os.path.join("assets", "emoji", base_filename))

                if not os.path.exists(base_path):
                    print(f"[load_emoji_image] emoji asset not found: {emoji_path} nor {base_path}")
                    return None

                emoji_img = Image.open(base_path).convert("RGBA")
            else:
                emoji_img = Image.open(emoji_path).convert("RGBA")

            if emoji_img.width != emoji_size or emoji_img.height != emoji_size:
                emoji_img = emoji_img.resize((emoji_size, emoji_size), Image.Resampling.BILINEAR)

            return emoji_img
        except Exception as e:
            print(f"[load_emoji_image] 加载emoji图片失败 {emoji_char_or_seq}: {e}")
            return None

    def draw_text_or_emoji(
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        text: str,
        # font: ImageFont.FreeTypeFont,
        color: Tuple[int, int, int],
        emoji_size: Optional[int] = None,
        shadow_offset: int = 4,
    ) -> int:
        if emoji_size is not None:
            emoji_img = load_emoji_image(text, emoji_size)
            if emoji_img is None:
                try:
                    draw.text((x + shadow_offset, y + shadow_offset), EMOJI_FALLBACK_CHAR, font=font, fill=(0, 0, 0))
                    draw.text((x, y), EMOJI_FALLBACK_CHAR, font=font, fill=color)
                    w = int(draw.textlength(EMOJI_FALLBACK_CHAR, font=font))
                    print(f"[draw_text_or_emoji] emoji 加载失败，使用替代字符绘制: {text}")
                    return w
                except Exception as e:
                    print(f"[draw_text_or_emoji] emoji 绘制失败且替代字符绘制也失败: {text} -> {e}")
                    return 0

            try:
                ascent, _ = font.getmetrics()
                emoji_y = y + ascent - emoji_size + int(emoji_size * 0.1)
                img = draw._image
                font_size_ratio = emoji_size / 90 if 90 != 0 else 1
                dynamic_offset = int(emoji_size * 0.1 * font_size_ratio)
                paste_y = emoji_y + dynamic_offset
                img.paste(emoji_img, (x, paste_y), emoji_img)
                return emoji_img.width
            except Exception as e:
                print(f"[draw_text_or_emoji] emoji paste 失败 {text}: {e}")
                try:
                    draw.text((x + shadow_offset, y + shadow_offset), EMOJI_FALLBACK_CHAR, font=font, fill=(0, 0, 0))
                    draw.text((x, y), EMOJI_FALLBACK_CHAR, font=font, fill=color)
                    w = int(draw.textlength(EMOJI_FALLBACK_CHAR, font=font))
                    return w
                except Exception as e2:
                    print(f"[draw_text_or_emoji] 替代字符绘制也失败: {e2}")
                    return 0
        else:
            draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0))
            draw.text((x, y), text, font=font, fill=color)
            return int(draw.textlength(text, font=font))

    def wrap_lines_with_measure(txt: str, font: ImageFont.FreeTypeFont, max_w: int):
        lines: list[str] = []
        ascent, descent = font.getmetrics()
        line_h = int((ascent + descent) * (1 + line_spacing))

        max_line_w = 0
        
        measure_cache = {}
        def measure(s: str) -> float:
            if s not in measure_cache:
                measure_cache[s] = draw.textlength(s, font=font)
            return measure_cache[s]
        
        for para in txt.splitlines() or [""]:
            has_space = " " in para
            units = para.split(" ") if has_space else list(para)
            buf = ""

            def unit_join(a: str, b: str) -> str:
                if not a:
                    return b
                return f"{a} {b}" if has_space else f"{a}{b}"

            i = 0
            units_len = len(units)

            while i < units_len:
                trial = unit_join(buf, units[i])
                w = measure(trial)

                if w <= max_w:
                    buf = trial
                    i += 1
                else:
                    if buf:
                        lines.append(buf)
                        max_line_w = max(max_line_w, measure(buf))
                        buf = ""
                    else:
                        if has_space and len(units[i]) > 1:
                            word = units[i]
                            left, right = 1, len(word)

                            while left <= right:
                                mid = (left + right) // 2
                                prefix = word[:mid]
                                if measure(prefix) <= max_w:
                                    left = mid + 1
                                else:
                                    right = mid - 1

                            if right > 0:
                                part = word[:right]
                                lines.append(part)
                                max_line_w = max(max_line_w, measure(part))
                                units[i] = word[right:]
                            else:
                                lines.append(word)
                                max_line_w = max(max_line_w, measure(word))
                                i += 1
                        else:
                            u = units[i]
                            u_w = measure(u)
                            if u_w <= max_w:
                                buf = u
                            else:
                                lines.append(u)
                                max_line_w = max(max_line_w, u_w)
                            i += 1

            if buf:
                lines.append(buf)
                max_line_w = max(max_line_w, measure(buf))

            if para == "" and (not lines or lines[-1] != ""):
                lines.append("")

        total_h = max(line_h * max(1, len(lines)), 1)
        return lines, int(max_line_w), total_h, line_h

    # --- 主函数逻辑开始 ---
    st=time.time()

    if isinstance(image_source, Image.Image):
        img = image_source
    else:
        img = Image.open(image_source).convert("RGBA")

    draw = ImageDraw.Draw(img)

    x1, y1 = top_left
    x2, y2 = bottom_right
    if not (x2 > x1 and y2 > y1):
        raise ValueError("无效的区域。")

    region_w, region_h = x2 - x1, y2 - y1
    
    # 计算文字区域和图片区域
    if content_image is not None and text is not None:
        # 提取emoji并替换为占位符
        placeholder_text, emoji_list = extract_emojis_and_replace(text, PLACEHOLDER_CHAR)
        text_length = len(placeholder_text)
        
        # 获取图片尺寸和特征
        cw, ch = content_image.size
        image_aspect = cw / ch if ch > 0 else 1
        
        # 根据图片宽高比决定基础比例
        if image_aspect > 2:
            # 宽幅图片：需要更多宽度
            base_image_ratio = 0.6
        elif image_aspect > 1:
            # 横版图片
            base_image_ratio = 0.5
        else:
            # 竖版或方形图片
            base_image_ratio = 0.4
        
        # 根据文本长度调整
        if text_length <= 10:
            # 短文本：加大图片比例
            image_ratio = min(base_image_ratio + 0.2, 0.7)
        elif text_length <= 30:
            # 中等文本：保持基础比例
            image_ratio = base_image_ratio
        else:
            # 长文本：减小图片比例
            image_ratio = max(base_image_ratio - 0.1, min_image_ratio)
        
        # 确保图片比例在合理范围内
        image_ratio = max(min(image_ratio, 0.7), min_image_ratio)
        
        # 计算具体宽度
        image_region_w = int(region_w * image_ratio)
        text_region_w = region_w - image_region_w
        
        # 设置矩形区域
        text_rect = (x1, y1, x1 + text_region_w, y2)
        image_rect = (x1 + text_region_w, y1, x2, y2)
        
    elif content_image is not None:
        # 只有图片：使用整个区域
        text_rect = None
        image_rect = (x1, y1, x2, y2)
    elif text is not None:
        # 只有文字：使用整个区域
        text_rect = (x1, y1, x2, y2)
        image_rect = None
    else:
        # 既没有文字也没有图片
        buf = BytesIO()
        img.convert("RGB").save(buf, format="BMP")
        return buf.getvalue()[14:]

    print(f"分区耗时: {int((time.time() - st)*1000)}")
    st=time.time()

    # --- 处理图片部分 ---
    if content_image is not None and image_rect is not None:
        ix1, iy1, ix2, iy2 = image_rect
        region_w_img = max(1, (ix2 - ix1) - 2 * image_padding)
        region_h_img = max(1, (iy2 - iy1) - 2 * image_padding)

        cw, ch = content_image.size
        if cw <= 0 or ch <= 0:
            raise ValueError("content_image 尺寸无效。")

        scale_w = region_w_img / cw
        scale_h = region_h_img / ch
        scale = min(scale_w, scale_h)

        new_w = max(1, int(round(cw * scale)))
        new_h = max(1, int(round(ch * scale)))

        resized = content_image.resize((new_w, new_h), Image.Resampling.BILINEAR)

        if image_align == "left":
            px = ix1 + image_padding
        elif image_align == "center":
            px = ix1 + image_padding + (region_w_img - new_w) // 2
        else:  # "right"
            px = ix2 - image_padding - new_w

        if image_valign == "top":
            py = iy1 + image_padding
        elif image_valign == "middle":
            py = iy1 + image_padding + (region_h_img - new_h) // 2
        else:  # "bottom"
            py = iy2 - image_padding - new_h

        if "A" in resized.getbands():
            img.paste(resized, (px, py), resized)
        else:
            img.paste(resized, (px, py))
        print(f"图片耗时: {int((time.time() - st)*1000)}")
        st=time.time()
        
    # --- 处理文字部分 ---
    if text is not None and text_rect is not None:
        tx1, ty1, tx2, ty2 = text_rect
        region_w_text, region_h_text = tx2 - tx1, ty2 - ty1

        # 提取emoji并替换为占位符
        placeholder_text, emoji_list = extract_emojis_and_replace(text, PLACEHOLDER_CHAR)
        print(f"emoji分析耗时: {int((time.time() - st)*1000)}")
        st=time.time()
        
        # 搜索最大字号
        hi = min(region_h_text, max_font_height) if max_font_height else region_h_text
        lo, best_size, best_lines, best_line_h, best_block_h = 1, 0, [], 0, 0

        while lo <= hi:
            mid = (lo + hi) // 2
            font = load_font(mid)
            lines, w, h, lh = wrap_lines_with_measure(placeholder_text, font, region_w_text)

            if w <= region_w_text and h <= region_h_text:
                best_size, best_lines, best_line_h, best_block_h = mid, lines, lh, h
                lo = mid + 1
            else:
                hi = mid - 1

        if best_size == 0:
            font = load_font(1)
            lines, _, h, lh = wrap_lines_with_measure(placeholder_text, font, region_w_text)
            best_lines, best_block_h, best_line_h = lines, h, lh
            best_size = 1
        else:
            font = load_font(best_size)
            _, _, best_block_h, best_line_h = wrap_lines_with_measure(placeholder_text, font, region_w_text)
        print(f"字号搜索耗时: {int((time.time() - st)*1000)}")
        st=time.time()
        
        # 计算emoji尺寸
        emoji_size = best_size

        # 计算垂直起始位置
        if text_valign == "top":
            y_start = ty1
        elif text_valign == "middle":
            y_start = ty1 + (region_h_text - best_block_h) // 2
        else:  # bottom
            y_start = ty2 - best_block_h

        # 绘制文字
        y_pos = y_start
        bracket_stack = []
        emoji_iter_index = 0
        total_emojis = len(emoji_list)

        # 解析颜色片段
        def parse_color_segments(
            s: str, bracket_stack: list
        ) -> Tuple[list[tuple[str, Tuple[int, int, int]]], list]:
            segs: list[tuple[str, Tuple[int, int, int]]] = []
            buf = ""

            for ch in s:
                if ch in bracket_pairs:
                    if buf:
                        current_color = bracket_color if bracket_stack else color
                        segs.append((buf, current_color))
                        buf = ""

                    if ch in ('"', "'", "`"):
                        if bracket_stack and bracket_stack[-1] == ch:
                            segs.append((ch, bracket_color))
                            bracket_stack.pop()
                        else:
                            segs.append((ch, bracket_color))
                            bracket_stack.append(ch)
                    else:
                        segs.append((ch, bracket_color))
                        bracket_stack.append(ch)

                elif ch in bracket_pairs.values():
                    if buf:
                        segs.append((buf, bracket_color))
                        buf = ""

                    segs.append((ch, bracket_color))

                    if bracket_stack:
                        last_bracket = bracket_stack[-1]
                        if bracket_pairs.get(last_bracket) == ch:
                            bracket_stack.pop()
                else:
                    buf += ch
                    
            if buf:
                current_color = bracket_color if bracket_stack else color
                segs.append((buf, current_color))

            return segs, bracket_stack

        for ln in best_lines:
            line_w = draw.textlength(ln, font=font)

            if text_align == "left":
                x_pos = tx1
            elif text_align == "center":
                x_pos = tx1 + (region_w_text - line_w) // 2
            else:
                x_pos = tx2 - line_w

            segments, bracket_stack = parse_color_segments(ln, bracket_stack)

            for seg_text, seg_color in segments:
                if not seg_text:
                    continue

                i = 0
                L = len(seg_text)
                while i < L:
                    ch = seg_text[i]
                    if ch == PLACEHOLDER_CHAR:
                        if emoji_iter_index < total_emojis:
                            emoji_seq = emoji_list[emoji_iter_index]
                            emoji_iter_index += 1
                            width = draw_text_or_emoji(draw, x_pos, y_pos, emoji_seq, seg_color, emoji_size)
                            x_pos += width
                        else:
                            width = draw_text_or_emoji(draw, x_pos, y_pos, EMOJI_FALLBACK_CHAR, seg_color, None)
                            x_pos += width
                        i += 1
                    else:
                        j = i
                        while j < L and seg_text[j] != PLACEHOLDER_CHAR:
                            j += 1
                        text_fragment = seg_text[i:j]
                        width = draw_text_or_emoji(draw, x_pos, y_pos, text_fragment, seg_color, None)
                        x_pos += width
                        i = j

            y_pos += best_line_h
            if y_pos - y_start > region_h_text:
                break

        if emoji_iter_index < total_emojis:
            print(f"[draw] 警告：有 {total_emojis - emoji_iter_index} 个 emoji 未被绘制（占位符不足）")
        print(f"绘制耗时: {int((time.time() - st)*1000)}")
        st=time.time()
        
    # --- 压缩图片 ---
    if compression_settings is not None:
        reduction_ratio = compression_settings.get("pixel_reduction_ratio", 50) / 100.0
        new_width = max(int(img.width * (1 - reduction_ratio)), 300)
        new_height = max(int(img.height * (1 - reduction_ratio)), 100)
        img = img.resize((new_width, new_height), Image.Resampling.BILINEAR)
        print(f"压缩耗时: {int((time.time() - st)*1000)}")
        st=time.time()

    # --- 输出 BMP ---
    buf = BytesIO()
    img_rgb = img.convert("RGB")
    img_rgb.save(buf, format="BMP")
    bmp_data = buf.getvalue()[14:]
        
    print(f"输出耗时: {int((time.time() - st)*1000)}")
    return bmp_data