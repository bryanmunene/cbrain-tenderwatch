"""
Generate PWA icons for TenderWatch
Creates PNG icons in various sizes for PWA manifest
"""

import os
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing Pillow...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont

# Icon sizes for PWA
SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

# Colors (cBrain theme)
BG_COLOR = (37, 99, 235)  # Blue
ACCENT_COLOR = (124, 58, 237)  # Purple
TEXT_COLOR = (255, 255, 255)  # White

def create_icon(size):
    """Create a single icon at specified size"""
    # Create image with gradient-like background
    img = Image.new('RGB', (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Draw circular background
    padding = int(size * 0.05)
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=BG_COLOR
    )
    
    # Draw "TW" text
    font_size = int(size * 0.45)
    try:
        # Try to use a system font
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    text = "TW"
    
    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - int(size * 0.05)
    
    # Draw text shadow
    shadow_offset = max(1, int(size * 0.02))
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 100), font=font)
    
    # Draw main text
    draw.text((x, y), text, fill=TEXT_COLOR, font=font)
    
    # Draw small magnifying glass icon (🔍) indicator
    indicator_size = int(size * 0.25)
    indicator_x = size - indicator_size - padding
    indicator_y = size - indicator_size - padding
    
    # Draw indicator circle (magnifying glass body)
    draw.ellipse(
        [indicator_x, indicator_y, indicator_x + indicator_size * 0.7, indicator_y + indicator_size * 0.7],
        outline=TEXT_COLOR,
        width=max(1, int(size * 0.03))
    )
    
    # Draw handle
    handle_start = (indicator_x + indicator_size * 0.55, indicator_y + indicator_size * 0.55)
    handle_end = (indicator_x + indicator_size * 0.9, indicator_y + indicator_size * 0.9)
    draw.line([handle_start, handle_end], fill=TEXT_COLOR, width=max(1, int(size * 0.03)))
    
    return img

def main():
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(script_dir, 'static', 'icons')
    
    # Create icons directory if needed
    os.makedirs(icons_dir, exist_ok=True)
    
    print("Generating TenderWatch PWA icons...")
    
    for size in SIZES:
        icon = create_icon(size)
        filename = os.path.join(icons_dir, f'icon-{size}.png')
        icon.save(filename, 'PNG')
        print(f"  ✓ Created icon-{size}.png")
    
    # Also create favicon.ico
    icon_16 = create_icon(16)
    icon_32 = create_icon(32)
    icon_48 = create_icon(48)
    favicon_path = os.path.join(icons_dir, 'favicon.ico')
    icon_32.save(favicon_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"  ✓ Created favicon.ico")
    
    # Create apple-touch-icon
    apple_icon = create_icon(180)
    apple_icon.save(os.path.join(icons_dir, 'apple-touch-icon.png'), 'PNG')
    print(f"  ✓ Created apple-touch-icon.png")
    
    print(f"\n✅ All icons saved to: {icons_dir}")

if __name__ == "__main__":
    main()
