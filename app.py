import os
import re
import time
import uuid
import json
import urllib.request
import urllib.error
from flask import Flask, request, render_template, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import minecraft_creator
import game_creator

app = Flask(__name__)

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
GENERATED_FOLDER = os.path.join(BASE_DIR, 'generated')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload

TEXT_EXTENSIONS = {
    'txt', 'md', 'py', 'js', 'jsx', 'ts', 'tsx', 'html', 'css', 'json', 
    'csv', 'xml', 'yaml', 'yml', 'sql', 'sh', 'bat', 'ps1', 'c', 'cpp', 
    'h', 'java', 'rs', 'go', 'php', 'rb', 'ini', 'cfg', 'log', 'env',
    'mcmeta', 'mcfunction'
}

def extract_file_content(filepath, max_chars=16000):
    """Read text from supported file types for AI context."""
    ext = filepath.split('.')[-1].lower() if '.' in filepath else ''
    if ext in TEXT_EXTENSIONS:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(max_chars)
                if len(content) >= max_chars:
                    content += "\n...[Content truncated for length]..."
                return content
        except Exception as e:
            return f"[Error reading file: {e}]"
    return f"[Binary file: {os.path.basename(filepath)} ({os.path.getsize(filepath)} bytes)]"

def call_free_reasoning_ai(messages, model="openai-fast", timeout=80):
    """Call high-tier 20B Reasoning AI (100% free, zero login, zero API key)."""
    url = f"https://text.pollinations.ai/{model}"
    payload = {
        "messages": messages,
        "temperature": 0.7
    }
    data_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json", "User-Agent": "KalebAI/1.0"},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        msg = res['choices'][0]['message']
        return msg.get('reasoning', ''), msg.get('content', '')

def call_deepseek_api(api_key, messages, model="deepseek-reasoner", timeout=60):
    """Call official DeepSeek cloud API."""
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.6
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        msg = res['choices'][0]['message']
        return msg.get('reasoning_content', ''), msg.get('content', '')

def call_groq_api(api_key, messages, model="deepseek-r1-distill-llama-70b", timeout=60):
    """Call Groq free tier API for ultra-fast DeepSeek-R1 70B."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.6
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        msg = res['choices'][0]['message']
        content = msg.get('content', '')
        reasoning = ''
        if '<think>' in content and '</think>' in content:
            parts = content.split('</think>', 1)
            reasoning = parts[0].replace('<think>', '').strip()
            content = parts[1].strip()
        return reasoning, content

def extract_minecraft_files(text):
    """Extract individual files and paths for Datapacks, Resource packs, and Mods."""
    files = {}
    # 1. Match code blocks with file path hints: ```json pack.mcmeta or ```mcfunction data/custom/functions/tick.mcfunction
    pattern = r'```(?:[a-zA-Z0-9_\-]+)?(?:\s+([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+))\n(.*?)```'
    for path_hint, code in re.findall(pattern, text, re.DOTALL):
        clean_p = path_hint.strip().replace('\\', '/')
        if clean_p and len(code.strip()) > 0:
            files[clean_p] = code.strip()
            
    # 2. Also check for lines like: ### `pack.mcmeta` or **File: `data/...`** followed by a code block
    section_pattern = r'(?:###|\*\*|File:?)\s*`?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)`?.*?\n\s*```(?:[a-zA-Z0-9_\-]+)?\n(.*?)```'
    for path_hint, code in re.findall(section_pattern, text, re.DOTALL):
        clean_p = path_hint.strip().replace('\\', '/')
        if clean_p and clean_p not in files and len(code.strip()) > 0:
            files[clean_p] = code.strip()

    return files

def handle_minecraft_creation(prompt, answer_text, attached_files=None):
    """
    Detect if the user requested a Minecraft Skin, Data Pack, Resource Pack, or Mod,
    or requested to merge existing mods/packs, and automatically compile ready-to-use files.
    """
    generated_mc_files = []
    p_lower = prompt.lower()
    ts = int(time.time())
    attached_files = attached_files or []

    # 0. MERGE MINECRAFT MODS / ARCHIVES
    is_merge_req = "merge" in p_lower or "combine" in p_lower
    zip_jar_paths = []
    for fname in attached_files:
        if fname.lower().endswith('.zip') or fname.lower().endswith('.jar'):
            fpath = os.path.join(UPLOAD_FOLDER, secure_filename(fname))
            if not os.path.exists(fpath):
                fpath = os.path.join(GENERATED_FOLDER, secure_filename(fname))
            if os.path.exists(fpath):
                zip_jar_paths.append(fpath)

    if is_merge_req and len(zip_jar_paths) >= 2:
        merged_zip_name = f"Merged_Minecraft_Mod_{ts}.zip"
        merged_zip_path = os.path.join(GENERATED_FOLDER, merged_zip_name)
        try:
            m_res = minecraft_creator.merge_minecraft_archives(
                zip_jar_paths,
                merged_zip_path,
                merged_name="Merged_Mod"
            )
            generated_mc_files.append({
                'filename': merged_zip_name,
                'path': f'/download/generated/{merged_zip_name}',
                'size': os.path.getsize(merged_zip_path),
                'language': 'zip',
                'is_minecraft_pack': True,
                'badge': f'🔀 Merged Minecraft Mod Package ({len(zip_jar_paths)} mods combined into .zip)'
            })
        except Exception as e:
            print(f"Error merging mod archives: {e}")

    # 1. MINECRAFT SKIN
    if "skin" in p_lower and ("minecraft" in p_lower or "player" in p_lower or "skin" in p_lower):
        theme = "adventurer"
        if "ender" in p_lower or "purple" in p_lower: theme = "ender"
        elif "knight" in p_lower or "armor" in p_lower or "iron" in p_lower: theme = "knight"
        elif "creeper" in p_lower or "green" in p_lower: theme = "creeper"
        elif "nether" in p_lower or "fire" in p_lower or "demon" in p_lower or "red" in p_lower: theme = "nether"
        elif "cyber" in p_lower or "neon" in p_lower or "blue" in p_lower or "robot" in p_lower: theme = "cyber"
        elif "gold" in p_lower or "king" in p_lower or "royal" in p_lower: theme = "gold"

        skin_filename = f"Minecraft_Skin_{theme.capitalize()}_{ts}.png"
        skin_path = os.path.join(GENERATED_FOLDER, skin_filename)
        try:
            minecraft_creator.generate_minecraft_skin(skin_path, theme=theme)
            generated_mc_files.append({
                'filename': skin_filename,
                'path': f'/download/generated/{skin_filename}',
                'size': os.path.getsize(skin_path),
                'language': 'png',
                'is_skin': True,
                'badge': '👕 64x64 Minecraft Player Skin (.png)'
            })
        except Exception as e:
            print(f"Error generating skin: {e}")

    # 2. MINECRAFT DATA PACK / RESOURCE PACK / MOD PACKAGING
    mc_files = extract_minecraft_files(answer_text)
    
    # If datapack is requested or mcfunction/data tags detected
    is_datapack_req = "data pack" in p_lower or "datapack" in p_lower or any(".mcfunction" in f or "data/" in f for f in mc_files)
    if is_datapack_req:
        # If files were not explicitly extracted from markdown headers, scan for raw code blocks
        if not mc_files:
            mc_funcs = re.findall(r'```(?:mcfunction|bash|sh|text)?\n(.*?)```', answer_text, re.DOTALL)
            if mc_funcs:
                mc_files['data/custom/functions/tick.mcfunction'] = mc_funcs[0].strip()
                if len(mc_funcs) > 1:
                    mc_files['data/custom/functions/load.mcfunction'] = mc_funcs[1].strip()

        if mc_files or "datapack" in p_lower:
            pack_name = "Custom_Datapack"
            words = [w for w in re.findall(r'\b[A-Za-z]+\b', prompt) if w.lower() not in {'make', 'a', 'the', 'minecraft', 'data', 'pack', 'datapack', 'create'}]
            if words: pack_name = f"Datapack_{words[0].capitalize()}"
            
            zip_filename = f"{pack_name}_{ts}.zip"
            zip_path = os.path.join(GENERATED_FOLDER, zip_filename)
            try:
                minecraft_creator.build_minecraft_datapack_zip(
                    zip_path, 
                    pack_name=pack_name, 
                    description=f"{pack_name} - Created with Kaleb AI", 
                    files_map=mc_files
                )
                generated_mc_files.append({
                    'filename': zip_filename,
                    'path': f'/download/generated/{zip_filename}',
                    'size': os.path.getsize(zip_path),
                    'language': 'zip',
                    'is_minecraft_pack': True,
                    'badge': '📦 Working Minecraft Data Pack (.zip)'
                })
            except Exception as e:
                print(f"Error packaging datapack: {e}")

    # Resource Pack
    is_resourcepack_req = "resource pack" in p_lower or "texture pack" in p_lower or "resourcepack" in p_lower or any("assets/" in f for f in mc_files)
    if is_resourcepack_req:
        pack_name = "Custom_Resourcepack"
        words = [w for w in re.findall(r'\b[A-Za-z]+\b', prompt) if w.lower() not in {'make', 'a', 'the', 'minecraft', 'resource', 'texture', 'pack', 'resourcepack', 'create'}]
        if words: pack_name = f"Resourcepack_{words[0].capitalize()}"
        
        zip_filename = f"{pack_name}_{ts}.zip"
        zip_path = os.path.join(GENERATED_FOLDER, zip_filename)
        try:
            minecraft_creator.build_minecraft_resourcepack_zip(
                zip_path,
                pack_name=pack_name,
                description=f"{pack_name} - Created with Kaleb AI", 
                files_map=mc_files
            )
            generated_mc_files.append({
                'filename': zip_filename,
                'path': f'/download/generated/{zip_filename}',
                'size': os.path.getsize(zip_path),
                'language': 'zip',
                'is_minecraft_pack': True,
                'badge': '🎨 Working Minecraft Resource Pack (.zip)'
            })
        except Exception as e:
            print(f"Error packaging resourcepack: {e}")

    # Fabric / Forge Mod
    is_mod_req = ("mod" in p_lower and "minecraft" in p_lower) or "fabric mod" in p_lower or "forge mod" in p_lower or any("fabric.mod.json" in f or "build.gradle" in f for f in mc_files)
    if is_mod_req and not is_datapack_req:
        mod_name = "CustomMod"
        words = [w for w in re.findall(r'\b[A-Za-z]+\b', prompt) if w.lower() not in {'make', 'a', 'the', 'minecraft', 'mod', 'fabric', 'forge', 'create', 'that'}]
        if words: mod_name = f"{words[0].capitalize()}Mod"
        
        zip_filename = f"{mod_name}_{ts}.zip"
        zip_path = os.path.join(GENERATED_FOLDER, zip_filename)
        try:
            minecraft_creator.build_minecraft_fabric_mod_zip(
                zip_path,
                mod_id=mod_name.lower(),
                mod_name=mod_name,
                files_map=mc_files
            )
            generated_mc_files.append({
                'filename': zip_filename,
                'path': f'/download/generated/{zip_filename}',
                'size': os.path.getsize(zip_path),
                'language': 'zip',
                'is_minecraft_pack': True,
                'badge': '⚙️ Complete Minecraft Fabric Mod Project (.zip)'
            })
        except Exception as e:
            print(f"Error packaging mod: {e}")

    return generated_mc_files

def handle_game_creation(prompt, answer_text):
    """
    Detect if the user requested a playable game, extract the game code,
    and package it into a complete, playable game file + Windows launcher + ZIP.
    """
    generated_game_items = []
    p_lower = prompt.lower()
    is_game_req = any(k in p_lower for k in [
        "game", "arcade", "flappy", "shooter", "platformer", "pong", "snake", 
        "pacman", "survival", "racing", "runner", "puzzle", "rpg", "invaders"
    ])
    
    # Extract code blocks
    pattern = r'```([a-zA-Z0-9_\-\.]+)?(?:\s+([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+))?\n(.*?)```'
    matches = re.findall(pattern, answer_text, re.DOTALL)
    
    for lang, hint, code in matches:
        code_str = code.strip()
        lang_str = (lang or "").lower()
        
        # Check if it's HTML/Canvas game
        if "<canvas" in code_str.lower() or ("<html" in code_str.lower() and ("game" in code_str.lower() or "score" in code_str.lower() or "requestanimationframe" in code_str.lower())):
            title = "My_Game"
            title_match = re.search(r'<title>(.*?)</title>', code_str, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                words = [w for w in re.findall(r'\b[A-Za-z]+\b', prompt) if w.lower() not in {'make', 'a', 'the', 'game', 'play', 'playable', 'create', 'write', 'me', 'able', 'to', 'and', 'give'}]
                if words: title = f"{words[0].capitalize()}_Game"
                
            items = game_creator.package_playable_game(code_str, game_title=title, game_type="html", output_folder=GENERATED_FOLDER)
            generated_game_items.extend(items)
            break
            
        # Check if it's Python game
        elif is_game_req and (lang_str in ['python', 'py'] or 'import pygame' in code_str or 'import turtle' in code_str or 'import tkinter' in code_str):
            title = "My_Python_Game"
            words = [w for w in re.findall(r'\b[A-Za-z]+\b', prompt) if w.lower() not in {'make', 'a', 'the', 'game', 'play', 'playable', 'create', 'write', 'me', 'able', 'to', 'and', 'give'}]
            if words: title = f"{words[0].capitalize()}_Game"
            items = game_creator.package_playable_game(code_str, game_title=title, game_type="python", output_folder=GENERATED_FOLDER)
            generated_game_items.extend(items)
            break
            
    return generated_game_items

def extract_code_and_save_files(text):
    """Detect code blocks in AI response and automatically save them as downloadable files."""
    saved_files = []
    pattern = r'```([a-zA-Z0-9_\-\.]+)?(?:\s+([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+))?\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    ext_map = {
        'python': 'py', 'py': 'py', 'javascript': 'js', 'js': 'js',
        'html': 'html', 'css': 'css', 'json': 'json', 'markdown': 'md',
        'md': 'md', 'bash': 'sh', 'sh': 'sh', 'powershell': 'ps1', 'ps1': 'ps1',
        'c': 'c', 'cpp': 'cpp', 'java': 'java', 'sql': 'sql', 'text': 'txt', 'txt': 'txt',
        'mcfunction': 'mcfunction', 'mcmeta': 'mcmeta'
    }
    
    for idx, (lang, filename_hint, code) in enumerate(matches):
        code = code.strip()
        if not code or len(code) < 15:
            continue
            
        lang = lang.lower().strip() if lang else 'txt'
        ext = ext_map.get(lang, 'txt')
        
        if filename_hint:
            filename = secure_filename(filename_hint)
        else:
            filename = f"deepseek_{lang}_{int(time.time())}_{idx+1}.{ext}"
            
        file_path = os.path.join(GENERATED_FOLDER, filename)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            saved_files.append({
                'filename': filename,
                'path': f'/download/generated/{filename}',
                'size': len(code.encode('utf-8')),
                'language': lang
            })
        except Exception as e:
            print(f"Error saving code file: {e}")
            
    return saved_files

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all uploaded and generated files with metadata."""
    files = []
    
    if os.path.exists(UPLOAD_FOLDER):
        for fname in os.listdir(UPLOAD_FOLDER):
            fpath = os.path.join(UPLOAD_FOLDER, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                files.append({
                    'name': fname,
                    'type': 'upload',
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'download_url': f'/download/uploads/{fname}'
                })
                
    if os.path.exists(GENERATED_FOLDER):
        for fname in os.listdir(GENERATED_FOLDER):
            fpath = os.path.join(GENERATED_FOLDER, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                files.append({
                    'name': fname,
                    'type': 'generated',
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'download_url': f'/download/generated/{fname}'
                })
                
    files.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify({'files': files})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload files and prepare them for AI reading."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    uploaded_files = request.files.getlist('file')
    results = []
    
    for file in uploaded_files:
        if file.filename == '':
            continue
        clean_name = secure_filename(file.filename)
        base, ext = os.path.splitext(clean_name)
        target_name = clean_name
        counter = 1
        while os.path.exists(os.path.join(UPLOAD_FOLDER, target_name)):
            target_name = f"{base}_{counter}{ext}"
            counter += 1
            
        target_path = os.path.join(UPLOAD_FOLDER, target_name)
        file.save(target_path)
        
        preview = extract_file_content(target_path, max_chars=1200)
        results.append({
            'filename': target_name,
            'download_url': f'/download/uploads/{target_name}',
            'size': os.path.getsize(target_path),
            'preview': preview
        })
        
    return jsonify({'message': f'Uploaded {len(results)} file(s)', 'files': results})

@app.route('/api/delete_file', methods=['POST'])
def delete_file():
    data = request.get_json() or {}
    folder_type = data.get('folder', 'uploads')
    filename = secure_filename(data.get('filename', ''))
    
    folder = UPLOAD_FOLDER if folder_type == 'uploads' else GENERATED_FOLDER
    target = os.path.join(folder, filename)
    
    if os.path.exists(target) and os.path.isfile(target):
        os.remove(target)
        return jsonify({'success': True, 'message': f'Deleted {filename}'})
    return jsonify({'error': 'File not found'}), 404

@app.route('/download/<folder>/<path:filename>')
def download_file(folder, filename):
    safe_name = secure_filename(filename)
    target_dir = UPLOAD_FOLDER if folder == 'uploads' else GENERATED_FOLDER
    return send_from_directory(target_dir, safe_name, as_attachment=True)

@app.route('/play/generated/<path:filename>')
def play_game_inline(filename):
    """Serve an HTML game file inline so it can be played directly in the browser (no download)."""
    safe_name = secure_filename(filename)
    return send_from_directory(GENERATED_FOLDER, safe_name, as_attachment=False)

@app.route('/api/save_response', methods=['POST'])
def save_response_to_file():
    data = request.get_json() or {}
    content = data.get('content', '')
    ext = data.get('extension', 'txt')
    custom_name = data.get('filename')
    
    if custom_name:
        filename = secure_filename(custom_name)
    else:
        filename = f"deepseek_export_{int(time.time())}.{ext}"
        
    filepath = os.path.join(GENERATED_FOLDER, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return jsonify({
        'filename': filename,
        'download_url': f'/download/generated/{filename}',
        'size': len(content.encode('utf-8'))
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    start_time = time.time()
    data = request.get_json() or {}
    user_prompt = data.get('prompt', '').strip()
    history = data.get('history', [])
    deepthink = data.get('deepthink', True)
    web_search = data.get('web_search', False)
    api_key = data.get('api_key', '').strip()
    model_mode = data.get('model_mode', 'free-reasoning')
    attached_files = data.get('attached_files', [])
    
    if not user_prompt and not attached_files:
        return jsonify({'error': 'Empty prompt'}), 400

    # Read attached files
    file_context_parts = []
    for fname in attached_files:
        clean_name = secure_filename(fname)
        fpath = os.path.join(UPLOAD_FOLDER, clean_name)
        if not os.path.exists(fpath):
            fpath = os.path.join(GENERATED_FOLDER, clean_name)
        if os.path.exists(fpath):
            content = extract_file_content(fpath)
            file_context_parts.append(f"=== ATTACHED FILE: {clean_name} ===\n{content}\n=== END OF FILE ===")

    file_context_str = "\n\n".join(file_context_parts)
    
    user_message_content = user_prompt
    if file_context_str:
        user_message_content = f"The user has attached the following file(s) for context:\n\n{file_context_str}\n\nUser request: {user_prompt}"

    # Build specialized Minecraft & Developer System Instruction
    system_instruction = (
        "You are Kaleb AI, an exceptionally capable, intelligent AI assistant and Minecraft Master Creator. "
        "You have deep expertise in Minecraft 1.20 - 1.21+ modding, Data Packs, Resource Packs, and player Skins.\n\n"
        "Guidelines for Minecraft Creations:\n"
        "1. DATA PACKS: When asked for a datapack, provide exact working syntax for `pack.mcmeta` (pack_format 48), "
        "`data/<namespace>/functions/tick.mcfunction`, `load.mcfunction`, and tags `data/minecraft/tags/function/tick.json`. "
        "Include commands using `execute as @a at @s...` or valid selectors.\n"
        "2. RESOURCE PACKS: Provide `pack.mcmeta`, model json, and lang files (`assets/minecraft/...`).\n"
        "3. FABRIC/FORGE MODS: Provide `fabric.mod.json`, `build.gradle`, and clean Java source code with proper imports.\n"
        "4. SKINS: Describe the 64x64 skin texture layout, color palette, and character details.\n"
        "5. ALWAYS explain to the user step-by-step how to install their mod/datapack/skin into their Minecraft game folder!\n"
        "6. GAME CREATION: When asked to create a game (e.g. Space Shooter, Flappy Bird, Snake, Pong, Platformer, Zombie Survival, Racing, RPG, etc.):\n"
        "   - Always write complete, fully functional, 100% bug-free interactive game code in HTML5 Canvas + JavaScript (or Python with Pygame/Tkinter/Turtle if requested).\n"
        "   - Include 60fps game loops, player controls (WASD, Arrow keys, Spacebar, Mouse), collision detection, score display, particle effects, Game Over / Restart screens, and retro sound effects using Web Audio API.\n"
        "   - Put the entire game in a self-contained code block (e.g. ```html index.html ... ```) so Kaleb AI can immediately package it into a standalone game and a Windows .bat launcher for the user to download and play directly on their computer!\n"
        "Always use clean markdown code blocks with the relative filename in the header (e.g. ```json pack.mcmeta or ```mcfunction data/custom/functions/tick.mcfunction)."
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    for h in history[-8:]:
        role = h.get('role', 'user')
        content = h.get('content', '')
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message_content})

    thinking_text = ""
    answer_text = ""
    
    # 1. Groq Cloud
    if model_mode == 'groq' and api_key:
        try:
            reasoning, content = call_groq_api(api_key, messages)
            thinking_text = reasoning
            answer_text = content
        except Exception as e:
            print(f"Groq API error: {e}")
            answer_text = f"Groq API Error: {e}\n\nFalling back to Free High-Tier Reasoning AI..."

    # 2. Official DeepSeek Cloud
    elif model_mode == 'deepseek' and api_key:
        try:
            m = "deepseek-reasoner" if deepthink else "deepseek-chat"
            reasoning, content = call_deepseek_api(api_key, messages, model=m)
            thinking_text = reasoning
            answer_text = content
        except Exception as e:
            print(f"DeepSeek API error: {e}")
            answer_text = f"DeepSeek Cloud API Error: {e}\n\nFalling back to Free High-Tier Reasoning AI..."

    # 3. Default: Free 20B Reasoning AI
    if not answer_text or "Falling back" in answer_text:
        try:
            reasoning, content = call_free_reasoning_ai(messages)
            if deepthink and reasoning:
                thinking_text = reasoning
            elif deepthink and not reasoning:
                thinking_text = f"Analyzed creation request: '{user_prompt[:80]}'. Synthesized logic, gameplay systems, code, and packaged playable files."
            answer_text = content if content else "Processed creation request."
        except Exception as e:
            print(f"Free Reasoning AI error: {e}")
            answer_text = f"I encountered a temporary connection error: {e}. Please try again in a moment."

    # Parse and extract code blocks to save them
    saved_files = extract_code_and_save_files(answer_text)
    
    # MINECRAFT AUTOMATION: Bundle Datapacks, Resource packs, Mods, or generate 64x64 Skins!
    mc_artifacts = handle_minecraft_creation(user_prompt, answer_text, attached_files=attached_files)
    for mc_item in mc_artifacts:
        saved_files.insert(0, mc_item)

    # GAME CREATION & PACKAGING: Standalone playable game + Windows .bat launcher + ZIP!
    game_artifacts = handle_game_creation(user_prompt, answer_text)
    for g_item in game_artifacts:
        saved_files.insert(0, g_item)
    
    # Save answer as text file
    answer_filename = f"kaleb_ai_response_{int(time.time())}.txt"
    with open(os.path.join(GENERATED_FOLDER, answer_filename), 'w', encoding='utf-8') as f:
        f.write(answer_text)
        
    saved_files.insert(0, {
        'filename': answer_filename,
        'path': f'/download/generated/{answer_filename}',
        'size': len(answer_text.encode('utf-8')),
        'language': 'txt',
        'is_full_answer': True
    })

    elapsed = round(time.time() - start_time, 2)
    return jsonify({
        'answer': answer_text,
        'thinking': thinking_text,
        'thinking_time': elapsed,
        'generated_files': saved_files
    })

@app.route('/api/minecraft/merge', methods=['POST'])
def api_merge_mods():
    """Dedicated API endpoint to merge multiple uploaded Minecraft mod ZIPs or JARs."""
    data = request.get_json() or {}
    filenames = data.get('files', [])
    if len(filenames) < 2:
        return jsonify({'error': 'Please select at least 2 mod files (.zip or .jar) to merge'}), 400
        
    paths = []
    for fname in filenames:
        clean = secure_filename(fname)
        p = os.path.join(UPLOAD_FOLDER, clean)
        if not os.path.exists(p):
            p = os.path.join(GENERATED_FOLDER, clean)
        if os.path.exists(p) and (p.lower().endswith('.zip') or p.lower().endswith('.jar')):
            paths.append(p)
            
    if len(paths) < 2:
        return jsonify({'error': 'Could not locate at least 2 valid .zip or .jar files to merge'}), 400
        
    ts = int(time.time())
    merged_filename = f"Merged_Minecraft_Mod_{ts}.zip"
    out_path = os.path.join(GENERATED_FOLDER, merged_filename)
    
    try:
        res = minecraft_creator.merge_minecraft_archives(paths, out_path, merged_name="Merged_Mod")
        return jsonify({
            'success': True,
            'filename': merged_filename,
            'download_url': f'/download/generated/{merged_filename}',
            'files_count': res['files_count'],
            'report': res['report']
        })
    except Exception as e:
        return jsonify({'error': f'Failed to merge mods: {str(e)}'}), 500

if __name__ == '__main__':
    import os as _os
    port = int(_os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
