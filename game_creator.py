import os
import re
import json
import time
import zipfile

def package_playable_game(game_code, game_title="Custom Game", game_type="html", output_folder="generated"):
    """
    Package code into a complete, standalone, playable game file
    with a Windows .bat launcher and a ready-to-play ZIP archive.
    """
    ts = int(time.time())
    clean_title = re.sub(r'[^a-zA-Z0-9_]', '_', game_title).strip('_') or "MyGame"
    os.makedirs(output_folder, exist_ok=True)
    
    generated_items = []
    
    if game_type == "html" or "<!doctype html>" in game_code.lower() or "<canvas" in game_code.lower() or "<html" in game_code.lower():
        html_filename = f"{clean_title}_{ts}.html"
        html_path = os.path.join(output_folder, html_filename)
        
        # Ensure complete standalone HTML structure
        complete_html = game_code
        if "<!doctype html>" not in game_code.lower() and "<html" not in game_code.lower():
            complete_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{game_title}</title>
    <style>
        body {{
            margin: 0;
            background: #111;
            color: #fff;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
        }}
        canvas {{
            border: 2px solid #4D6BFE;
            box-shadow: 0 0 20px rgba(77, 107, 254, 0.4);
            border-radius: 8px;
            background: #000;
        }}
        .game-controls {{
            margin-top: 10px;
            color: #aaa;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    {game_code}
</body>
</html>"""

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(complete_html)
            
        # Create Windows 1-click batch launcher
        bat_filename = f"Play_{clean_title}.bat"
        bat_content = f"""@echo off
echo ========================================================
echo Launching {game_title}...
echo Created with Kaleb AI
echo ========================================================
start "" "{html_filename}"
"""
        
        # Bundle into a portable ZIP package
        zip_filename = f"Playable_Game_{clean_title}_{ts}.zip"
        zip_path = os.path.join(output_folder, zip_filename)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(html_filename, complete_html)
            zf.writestr(bat_filename, bat_content)
            zf.writestr("README.txt", f"""{game_title}
Created by Kaleb AI

HOW TO PLAY:
1. Double-click '{bat_filename}' (or open '{html_filename}' in any web browser like Chrome, Edge, or Firefox).
2. Enjoy playing your game offline anytime!
""")

        generated_items.append({
            'filename': html_filename,
            'path': f'/download/generated/{html_filename}',
            'play_url': f'/play/generated/{html_filename}',
            'size': os.path.getsize(html_path),
            'language': 'html',
            'is_game': True,
            'game_title': game_title,
            'badge': f'🎮 Playable Game File ({html_filename})'
        })
        
        generated_items.append({
            'filename': zip_filename,
            'path': f'/download/generated/{zip_filename}',
            'size': os.path.getsize(zip_path),
            'language': 'zip',
            'is_game_package': True,
            'badge': f'📦 1-Click Game Package (.zip with Windows .bat Launcher)'
        })
        
    elif game_type == "python" or "import pygame" in game_code or "import turtle" in game_code or "import tkinter" in game_code or "def " in game_code:
        py_filename = f"{clean_title}_{ts}.py"
        py_path = os.path.join(output_folder, py_filename)
        with open(py_path, 'w', encoding='utf-8') as f:
            f.write(game_code)
            
        bat_filename = f"Play_{clean_title}.bat"
        bat_content = f"""@echo off
echo ========================================================
echo Launching {game_title}...
echo Created with Kaleb AI
echo ========================================================
python "{py_filename}"
if %errorlevel% neq 0 (
    echo.
    echo Game closed or error encountered.
    pause
)
"""
        
        zip_filename = f"Playable_Python_Game_{clean_title}_{ts}.zip"
        zip_path = os.path.join(output_folder, zip_filename)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(py_filename, game_code)
            zf.writestr(bat_filename, bat_content)
            zf.writestr("README.txt", f"""{game_title} (Python Edition)
Created by Kaleb AI

HOW TO PLAY:
1. Double-click '{bat_filename}' to launch the game directly on your computer!
2. You can also run 'python {py_filename}' from a command prompt.
""")

        generated_items.append({
            'filename': py_filename,
            'path': f'/download/generated/{py_filename}',
            'size': os.path.getsize(py_path),
            'language': 'python',
            'is_game': True,
            'game_title': game_title,
            'badge': f'🐍 Playable Python Game File ({py_filename})'
        })
        
        generated_items.append({
            'filename': zip_filename,
            'path': f'/download/generated/{zip_filename}',
            'size': os.path.getsize(zip_path),
            'language': 'zip',
            'is_game_package': True,
            'badge': f'📦 1-Click Python Game (.zip with .bat Launcher)'
        })

    return generated_items
