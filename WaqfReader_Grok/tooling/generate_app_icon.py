"""Generate وقف وابتداء app icons across branding, Android, iOS, Web, and Windows from the master artwork."""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'assets', 'branding')
MASTER_PATH = os.path.join(OUT_DIR, 'app_icon_master.png')
RES_DIR = os.path.join(ROOT, 'android', 'app', 'src', 'main', 'res')
WEB_DIR = os.path.join(ROOT, 'web')
WEB_ICONS_DIR = os.path.join(WEB_DIR, 'icons')
IOS_ICON_DIR = os.path.join(
    ROOT, 'ios', 'Runner', 'Assets.xcassets', 'AppIcon.appiconset'
)
WINDOWS_ICO_PATH = os.path.join(
    ROOT, 'windows', 'runner', 'resources', 'app_icon.ico'
)

DEFAULT_SOURCE = (
    r'C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84'
    r'\waqf_ibtida_app_icon_1794600211758.jpg'
)


def _rounded_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    """Create an anti-aliased rounded-square mask via 4x supersampling."""
    scale = 4
    hi = size * scale
    mask = Image.new('L', (hi, hi), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(round(hi * radius_ratio))
    draw.rounded_rectangle([0, 0, hi - 1, hi - 1], radius=radius, fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def _render_icon(master: Image.Image, size: int, *, rounded: bool) -> Image.Image:
    resized = master.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
    if not rounded:
        return resized
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(resized, (0, 0), _rounded_mask(size))
    return out


def _render_adaptive_foreground(master: Image.Image, size: int) -> Image.Image:
    """Scale master artwork onto Android's 108dp adaptive foreground canvas.

    Scales the artwork to ~86% with feathered edges so the Mushaf & Rub el Hizb emblem
    sits with comfortable breathing room inside Android's 72dp circle/squircle safe zone
    and blends smoothly into @color/ic_launcher_background (#073E29).
    """
    inner = max(1, int(round(size * 0.86)))
    scaled = master.convert('RGBA').resize((inner, inner), Image.Resampling.LANCZOS)

    mask = Image.new('L', (inner, inner), 0)
    inset = max(2, int(round(inner * 0.08)))
    ImageDraw.Draw(mask).rounded_rectangle(
        [inset, inset, inner - inset - 1, inner - inset - 1],
        radius=max(4, int(round(inner * 0.16))),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(1.5, inner * 0.045)))

    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    offset = (size - inner) // 2
    out.paste(scaled, (offset, offset), mask)
    return out


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(WEB_ICONS_DIR, exist_ok=True)

    if not os.path.exists(MASTER_PATH):
        if os.path.exists(DEFAULT_SOURCE):
            Image.open(DEFAULT_SOURCE).convert('RGB').save(MASTER_PATH, 'PNG')
        else:
            raise FileNotFoundError(f'Missing master artwork at {MASTER_PATH}')

    master = Image.open(MASTER_PATH)

    # Branding masters
    _render_icon(master, 1024, rounded=True).save(os.path.join(OUT_DIR, 'app_icon_1024.png'), 'PNG')
    _render_icon(master, 1024, rounded=False).save(os.path.join(OUT_DIR, 'app_icon_1024_full.png'), 'PNG')
    _render_icon(master, 512, rounded=True).save(os.path.join(OUT_DIR, 'app_icon_512.png'), 'PNG')

    # Android legacy launcher icons + adaptive foregrounds
    android_mipmaps = {
        'mipmap-mdpi': (48, 108),
        'mipmap-hdpi': (72, 162),
        'mipmap-xhdpi': (96, 216),
        'mipmap-xxhdpi': (144, 324),
        'mipmap-xxxhdpi': (192, 432),
    }
    for folder, (legacy_sz, fg_sz) in android_mipmaps.items():
        folder_path = os.path.join(RES_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)
        _render_icon(master, legacy_sz, rounded=True).save(
            os.path.join(folder_path, 'ic_launcher.png'), 'PNG'
        )
        _render_adaptive_foreground(master, fg_sz).save(
            os.path.join(folder_path, 'ic_launcher_foreground.png'), 'PNG'
        )
        print('wrote android', folder, f'({legacy_sz}px / fg {fg_sz}px)')

    # Web icons & favicon
    _render_icon(master, 192, rounded=True).save(os.path.join(WEB_ICONS_DIR, 'Icon-192.png'), 'PNG')
    _render_icon(master, 512, rounded=True).save(os.path.join(WEB_ICONS_DIR, 'Icon-512.png'), 'PNG')
    _render_icon(master, 192, rounded=False).save(os.path.join(WEB_ICONS_DIR, 'Icon-maskable-192.png'), 'PNG')
    _render_icon(master, 512, rounded=False).save(os.path.join(WEB_ICONS_DIR, 'Icon-maskable-512.png'), 'PNG')
    _render_icon(master, 64, rounded=True).save(os.path.join(WEB_DIR, 'favicon.png'), 'PNG')

    # iOS AppIcon set (opaque PNGs required by Xcode)
    if os.path.isdir(IOS_ICON_DIR):
        ios_specs = {
            'Icon-App-20x20@1x.png': 20,
            'Icon-App-20x20@2x.png': 40,
            'Icon-App-20x20@3x.png': 60,
            'Icon-App-29x29@1x.png': 29,
            'Icon-App-29x29@2x.png': 58,
            'Icon-App-29x29@3x.png': 87,
            'Icon-App-40x40@1x.png': 40,
            'Icon-App-40x40@2x.png': 80,
            'Icon-App-40x40@3x.png': 120,
            'Icon-App-60x60@2x.png': 120,
            'Icon-App-60x60@3x.png': 180,
            'Icon-App-76x76@1x.png': 76,
            'Icon-App-76x76@2x.png': 152,
            'Icon-App-83.5x83.5@2x.png': 167,
            'Icon-App-1024x1024@1x.png': 1024,
        }
        for fname, sz in ios_specs.items():
            master.convert('RGB').resize((sz, sz), Image.Resampling.LANCZOS).save(
                os.path.join(IOS_ICON_DIR, fname), 'PNG'
            )
        print('wrote iOS AppIcon set:', len(ios_specs), 'sizes')

    # Windows multi-resolution ICO
    if os.path.isdir(os.path.dirname(WINDOWS_ICO_PATH)):
        win_base = _render_icon(master, 256, rounded=True)
        win_base.save(
            WINDOWS_ICO_PATH,
            format='ICO',
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        print('wrote', WINDOWS_ICO_PATH)

    print('all platform icons updated cleanly')


if __name__ == '__main__':
    main()
