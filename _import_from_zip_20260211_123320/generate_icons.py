"""
Generate PWA icons from SVG
Run: python generate_icons.py
Requires: pip install pillow cairosvg
"""
try:
    from PIL import Image, ImageDraw, ImageFont
    import os
    
    # Icon sizes needed for PWA
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    # Create static directory if it doesn't exist
    static_dir = os.path.join(os.path.dirname(__file__), 'app', 'static')
    os.makedirs(static_dir, exist_ok=True)
    
    # Generate icons
    for size in sizes:
        # Create a new image with cBrain blue background
        img = Image.new('RGB', (size, size), color='#1e3a8a')
        draw = ImageDraw.Draw(img)
        
        # Draw a circle
        circle_margin = size // 6
        draw.ellipse(
            [circle_margin, circle_margin, size - circle_margin, size - circle_margin],
            fill='#3b82f6',
            outline='#60a5fa',
            width=max(2, size // 64)
        )
        
        # Try to add text "TW"
        try:
            # Try to use a nice font
            font_size = size // 3
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
            text = "TW"
            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Center the text
            x = (size - text_width) // 2
            y = (size - text_height) // 2 - font_size // 8
            
            draw.text((x, y), text, fill='white', font=font)
        except Exception as e:
            print(f"Could not add text to {size}x{size} icon: {e}")
        
        # Save the icon
        icon_path = os.path.join(static_dir, f'icon-{size}.png')
        img.save(icon_path, 'PNG', optimize=True)
        print(f'✓ Generated {icon_path}')
    
    print(f'\n✅ Generated {len(sizes)} PWA icons successfully!')
    print('Icons saved to: app/static/')
    
except ImportError:
    print('⚠️  Pillow not installed. Installing...')
    import subprocess
    subprocess.check_call(['pip', 'install', 'pillow'])
    print('✓ Pillow installed. Please run this script again.')
except Exception as e:
    print(f'❌ Error generating icons: {e}')
    print('\nYou can also:')
    print('1. Use an online icon generator (e.g., realfavicongenerator.net)')
    print('2. Create icons manually and save them as icon-72.png, icon-96.png, etc.')
