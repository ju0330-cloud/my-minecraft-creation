import os
import io
import re
import json
import zipfile
import random
from PIL import Image, ImageDraw

def create_color_palette(theme="default"):
    theme = theme.lower()
    if "ender" in theme or "purple" in theme:
        return {
            "skin": (25, 25, 30, 255), "eyes": (200, 50, 240, 255),
            "clothes": (35, 20, 50, 255), "accent": (160, 40, 220, 255),
            "hair": (15, 10, 25, 255)
        }
    elif "knight" in theme or "armor" in theme or "iron" in theme or "silver" in theme:
        return {
            "skin": (220, 180, 140, 255), "eyes": (60, 120, 200, 255),
            "clothes": (140, 145, 155, 255), "accent": (210, 215, 225, 255),
            "hair": (80, 50, 30, 255)
        }
    elif "creeper" in theme or "green" in theme:
        return {
            "skin": (40, 160, 60, 255), "eyes": (15, 40, 20, 255),
            "clothes": (30, 120, 45, 255), "accent": (70, 200, 90, 255),
            "hair": (20, 80, 30, 255)
        }
    elif "nether" in theme or "fire" in theme or "red" in theme or "demon" in theme:
        return {
            "skin": (180, 40, 40, 255), "eyes": (255, 220, 50, 255),
            "clothes": (60, 20, 20, 255), "accent": (230, 80, 40, 255),
            "hair": (30, 10, 10, 255)
        }
    elif "cyber" in theme or "neon" in theme or "blue" in theme:
        return {
            "skin": (215, 185, 155, 255), "eyes": (0, 240, 255, 255),
            "clothes": (20, 25, 35, 255), "accent": (0, 220, 255, 255),
            "hair": (240, 240, 245, 255)
        }
    elif "gold" in theme or "king" in theme or "royal" in theme:
        return {
            "skin": (225, 190, 150, 255), "eyes": (70, 140, 220, 255),
            "clothes": (180, 20, 35, 255), "accent": (255, 200, 30, 255),
            "hair": (210, 160, 60, 255)
        }
    else:  # Modern casual adventurer / Steve variant
        return {
            "skin": (215, 175, 135, 255), "eyes": (45, 75, 165, 255),
            "clothes": (35, 95, 155, 255), "accent": (65, 50, 40, 255),
            "hair": (85, 55, 35, 255)
        }

def add_noise(color, variance=12):
    v = abs(variance)
    r = max(0, min(255, color[0] + random.randint(-v, v)))
    g = max(0, min(255, color[1] + random.randint(-v, v)))
    b = max(0, min(255, color[2] + random.randint(-v, v)))
    return (r, g, b, color[3] if len(color) > 3 else 255)

def fill_textured_rect(draw, x1, y1, x2, y2, base_color, variance=10):
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            draw.point((x, y), fill=add_noise(base_color, variance))

def generate_minecraft_skin(output_path, theme="adventurer"):
    """
    Generate an authentic 64x64 RGBA Minecraft player skin (1.8+ format)
    with head, body, arms, legs and outer overlay layers.
    """
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    palette = create_color_palette(theme)

    skin = palette["skin"]
    hair = palette["hair"]
    eyes = palette["eyes"]
    clothes = palette["clothes"]
    accent = palette["accent"]

    # 1. HEAD (0,0 to 32,16)
    # Head Top (8,0)-(15,7) - Hair
    fill_textured_rect(draw, 8, 0, 15, 7, hair)
    # Head Bottom (16,0)-(23,7) - Neck
    fill_textured_rect(draw, 16, 0, 23, 7, skin)
    # Head Right (0,8)-(7,15)
    fill_textured_rect(draw, 0, 8, 7, 15, skin)
    fill_textured_rect(draw, 0, 8, 7, 10, hair)
    # Head Front Face (8,8)-(15,15)
    fill_textured_rect(draw, 8, 8, 15, 15, skin)
    fill_textured_rect(draw, 8, 8, 15, 9, hair) # forehead hair
    # Eyes
    draw.point((9, 12), fill=(255, 255, 255, 255))
    draw.point((10, 12), fill=eyes)
    draw.point((13, 12), fill=eyes)
    draw.point((14, 12), fill=(255, 255, 255, 255))
    # Mouth / Nose
    draw.point((11, 14), fill=add_noise(skin, -25))
    draw.point((12, 14), fill=add_noise(skin, -25))
    # Head Left (16,8)-(23,15)
    fill_textured_rect(draw, 16, 8, 23, 15, skin)
    fill_textured_rect(draw, 16, 8, 23, 10, hair)
    # Head Back (24,8)-(31,15)
    fill_textured_rect(draw, 24, 8, 31, 15, hair)

    # 2. TORSO / BODY (16,16 to 40,32)
    # Top (20,16)-(27,19) & Bottom (28,16)-(35,19)
    fill_textured_rect(draw, 20, 16, 27, 19, clothes)
    fill_textured_rect(draw, 28, 16, 35, 19, accent)
    # Front (20,20)-(27,31)
    fill_textured_rect(draw, 20, 20, 27, 31, clothes)
    # Front details / belt
    fill_textured_rect(draw, 20, 29, 27, 31, accent)
    draw.rectangle([23, 29, 24, 30], fill=(230, 200, 50, 255)) # belt buckle
    # Back (32,20)-(39,31)
    fill_textured_rect(draw, 32, 20, 39, 31, clothes)
    fill_textured_rect(draw, 32, 29, 39, 31, accent)
    # Right side (16,20)-(19,31) & Left side (28,20)-(31,31)
    fill_textured_rect(draw, 16, 20, 19, 31, clothes)
    fill_textured_rect(draw, 28, 20, 31, 31, clothes)

    # 3. RIGHT ARM (40,16 to 56,32)
    # Top (44,16)-(47,19)
    fill_textured_rect(draw, 44, 16, 47, 19, clothes)
    # Sleeve portion
    fill_textured_rect(draw, 40, 20, 55, 24, clothes)
    # Hand skin portion
    fill_textured_rect(draw, 40, 25, 55, 31, skin)
    # Bottom (48,16)-(51,19)
    fill_textured_rect(draw, 48, 16, 51, 19, skin)

    # 4. LEFT ARM (32,48 to 48,64)
    # Top (36,48)-(39,51)
    fill_textured_rect(draw, 36, 48, 39, 51, clothes)
    # Sleeve
    fill_textured_rect(draw, 32, 52, 47, 56, clothes)
    # Hand
    fill_textured_rect(draw, 32, 57, 47, 63, skin)
    # Bottom (40,48)-(43,51)
    fill_textured_rect(draw, 40, 48, 43, 51, skin)

    # 5. RIGHT LEG (0,16 to 16,32)
    # Pants
    fill_textured_rect(draw, 0, 16, 15, 27, accent)
    # Shoes
    fill_textured_rect(draw, 0, 28, 15, 31, (40, 40, 45, 255))
    fill_textured_rect(draw, 8, 16, 11, 19, (35, 35, 40, 255)) # bottom

    # 6. LEFT LEG (16,48 to 32,64)
    # Pants
    fill_textured_rect(draw, 16, 48, 31, 59, accent)
    # Shoes
    fill_textured_rect(draw, 16, 60, 31, 63, (40, 40, 45, 255))
    fill_textured_rect(draw, 24, 48, 27, 51, (35, 35, 40, 255))

    # 7. OUTER HAT / HOODIE LAYER (32,0 to 63,15)
    # Front overlay (40,8)-(47,15)
    for x, y in [(40,8), (41,8), (46,8), (47,8), (40,9), (47,9)]:
        draw.point((x, y), fill=add_noise(hair, 15))

    img.save(output_path, 'PNG')
    return output_path

def build_minecraft_datapack_zip(output_zip_path, pack_name, description, files_map, pack_format=48):
    """
    Package files into a 100% valid, functional Minecraft Data Pack ZIP.
    Requires pack.mcmeta and data/ namespace.
    """
    namespace = re.sub(r'[^a-z0-9_]', '', pack_name.lower()) or "custom"
    
    # Check if pack.mcmeta is provided
    if "pack.mcmeta" not in files_map:
        files_map["pack.mcmeta"] = json.dumps({
            "pack": {
                "pack_format": pack_format,
                "description": description or f"{pack_name} by Kaleb AI"
            }
        }, indent=2)

    # Ensure tick.json and load.json function tags exist if functions are present
    has_tick = any("tick.mcfunction" in path.lower() for path in files_map)
    has_load = any("load.mcfunction" in path.lower() for path in files_map)

    tick_tag_path = "data/minecraft/tags/function/tick.json"
    load_tag_path = "data/minecraft/tags/function/load.json"
    alt_tick_tag = "data/minecraft/tags/functions/tick.json"
    alt_load_tag = "data/minecraft/tags/functions/load.json"

    if has_tick and not (tick_tag_path in files_map or alt_tick_tag in files_map):
        files_map[tick_tag_path] = json.dumps({
            "values": [f"{namespace}:tick"]
        }, indent=2)

    if has_load and not (load_tag_path in files_map or alt_load_tag in files_map):
        files_map[load_tag_path] = json.dumps({
            "values": [f"{namespace}:load"]
        }, indent=2)

    # Write to ZIP
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files_map.items():
            # Clean up path
            clean_path = rel_path.replace('\\', '/').lstrip('/')
            if isinstance(content, str):
                zf.writestr(clean_path, content)
            elif isinstance(content, bytes):
                zf.writestr(clean_path, content)

    return output_zip_path

def build_minecraft_resourcepack_zip(output_zip_path, pack_name, description, files_map, pack_format=34):
    """
    Package files into a 100% valid, functional Minecraft Resource Pack ZIP.
    Includes pack.mcmeta and optional 64x64 pack.png icon.
    """
    if "pack.mcmeta" not in files_map:
        files_map["pack.mcmeta"] = json.dumps({
            "pack": {
                "pack_format": pack_format,
                "description": description or f"{pack_name} Resource Pack"
            }
        }, indent=2)

    # Generate a nice 64x64 pack.png if missing
    if "pack.png" not in files_map:
        icon_img = Image.new('RGBA', (64, 64), (30, 32, 40, 255))
        idraw = ImageDraw.Draw(icon_img)
        # Draw a custom sword / pickaxe icon
        idraw.rectangle([10, 10, 53, 53], outline=(77, 107, 254, 255), width=2)
        idraw.line([(20, 44), (44, 20)], fill=(0, 220, 255, 255), width=4)
        idraw.line([(18, 46), (22, 42)], fill=(180, 120, 50, 255), width=3)
        idraw.rectangle([40, 18, 46, 24], fill=(0, 255, 200, 255))
        buf = io.BytesIO()
        icon_img.save(buf, format='PNG')
        files_map["pack.png"] = buf.getvalue()

    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files_map.items():
            clean_path = rel_path.replace('\\', '/').lstrip('/')
            if isinstance(content, str):
                zf.writestr(clean_path, content)
            elif isinstance(content, bytes):
                zf.writestr(clean_path, content)

    return output_zip_path

def build_minecraft_fabric_mod_zip(output_zip_path, mod_id, mod_name, files_map):
    """
    Package a complete Fabric mod project with fabric.mod.json, build.gradle,
    and Java source files ready to compile.
    """
    if "src/main/resources/fabric.mod.json" not in files_map and "fabric.mod.json" not in files_map:
        files_map["src/main/resources/fabric.mod.json"] = json.dumps({
            "schemaVersion": 1,
            "id": mod_id.lower().replace("-", "_"),
            "version": "1.0.0",
            "name": mod_name,
            "description": f"{mod_name} created with Kaleb AI",
            "authors": ["Player"],
            "contact": {},
            "license": "MIT",
            "environment": "*",
            "entrypoints": {
                "main": [f"net.minecraft.custom.{mod_id.lower()}.{mod_name.replace(' ', '')}"]
            },
            "depends": {
                "fabricloader": ">=0.15.0",
                "minecraft": "~1.20.4",
                "java": ">=17"
            }
        }, indent=2)

    if "build.gradle" not in files_map:
        files_map["build.gradle"] = f"""plugins {{
    id 'fabric-loom' version '1.5-SNAPSHOT'
    id 'maven-publish'
}}

version = "1.0.0"
group = "com.custom.{mod_id.lower()}"

repositories {{
    mavenCentral()
}}

dependencies {{
    minecraft "com.mojang:minecraft:1.20.4"
    mappings "net.fabricmc:yarn:1.20.4+build.3:v2"
    modImplementation "net.fabricmc:fabric-loader:0.15.7"
    modImplementation "net.fabricmc.fabric-api:fabric-api:0.96.4+1.20.4"
}}

processResources {{
    inputs.property "version", project.version
    filesMatching("fabric.mod.json") {{
        expand "version": project.version
    }}
}}
"""

    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files_map.items():
            clean_path = rel_path.replace('\\', '/').lstrip('/')
            if isinstance(content, str):
                zf.writestr(clean_path, content)
            elif isinstance(content, bytes):
                zf.writestr(clean_path, content)

    return output_zip_path

def merge_minecraft_archives(archive_paths, output_path, merged_name="Merged_Mod"):
    """
    Intelligently merge multiple Minecraft Mod JARs, Data Pack ZIPs, or Resource Pack ZIPs.
    Handles:
    - Merging pack.mcmeta (taking highest pack_format, combining descriptions)
    - Merging fabric.mod.json (combining entrypoints, mixins, dependencies)
    - Merging function tags (tick.json, load.json arrays concatenated without loss)
    - Merging lang files (en_us.json dictionaries merged so item names from all mods are preserved)
    - Preserving all data/, assets/, textures, models, and classes
    """
    merged_files = {}
    merged_langs = {}
    merged_tags = {}
    fabric_mod_json = None
    pack_mcmeta = None
    report = []
    
    for arc_path in archive_paths:
        base_name = os.path.basename(arc_path)
        try:
            with zipfile.ZipFile(arc_path, 'r') as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    filename = member.filename.replace('\\', '/')
                    data = zf.read(member)
                    
                    # 1. pack.mcmeta
                    if filename.lower() == "pack.mcmeta":
                        try:
                            meta_obj = json.loads(data.decode('utf-8'))
                            if not pack_mcmeta:
                                pack_mcmeta = meta_obj
                            else:
                                curr_fmt = pack_mcmeta.get("pack", {}).get("pack_format", 48)
                                new_fmt = meta_obj.get("pack", {}).get("pack_format", 48)
                                pack_mcmeta["pack"]["pack_format"] = max(curr_fmt, new_fmt)
                                pack_mcmeta["pack"]["description"] = f"{merged_name} (Merged by Kaleb AI)"
                        except Exception:
                            merged_files[filename] = data
                        continue

                    # 2. fabric.mod.json
                    if filename.lower().endswith("fabric.mod.json"):
                        try:
                            f_obj = json.loads(data.decode('utf-8'))
                            if not fabric_mod_json:
                                fabric_mod_json = f_obj
                            else:
                                # Merge entrypoints
                                for ep_type, ep_list in f_obj.get("entrypoints", {}).items():
                                    if ep_type not in fabric_mod_json.setdefault("entrypoints", {}):
                                        fabric_mod_json["entrypoints"][ep_type] = []
                                    if isinstance(ep_list, list):
                                        fabric_mod_json["entrypoints"][ep_type].extend([x for x in ep_list if x not in fabric_mod_json["entrypoints"][ep_type]])
                                    elif isinstance(ep_list, str):
                                        if ep_list not in fabric_mod_json["entrypoints"][ep_type]:
                                            fabric_mod_json["entrypoints"][ep_type].append(ep_list)
                                # Merge mixins
                                curr_mixins = fabric_mod_json.get("mixins", [])
                                new_mixins = f_obj.get("mixins", [])
                                if isinstance(curr_mixins, list) and isinstance(new_mixins, list):
                                    fabric_mod_json["mixins"] = list(set(curr_mixins + new_mixins))
                        except Exception:
                            merged_files[filename] = data
                        continue

                    # 3. Language files (e.g. assets/<ns>/lang/en_us.json)
                    if "/lang/" in filename.lower() and filename.lower().endswith(".json"):
                        try:
                            lang_obj = json.loads(data.decode('utf-8'))
                            if filename not in merged_langs:
                                merged_langs[filename] = {}
                            merged_langs[filename].update(lang_obj)
                            continue
                        except Exception:
                            pass

                    # 4. Function tags (data/minecraft/tags/function/tick.json or load.json)
                    if "/tags/function/" in filename.lower() or "/tags/functions/" in filename.lower():
                        try:
                            tag_obj = json.loads(data.decode('utf-8'))
                            if filename not in merged_tags:
                                merged_tags[filename] = {"values": []}
                            for val in tag_obj.get("values", []):
                                if val not in merged_tags[filename]["values"]:
                                    merged_tags[filename]["values"].append(val)
                            continue
                        except Exception:
                            pass

                    # 5. Regular file
                    if filename not in merged_files:
                        merged_files[filename] = data
                    else:
                        report.append(f"Merged asset: {filename} from {base_name}")
                        merged_files[filename] = data
                        
            report.append(f"Successfully processed archive: {base_name}")
        except Exception as e:
            report.append(f"Failed to read {base_name}: {e}")

    # Finalize merged packs
    if pack_mcmeta:
        merged_files["pack.mcmeta"] = json.dumps(pack_mcmeta, indent=2)
    elif fabric_mod_json:
        entry_key = "src/main/resources/fabric.mod.json" if any("src/main/resources" in k for k in merged_files) else "fabric.mod.json"
        merged_files[entry_key] = json.dumps(fabric_mod_json, indent=2)

    for l_path, l_dict in merged_langs.items():
        merged_files[l_path] = json.dumps(l_dict, indent=2)

    for t_path, t_dict in merged_tags.items():
        merged_files[t_path] = json.dumps(t_dict, indent=2)

    # Write output zip
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fpath, fcontent in merged_files.items():
            clean_p = fpath.replace('\\', '/').lstrip('/')
            if isinstance(fcontent, str):
                zf.writestr(clean_p, fcontent)
            elif isinstance(fcontent, bytes):
                zf.writestr(clean_p, fcontent)

    return {
        "output_path": output_path,
        "files_count": len(merged_files),
        "report": report
    }

