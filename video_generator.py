import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.video.VideoClip import VideoClip
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
)
from moviepy.audio.fx import all as afx
import os
import tempfile
import urllib.request


class VideoGenerator:
    def __init__(self, width: int, height: int):
        self.VIDEO_WIDTH = width
        self.VIDEO_HEIGHT = height
        self.VIDEO_SIZE = (width, height)
        # Dynamic font size: 4% of video height
        self.font_size = int(self.VIDEO_HEIGHT * 0.04)
        self.font = self._load_font()

    def _apply_effect(self, clip: ImageClip, effect: str, duration: float) -> ImageClip:
        """Apply a simple pan or zoom effect to the clip."""
        speed = 50

        def scaled(clip, dim, dur):
            dist = speed * dur
            scale = 1 + 2 * dist / dim
            c = clip.resize(scale)
            offset = (c.w - self.VIDEO_WIDTH) / 2 if dim == clip.w else (c.h - self.VIDEO_HEIGHT) / 2
            return c, offset

        if effect == "zoom_in":
            return clip.resize(lambda t: 1 + 0.1 * t / duration)
        if effect == "zoom_out":
            return clip.resize(lambda t: 1 + 0.1 * (1 - t / duration))
        if effect == "pan_left":
            clip, off = scaled(clip, clip.w, duration)
            return clip.set_position(lambda t: (-speed * t - off, "center"))
        if effect == "pan_right":
            clip, off = scaled(clip, clip.w, duration)
            return clip.set_position(lambda t: (speed * t - off, "center"))
        if effect == "pan_up":
            clip, off = scaled(clip, clip.h, duration)
            return clip.set_position(lambda t: ("center", -speed * t - off))
        if effect == "pan_down":
            clip, off = scaled(clip, clip.h, duration)
            return clip.set_position(lambda t: ("center", speed * t - off))
        return clip

    def _load_font(self):
        """Load a font, downloading Montserrat if necessary, with fallback to default."""
        temp_dir = tempfile.gettempdir()
        font_path = os.path.join(temp_dir, "Montserrat-Bold.ttf")
        try:
            if not os.path.exists(font_path):
                font_url = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"
                urllib.request.urlretrieve(font_url, font_path)
            return ImageFont.truetype(font_path, self.font_size)
        except Exception:
            pass
        system_fonts = [
            "Impact.ttf",
            "arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        for font in system_fonts:
            try:
                return ImageFont.truetype(font, self.font_size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _wrap_words_into_lines(self, text: str, max_width: int):
        dummy = Image.new("RGB", (max_width, 200))
        draw = ImageDraw.Draw(dummy)
        words = text.split()
        lines = []
        current_line = []
        current_width = 0
        max_height = 0
        for w in words:
            w_width, w_height = draw.textsize(w, font=self.font)
            space_w, _ = draw.textsize(" ", font=self.font)
            new_width = w_width if not current_line else current_width + space_w + w_width
            if new_width <= max_width:
                current_line.append(w)
                current_width = new_width
                max_height = max(max_height, w_height)
            else:
                if current_line:
                    lines.append((current_line, current_width, max_height))
                current_line = [w]
                current_width = w_width
                max_height = w_height
        if current_line:
            lines.append((current_line, current_width, max_height))
        return lines

    def generate_dynamic_subtitle(self, text: str, duration: float) -> VideoClip:
        safe_text = text.encode("utf-8", errors="replace").decode("utf-8")
        max_text_width = int(self.VIDEO_WIDTH * 0.85)
        lines_data = self._wrap_words_into_lines(safe_text, max_text_width)
        total_words = sum(len(line[0]) for line in lines_data)
        pairs = [lines_data[i:i+2] for i in range(0, len(lines_data), 2)]
        pair_counts = [sum(len(line[0]) for line in pair) for pair in pairs]
        cum_counts = []
        cum = 0
        for c in pair_counts:
            cum += c
            cum_counts.append(cum)

        def make_frame(t: float):
            word_time = duration / total_words
            global_idx = min(int(t / word_time), total_words - 1)
            pair_idx = next(i for i, cum in enumerate(cum_counts) if global_idx < cum)
            prev_cum = cum_counts[pair_idx - 1] if pair_idx > 0 else 0
            local_idx = global_idx - prev_cum
            vis_lines = pairs[pair_idx]
            widths, heights = zip(*( (line[1], line[2]) for line in vis_lines ))
            max_w = min(max(widths), max_text_width)
            line_spacing = max(10, int(self.VIDEO_HEIGHT * 0.005))
            total_h = sum(heights) + line_spacing * (len(heights)-1) if len(heights) > 1 else sum(heights)
            pad = int(min(self.VIDEO_WIDTH, self.VIDEO_HEIGHT) * 0.03)
            bg = Image.new("RGBA", (max_w + 2*pad, total_h + 2*pad), (0, 0, 0, 0))
            draw_bg = ImageDraw.Draw(bg)
            draw_bg.rounded_rectangle([(0,0),(bg.width,bg.height)], radius=15, fill=(0,0,0,180))
            bg = bg.filter(ImageFilter.GaussianBlur(5))
            draw = ImageDraw.Draw(bg)
            y = pad
            count = 0
            for words, w, h in vis_lines:
                x = pad + (max_w - w) // 2
                for word in words:
                    fill = "red" if count == local_idx else "yellow"
                    draw.text((x, y), word, font=self.font, fill=fill,
                              stroke_width=3, stroke_fill="black")
                    sw, _ = draw.textsize(" ", font=self.font)
                    x += draw.textsize(word, font=self.font)[0] + sw
                    count += 1
                y += h + line_spacing
            return np.array(bg.convert("RGB"))

        return VideoClip(make_frame, duration=duration)

    def generate_scene_clip(self, scene_data: dict) -> VideoClip:
        audio = AudioFileClip(scene_data["audioPath"])
        duration = audio.duration
        img = ImageClip(scene_data["imagePath"]).set_duration(duration)
        img = img.resize(height=self.VIDEO_HEIGHT)
        if img.w > self.VIDEO_WIDTH:
            img = img.crop(x_center=img.w/2, width=self.VIDEO_WIDTH)
        else:
            img = img.resize(width=self.VIDEO_WIDTH)
        effect = scene_data.get("effect", "none")
        img = self._apply_effect(img, effect, duration)
        subtitle_y = int(self.VIDEO_HEIGHT * 0.625)
        subtitle = self.generate_dynamic_subtitle(scene_data["script"], duration).set_position(("center", subtitle_y))
        clip = CompositeVideoClip([img, subtitle], size=self.VIDEO_SIZE).set_duration(duration).set_audio(audio)
        return clip

    def create_final_video(self, data: dict, output_file: str, bg_music_path: str | None = None):
        clips = []
        total = int(data.get("scenes", len([k for k in data if k.isdigit()])))
        for i in range(1, total + 1):
            key = str(i)
            if key in data:
                clips.append(self.generate_scene_clip(data[key]))
        final = concatenate_videoclips(clips, method="compose")
        bg_path = bg_music_path or os.path.join("data", "news-bg-music.mp3")
        if os.path.exists(bg_path):
            try:
                bg_music = AudioFileClip(bg_path)
                bg_music = afx.audio_loop(bg_music, duration=final.duration)
                bg_music = bg_music.volumex(0.05)
                final_audio = CompositeAudioClip([final.audio, bg_music])
                final = final.set_audio(final_audio)
            except Exception:
                pass
        final.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, audio=True)
