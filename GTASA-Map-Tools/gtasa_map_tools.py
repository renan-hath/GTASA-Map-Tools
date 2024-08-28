import argparse
import glob
import os
import random
import re
import shutil
import stat
import string
from itertools import chain
from pathlib import Path

import chardet
import tkinter as tk
import unidecode

from application.data_entry_types.str.ide.anim import Anim
from application.data_entry_types.str.ide.cars_ide import CarsIde
from application.data_entry_types.str.ide.hier import Hier
from application.data_entry_types.str.ide.objs import Objs
from application.data_entry_types.str.ide.peds import Peds
from application.data_entry_types.str.ide.tobj import Tobj
from application.data_entry_types.str.ide.txdp import Txdp
from application.data_entry_types.str.ide.weap import Weap
from application.data_entry_types.str.ipl.auzo import Auzo
from application.data_entry_types.str.ipl.cars_ipl import CarsIpl
from application.data_entry_types.str.ipl.cull import Cull
from application.data_entry_types.str.ipl.enex import Enex
from application.data_entry_types.str.ipl.grge import Grge
from application.data_entry_types.str.ipl.inst import Inst
from application.data_entry_types.str.ipl.jump import Jump
from application.data_entry_types.str.ipl.occl import Occl
from application.data_entry_types.str.ipl.pick import Pick
from application.data_entry_types.str.ipl.tcyc import Tcyc
from application.file_types.binary.col import Col
from application.file_types.binary.ipl_binary import IplBinary
from application.file_types.str.dat import Dat
from application.file_types.str.ide import Ide
from application.file_types.str.ipl import Ipl
from application.data_entry_types.binary.ipl.inst_binary import InstBinary
from application.gui.map_gui import MapGui
from application.tools.img_console import IMGConsole
from application.tools.sa_paths_data_extender import SAPathsDataExtender
from application.data_entry_types.str.dat.dat_object import DatObject

#region Constants
SA_DATA_DIR = "C:\\Games\\GTA San Andreas\\data"
SA_MODLOADER_DIR = "C:\\Games\\GTA San Andreas\\modloader"
INPUT_DIR = "files"
OUTPUT_DIR = "modified_files"
OUTPUT_IMG_DIR = os.path.join(OUTPUT_DIR, "img")
OUTPUT_ASSETS_DIR = os.path.join(OUTPUT_DIR, "assets")
OUTPUT_MAP_DIR = os.path.join(OUTPUT_DIR, "map")
OUTPUT_PATHS_DIR = os.path.join(OUTPUT_DIR, "gta3.img")
RESOURCES_DIR = "resources"
IMG_CONSOLE_DIR = os.path.join(RESOURCES_DIR, "IMGconsole_32-bit")
IMG_CONSOLE_TEMP_DIR = os.path.join(IMG_CONSOLE_DIR, "Temp")
IMG_CONSOLE_NAME = "fastman92ImgConsole32.exe"
IMG_CONSOLE_PATH = os.path.join(IMG_CONSOLE_DIR, IMG_CONSOLE_NAME)
VANILLA_IMG_FILE_NAMES = ['gta3.img', 'gta_int.img', 'player.img', 'cutscene.img']
SA_PATHS_DATA_EXTENDER_DIR = os.path.join(RESOURCES_DIR, "SAPathsDataExtender")
SA_PATHS_DATA_EXTENDER_INPUT_DIR = os.path.join(SA_PATHS_DATA_EXTENDER_DIR, "Input")
SA_PATHS_DATA_EXTENDER_OUTPUT_DIR = os.path.join(SA_PATHS_DATA_EXTENDER_DIR, "Output")
SA_PATHS_DATA_EXTENDER_NAME = "sa-pathsdata-extender.exe"
SA_PATHS_DATA_EXTENDER_PATH = os.path.join(SA_PATHS_DATA_EXTENDER_DIR, SA_PATHS_DATA_EXTENDER_NAME)
INVALID_IDS_FILE_NAME = 'invalid_ids.txt'
INVALID_IDS_PATH = os.path.join(RESOURCES_DIR, INVALID_IDS_FILE_NAME)
VANILLA_FILES_FILE_NAME = "vanilla_files.txt"
VANILLA_FILES_PATH = os.path.join(RESOURCES_DIR, VANILLA_FILES_FILE_NAME)
VANILLA_OBJECTS_FILE_NAME = "vanilla_objects.txt"
VANILLA_OBJECTS_FILE_PATH = os.path.join(RESOURCES_DIR, VANILLA_OBJECTS_FILE_NAME)
VANILLA_DAT_OBJECTS_FILE_NAME = "vanilla_dat_objects.txt"
VANILLA_DAT_OBJECTS_FILE_PATH = os.path.join(RESOURCES_DIR, VANILLA_DAT_OBJECTS_FILE_NAME)
VANILLA_PLACEMENTS_FILE_NAME = "vanilla_placements.txt"
VANILLA_PLACEMENTS_PATH =  os.path.join(RESOURCES_DIR, VANILLA_PLACEMENTS_FILE_NAME)
#endregion

#region Global variables
fix_command = False
id_command = False
path_command = False
map_command = False
map_command_x = 0
map_command_y = 0
map_command_z = 0

mod_map_files = []
vanilla_objects = {}
vanilla_dat_objects = set()
vanilla_ids = set()
vanilla_models = set()

ids_in_use = []
replaced_ids = {}

ide_objects = []
inst_objects = []
inst_binary_objects = []
ipl_objects = []
inst_total_objects = []
coordinate_objects = []
vanilla_files = {}
object_resources_renames = {}
col_models_renames = {}
dff_renames = {}
txd_renames = {}
new_col_files = []
free_ids = []
vanilla_placements = []
inst_binary_files = {}
existent_binary_ipl_files = False
dff_models = []
col_models = []
vanilla_files_basenames = set()
dff_new_basenames = set()
col_models_new_basenames = set()
txd_new_basenames = set()

img_console = IMGConsole()

def get_vanilla_objects():
    global vanilla_objects
    global vanilla_ids
    global vanilla_models
    
    file_encoding = detect_file_encoding(VANILLA_OBJECTS_FILE_PATH)
    file_content = read_file(VANILLA_OBJECTS_FILE_PATH, file_encoding)
    
    for line in file_content:
        elements = [element.strip().lower() for element in line.split(',')]
        vanilla_object_id = int(elements[0])
        vanilla_object_model = elements[1]

        vanilla_objects[vanilla_object_id] = vanilla_object_model
        
    vanilla_ids = set(vanilla_objects.keys())
    vanilla_models = set(vanilla_objects.values())
    
def get_vanilla_dat_objects():
    global vanilla_dat_objects
    
    file_encoding = detect_file_encoding(VANILLA_DAT_OBJECTS_FILE_PATH)
    file_content = read_file(VANILLA_DAT_OBJECTS_FILE_PATH, file_encoding)
    
    vanilla_dat_objects = {line.strip() for line in file_content}

def get_free_ids():
    global free_ids
    
    usable_ids = list(range(1, 65531))
    ids_in_use = get_ids_in_use()
    free_ids = [object_id for object_id in usable_ids if object_id not in ids_in_use]
    free_ids.sort()

def get_ids_in_use():
    for directory in [SA_DATA_DIR, SA_MODLOADER_DIR]:
        for root, dirs, files in os.walk(directory):
            for mod_file in files:
                file_extension = os.path.splitext(mod_file)[1][1:].lower()
                
                if file_extension == 'ide':
                    file_path = os.path.join(root, mod_file)
                    file_encoding = detect_file_encoding(file_path)
                    file_content = read_file(file_path, file_encoding)
                    
                    file = Ide(mod_file, file_content)
                    
                    if file.section_objs:
                        for obj in file.section_objs:
                            ids_in_use.append(obj.obj_id)
                    if file.section_tobj:
                        for obj in file.section_tobj:
                            ids_in_use.append(obj.obj_id)
                    if file.section_anim:
                        for obj in file.section_anim:
                            ids_in_use.append(obj.obj_id)
                    if file.section_cars:
                        for obj in file.section_cars:
                            ids_in_use.append(obj.obj_id)
                    if file.section_hier:
                        for obj in file.section_hier:
                            ids_in_use.append(obj.obj_id)
                    if file.section_peds:
                        for obj in file.section_peds:
                            ids_in_use.append(obj.obj_id)
                    if file.section_weap:
                        for obj in file.section_weap:
                            ids_in_use.append(obj.obj_id)
                            
    if os.path.exists(INVALID_IDS_PATH) and os.path.getsize(INVALID_IDS_PATH) > 0:
        file_encoding = detect_file_encoding(INVALID_IDS_PATH)
        file_content = read_file(INVALID_IDS_PATH, file_encoding)
        
        for line in file_content:
            line = int(line.strip())
            if line not in ids_in_use:
                ids_in_use.append(line)
                
    ids_in_use.sort()
                            
    return ids_in_use

def process_files():
    global fix_command, id_command, path_command
    global map_command, map_command_x, map_command_y, map_command_z
    global rot_command,rot_command_x, rot_command_y, rot_command_z, rot_command_w
    
    copy_files_to_output()
    root = tk.Tk()
    root.title("GTA Map Renderer")
    mod_coordinates = get_mod_coordinates(read_mod_placement_files())
    installed_mods_coordinates = get_installed_mods_coordinates(read_installed_placement_files())
    app = MapGui(root, mod_coordinates, installed_mods_coordinates)
    root.mainloop()
    
    if app.map_coordinates and app.map_coordinates != (0.0, 0.0, 0.0):
        map_command = True
        map_command_x, map_command_y, map_command_z = app.map_coordinates
    else:
        map_command = False
    
    if app.rotation_values and app.rotation_values != (0.0, 0.0, 0.0, 0.0):
        rot_command = True
        rot_command_x, rot_command_y, rot_command_z, rot_command_w = app.rotation_values
    else:
        rot_command = False
        
    if app.fix_command:
        fix_command = True
    else:
        fix_command = False
        
    if app.id_command:
        id_command = True
    else:
        id_command = False
        
    if app.path_command:
        path_command = True
    else:
        path_command = False
        
    uniquify_mod_files()
    read_map_files()
    uniquify_map_objects()
    list_objects_to_modify()
    modify_map_files()
    write_map_files()
    repack_inst_binary_files()

def read_map_files():
    global mod_map_files
    
    if os.path.exists(OUTPUT_MAP_DIR):
        for file_name in os.listdir(OUTPUT_MAP_DIR):
            file_extension = os.path.splitext(file_name)[1][1:].lower()
            file_path = os.path.join(OUTPUT_MAP_DIR, file_name)
            file_encoding = detect_file_encoding(file_path)
            file_content = read_file(file_path, file_encoding)
            
            if file_encoding == 'binary':
                if file_extension == 'ipl':
                    file = IplBinary(file_name, file_content)
            else:
                if file_extension == 'ide':
                    file = Ide(file_name, file_content)
                elif file_extension == 'ipl':
                    file = Ipl(file_name, file_content)
                elif (file_name.lower() == 'water.dat' or
                      file_name.lower() == 'object.dat'):
                    file = Dat(file_name, file_content)
                    
            mod_map_files.append(file)

def detect_file_encoding(file_path):
    with open(file_path, 'rb') as f:
        if f.read(4) == b"bnry":
            return 'binary'
        else:
            f.seek(0)
            result = chardet.detect(f.read())
            return result['encoding']
        
def is_fastman_node_format(file_path):
    with open(file_path, 'rb') as f:
        bytes_data = f.read(8)

        if len(bytes_data) >= 8 and bytes_data[4:8] == b"FM92":
            return True
        else:
            return False

def read_file(file_path, encoding):
    
    if encoding == 'binary':
        with open(file_path, 'rb') as f:
            return bytearray(f.read())
    else:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            return f.readlines()

def list_objects_to_modify():
    global ide_objects
    global inst_objects
    global inst_binary_objects
    global inst_total_objects
    global ipl_objects
    global coordinate_objects
    
    ide_objects = []
    inst_objects = []
    inst_binary_objects = []
    inst_total_objects = []
    ipl_objects = []
    coordinate_objects = []
    
    for file in mod_map_files:
        if isinstance(file, Ide):
            if file.section_objs:
                ide_objects.extend(file.section_objs)
            if file.section_tobj:
                ide_objects.extend(file.section_tobj)
            if file.section_anim:
                ide_objects.extend(file.section_anim)
            if file.section_cars:
                ide_objects.extend(file.section_cars)
            if file.section_hier:
                ide_objects.extend(file.section_hier)
            if file.section_peds:
                ide_objects.extend(file.section_peds)
            if file.section_weap:
                ide_objects.extend(file.section_weap)
        elif isinstance(file, Ipl):
            if file.section_inst:
                inst_objects.extend(file.section_inst)
                ipl_objects.extend(file.section_inst)
                coordinate_objects.extend(file.section_inst)
            if file.section_auzo:
                ipl_objects.extend(file.section_auzo)
                coordinate_objects.extend(file.section_auzo)
            if file.section_cars:
                ipl_objects.extend(file.section_cars)
                coordinate_objects.extend(file.section_cars)
            if file.section_cull:
                ipl_objects.extend(file.section_cull)
                coordinate_objects.extend(file.section_cull)
            if file.section_enex:
                ipl_objects.extend(file.section_enex)
                coordinate_objects.extend(file.section_enex)
            if file.section_grge:
                ipl_objects.extend(file.section_grge)
                coordinate_objects.extend(file.section_grge)
            if file.section_jump:
                ipl_objects.extend(file.section_jump)
                coordinate_objects.extend(file.section_jump)
            if file.section_occl:
                ipl_objects.extend(file.section_occl)
                coordinate_objects.extend(file.section_occl)
            if file.section_pick:
                ipl_objects.extend(file.section_pick)
                coordinate_objects.extend(file.section_pick)
            if file.section_tcyc:
                ipl_objects.extend(file.section_tcyc)
                coordinate_objects.extend(file.section_tcyc)
        elif isinstance(file, IplBinary):
            if file.section_inst:
                inst_binary_objects.extend(file.section_inst)
                ipl_objects.extend(file.section_inst)
                coordinate_objects.extend(file.section_inst)
            if file.section_cars:
                ipl_objects.extend(file.section_cars)
                coordinate_objects.extend(file.section_cars)
        elif isinstance(file, Dat):
            coordinate_objects.extend(file.section_water)
                
    inst_total_objects = inst_objects + inst_binary_objects

def modify_map_files():
    global fix_command
    global id_command
    global map_command
    
    if fix_command:
        remove_unreferenced_objects()
    if id_command:
        update_ids()
    if map_command:
        modify_coordinates()
        move_paths()
    if rot_command:
        rotate_coordinates()

    return

def remove_unreferenced_objects():
    global vanilla_ids
    global mod_map_files
    global ide_objects
    global inst_objects
    global inst_binary_objects
    global ipl_objects
    global dff_models
    global col_models

    # Identify IDE objects without assets
    list_objects_to_modify()
    update_current_assets_names()
    
    ide_objects_without_assets = [gta_object for gta_object in ide_objects if not object_has_assets(gta_object)]
    ide_objects_without_assets = list(set(ide_objects_without_assets))
    
    if ide_objects_without_assets:
        for invalid_ide_object in ide_objects_without_assets:
            file = invalid_ide_object.file
            if isinstance(invalid_ide_object, Objs):
                file.section_objs.remove(invalid_ide_object)
            elif isinstance(invalid_ide_object, Tobj):
                file.section_tobj.remove(invalid_ide_object)
            elif isinstance(invalid_ide_object, Anim):
                file.section_anim.remove(invalid_ide_object)
                
    # Identify duplicated IDE objects
    list_objects_to_modify()
    
    unique_ide_ids = set()
    unique_ide_models = set()
    duplicated_ide_objects = []

    for gta_object in ide_objects:
        if gta_object.obj_id in unique_ide_ids or gta_object.model in unique_ide_models:
            duplicated_ide_objects.append(gta_object)
        else:
            unique_ide_ids.add(gta_object.obj_id)
            unique_ide_models.add(gta_object.model)
            
    if duplicated_ide_objects:
        for duplicated_ide_object in duplicated_ide_objects:
            file = duplicated_ide_object.file
            if isinstance(duplicated_ide_object, Objs):
                file.section_objs.remove(duplicated_ide_object)
            elif isinstance(duplicated_ide_object, Tobj):
                file.section_tobj.remove(duplicated_ide_object)
            elif isinstance(duplicated_ide_object, Anim):
                file.section_anim.remove(duplicated_ide_object)
    
    # Identify IPL objects that already exist in the vanilla game
    list_objects_to_modify()
    correct_dummy_models()
    duplicated_vanilla_ipl_objects = []
    
    if ipl_objects:
        duplicated_vanilla_ipl_objects = [
            gta_object for gta_object in ipl_objects
            if (not isinstance(gta_object.file, IplBinary) and
                get_placement(gta_object.get_content_elements()) in vanilla_placements)
        ]
        
    duplicated_vanilla_ipl_objects = list(set(duplicated_vanilla_ipl_objects))
    
    if duplicated_vanilla_ipl_objects:
        for duplicated_vanilla_ipl_object in duplicated_vanilla_ipl_objects:
            file = duplicated_vanilla_ipl_object.file
            
            if isinstance(duplicated_vanilla_ipl_object, Inst):
                if isinstance(file, Ipl) and duplicated_vanilla_ipl_object in file.section_inst:
                    file.remove_from_section_inst(duplicated_vanilla_ipl_object)
                elif isinstance(file, IplBinary) and duplicated_vanilla_ipl_object in file.section_inst:
                    file.section_inst.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, Auzo) and duplicated_vanilla_ipl_object in file.section_auzo:
                file.section_auzo.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, CarsIpl) and duplicated_vanilla_ipl_object in file.section_cars:
                file.section_cars.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, Cull) and duplicated_vanilla_ipl_object in file.section_cull:
                file.section_cull.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, Enex) and duplicated_vanilla_ipl_object in file.section_enex:
                file.section_enex.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, Grge) and duplicated_vanilla_ipl_object in file.section_grge:
                file.section_grge.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, Jump) and duplicated_vanilla_ipl_object in file.section_jump:
                file.section_jump.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, Occl) and duplicated_vanilla_ipl_object in file.section_occl:
                file.section_occl.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, Pick) and duplicated_vanilla_ipl_object in file.section_pick:
                file.section_pick.remove(duplicated_vanilla_ipl_object)
            elif isinstance(duplicated_vanilla_ipl_object, Tcyc) and duplicated_vanilla_ipl_object in file.section_tcyc:
                file.section_tcyc.remove(duplicated_vanilla_ipl_object)
    
    # Identify undeclared IPL and IPL Binary objects
    list_objects_to_modify()
    
    ide_ids = {gta_object.obj_id for gta_object in ide_objects}
    
    for inst_object in chain(inst_objects, inst_binary_objects):
        if inst_object.obj_id not in ide_ids and inst_object.obj_id not in vanilla_ids:
            print(f"({inst_object.file_name}) [{inst_object.obj_id},{inst_object.model}] not found in any IDE or in vanilla objects")
        elif inst_object.obj_id not in ide_ids and inst_object.obj_id in vanilla_ids and inst_object.model.lower() != vanilla_objects[inst_object.obj_id].lower():
            print(f"Different model used: ({inst_object.file_name}) [{inst_object.obj_id},{inst_object.model}] x [{inst_object.obj_id},{vanilla_objects[inst_object.obj_id]}] (Vanilla)")

    ide_models = [gta_object.model for gta_object in ide_objects]
    ide_ids = [gta_object.obj_id for gta_object in ide_objects]

    for gta_object in inst_objects:
        if gta_object.obj_id not in ide_ids and gta_object.model not in ide_models:
            if gta_object.model in dff_renames.values():
                gta_object.model = next(key for key, value in dff_renames.items() if value == gta_object.model)
                print('Model altered to vanilla!')


    undeclared_inst_objects = [gta_object for gta_object in inst_objects if gta_object.obj_id not in ide_ids and gta_object.obj_id not in vanilla_ids]
    undeclared_inst_binary_objects = [gta_object for gta_object in inst_binary_objects if gta_object.obj_id not in ide_ids and gta_object.obj_id not in vanilla_ids]
    
    # Identify IPL objects without assets
    update_current_assets_names()
    
    inst_objects_without_assets = [gta_object for gta_object in inst_objects if not object_has_assets(gta_object)]
    temp_invalid_inst_objects = undeclared_inst_objects + undeclared_inst_binary_objects + inst_objects_without_assets
    
    total_invalid_inst_objects = []
    unique_internal_ids = set()
    
    if temp_invalid_inst_objects:
        for obj in temp_invalid_inst_objects:
            if obj.internal_id not in unique_internal_ids:
                unique_internal_ids.add(obj.internal_id)
                total_invalid_inst_objects.append(obj)

    if total_invalid_inst_objects:
        for invalid_inst_object in total_invalid_inst_objects:
            file = invalid_inst_object.file
            if isinstance(file, Ipl) and invalid_inst_object in file.section_inst:
                file.remove_from_section_inst(invalid_inst_object)
                inst_objects.remove(invalid_inst_object)
            elif isinstance(file, IplBinary) and invalid_inst_object in file.section_inst:
                file.section_inst.remove(invalid_inst_object)
                inst_binary_objects.remove(invalid_inst_object)

    # Identify unused IDE objects
    list_objects_to_modify()

    total_inst_ids = {gta_object.obj_id for gta_object in inst_objects} | {gta_object.obj_id for gta_object in inst_binary_objects}
    total_inst_models = {gta_object.model for gta_object in inst_objects} | {gta_object.model for gta_object in inst_binary_objects}
    
    for ide_object in ide_objects:
        if ide_object.obj_id not in total_inst_ids and ide_object.obj_id not in vanilla_ids:
            print(f"({ide_object.file_name}) [{ide_object.obj_id},{ide_object.model}] not found in any IPL or in vanilla objects")
        elif ide_object.obj_id not in total_inst_ids and ide_object.obj_id in vanilla_ids and ide_object.model.lower() != vanilla_objects[ide_object.obj_id].lower():
            print(f"Different model used: ({ide_object.file_name}) [{ide_object.obj_id},{ide_object.model}] x [{ide_object.obj_id},{vanilla_objects[ide_object.obj_id]}] (Vanilla)")
    
    unused_ide_objects = [gta_object for gta_object in ide_objects if gta_object.obj_id not in total_inst_ids and gta_object.model not in total_inst_models]
    unused_ide_objects = list(set(unused_ide_objects))
    
    if unused_ide_objects:
        for invalid_ide_object in unused_ide_objects:
            file = invalid_ide_object.file
            if isinstance(invalid_ide_object, Objs):
                file.section_objs.remove(invalid_ide_object)
            elif isinstance(invalid_ide_object, Tobj):
                file.section_tobj.remove(invalid_ide_object)
            elif isinstance(invalid_ide_object, Anim):
                file.section_anim.remove(invalid_ide_object)

def correct_dummy_models():
    global vanilla_objects
    global ide_objects
    global inst_objects
    global inst_binary_objects
    
    ide_ids_to_models = {gta_object.obj_id: gta_object.model for gta_object in ide_objects}
    
    for gta_object in inst_objects + inst_binary_objects:
        if gta_object.model == 'dummy':
            if gta_object.obj_id in ide_ids_to_models:
                gta_object.model = ide_ids_to_models[gta_object.obj_id]
            elif gta_object.obj_id in vanilla_objects:
                gta_object.model = vanilla_objects[gta_object.obj_id]

def update_ids():
    global vanilla_objects
    global free_ids
    global ide_objects
    global inst_total_objects
    global replaced_ids
    
    list_objects_to_modify()
    vanilla_models = set(vanilla_objects.values())
    ide_ids_models = {gta_object.obj_id: gta_object.model for gta_object in ide_objects}
    
    for gta_object in ide_objects:
        
        if gta_object.model in vanilla_models:
            print(f"({gta_object.file_name}) {gta_object.obj_id},{gta_object.model} is a vanilla object - Removing IDE declaration...")
            
            ide_ids_models.pop(gta_object.obj_id)
            
            file = gta_object.file
            if isinstance(gta_object, Objs):
                file.section_objs.remove(gta_object)
            elif isinstance(gta_object, Tobj):
                file.section_tobj.remove(gta_object)
            elif isinstance(gta_object, Anim):
                file.section_anim.remove(gta_object)
        else:
            print(f"({gta_object.file_name}) Giving new ID to {gta_object.obj_id},{gta_object.model}: ", end = '')
            replace_id(gta_object, free_ids[0])
            print(f"{gta_object.obj_id}")
    
    for gta_object in inst_total_objects:
        
        if (gta_object.obj_id in ide_ids_models or gta_object.model in ide_ids_models.values()):
            # [IPL] 1,chair == [IDE] 1,chair --> [IPL] 1,chair
            if (gta_object.obj_id in ide_ids_models and ide_ids_models[gta_object.obj_id] == gta_object.model):
                gta_object.obj_id = replaced_ids[gta_object.obj_id]
            # [IPL] 1,chair ~~ [IDE] 1,table --> [IPL] 1,table
            elif (gta_object.obj_id in ide_ids_models and ide_ids_models[gta_object.obj_id] != gta_object.model):
                gta_object.model = ide_ids_models[gta_object.obj_id]
                gta_object.obj_id = replaced_ids[gta_object.obj_id]
            # [IPL] 1,chair ~~ [IDE] 2,chair  --> [IPL] 2,chair
            elif (gta_object.obj_id not in ide_ids_models and gta_object.model in ide_ids_models.values()):
                respective_ide_old_id = next((obj_id for obj_id, model in ide_ids_models.items() if model == gta_object.model), None)
                gta_object.obj_id = replaced_ids[respective_ide_old_id]
        else:
            # [IPL] 1,chair == [Vanilla] 1,chair --> [IPL] 1,chair
                
            # [IPL] 1,chair ~~ [Vanilla] 2,chair --> [IPL] 2,chair
            if (gta_object.model in vanilla_objects.values()):
                corresponding_vanilla_id = next((obj_id for obj_id, model in vanilla_objects.items() if model == gta_object.model), None)
                
                if gta_object.obj_id != corresponding_vanilla_id:
                    gta_object.obj_id = corresponding_vanilla_id
                
            # [IPL] 1,chair ~~ [Vanilla] 1,table --> [IPL] 1,table
            elif (gta_object.obj_id in vanilla_objects and vanilla_objects[gta_object.obj_id] != gta_object.model):
                gta_object.model = vanilla_objects[gta_object.obj_id]
            # 1 nor 'chair' in Vanilla --> Remove IPL object
            elif (gta_object.obj_id not in vanilla_objects and gta_object.model not in vanilla_objects.values()):
                if isinstance(gta_object, Inst):
                    file = gta_object.file
                    file.remove_from_section_inst(gta_object)

def replace_id(gta_object, new_id):
    global free_ids
    global replaced_ids
    global ids_in_use
    
    if gta_object.obj_id in replaced_ids:
        gta_object.obj_id = replaced_ids[gta_object.obj_id]
    else:
        replaced_ids[gta_object.obj_id] = new_id
        gta_object.obj_id = new_id
        
        if new_id in free_ids:
            ids_in_use.append(new_id)
            free_ids.remove(new_id)
        
    return gta_object

def modify_coordinates():
    global coordinate_objects
    global map_command_x
    global map_command_y
    global map_command_z
    
    for gta_object in coordinate_objects:
        gta_object.move_coordinates(map_command_x, map_command_y, map_command_z)
        print(f"({gta_object.file_name} - {gta_object.section}) Object {gta_object.index} moved X: {str(map_command_x)}, Y: {str(map_command_y)}, Z: {str(map_command_z)}")

def write_map_files():
    os.makedirs(OUTPUT_MAP_DIR, exist_ok=True)
    
    for file in mod_map_files:
        original_filename = file.file_name
        modified_filepath = os.path.join(OUTPUT_MAP_DIR, original_filename)
        
        if not file_is_empty(file):
            if isinstance(file, IplBinary):
                with open(modified_filepath, 'wb') as modified_file:
                    modified_file.write(file.write_file_sections())
            else:
                with open(modified_filepath, 'w', encoding='utf-8') as modified_file:
                    modified_file.write(file.write_file_sections())
                    
            print(f"Saved {original_filename} at: {modified_filepath}")
        else:
            if os.path.exists(modified_filepath):
                os.remove(modified_filepath)

def rotate_coordinates():
    global coordinate_objects
    global rot_command_x
    global rot_command_y
    global rot_command_z
    global rot_command_w
    
    for gta_object in coordinate_objects:
        if isinstance(gta_object, Inst) or isinstance(gta_object, InstBinary):
            gta_object.move_rotations(rot_command_x, rot_command_y, rot_command_z, rot_command_w)
            print(f"({gta_object.file_name} - {gta_object.section}) Object {gta_object.index} rotated X: {str(rot_command_x)}, Y: {str(rot_command_y)}, Z: {str(rot_command_z)}, W: {str(rot_command_w)}")

def list_vanilla_files():
    global vanilla_files
    
    vanilla_files = {}

    with open(VANILLA_FILES_PATH, 'r', encoding='utf-8') as file:
        for line in file:
            file_name, file_size = line.strip().split(',')
            file_size = int(file_size)
            
            if file_name in vanilla_files:
                current_value = vanilla_files[file_name]
                if isinstance(current_value, list):
                    vanilla_files[file_name].append(file_size)
                else:
                    vanilla_files[file_name] = [current_value, file_size]
            else:
                vanilla_files[file_name] = file_size

def copy_files_to_output():
    gta_dat_file_names = get_gta_dat_filenames()
    gta_dat_file_names = [file_name.lower() for file_name in gta_dat_file_names]
    
    if os.path.exists(OUTPUT_DIR) and os.path.isdir(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    
    for root, dirs, files in os.walk(INPUT_DIR):
        for mod_file in files:
            file_path = os.path.join(root, mod_file)
            is_valid_file = False
            
            if mod_file.lower().endswith('.img'):
                if (not gta_dat_file_names or 
                    mod_file.lower() in gta_dat_file_names or 
                    mod_file.lower() == 'gta3.img' or mod_file.lower() == 'gta_int.img'):
                    is_valid_file = True
            elif mod_file.lower().endswith('.ide'):
                if (not gta_dat_file_names or 
                    mod_file.lower() in gta_dat_file_names or 
                    mod_file.lower() == 'leveldes.ide' or mod_file.lower() == 'txd.ide'):
                    is_valid_file = True
            elif mod_file.lower().endswith('.ipl'):
                if (not gta_dat_file_names or 
                    mod_file.lower() in gta_dat_file_names or 
                    mod_file.lower() == 'leveldes.ipl' or mod_file.lower() == 'occlu.ipl' or mod_file.lower() == 'vegaxref.ipl'):
                    is_valid_file = True
            elif not mod_file.lower().endswith('.txt') and mod_file.lower() != 'gta.dat':
                is_valid_file = True
                    
            if is_valid_file:
                if mod_file.lower().endswith('.img'):
                    file_output_dir = OUTPUT_IMG_DIR
                elif (mod_file.lower().endswith('.ide') or mod_file.lower().endswith('.ipl') or 
                      mod_file.lower() == 'water.dat' or mod_file.lower() == 'object.dat'):
                    file_output_dir = OUTPUT_MAP_DIR
                else:
                    file_output_dir = OUTPUT_ASSETS_DIR
                    
                os.chmod(file_path, stat.S_IWRITE)
                os.makedirs(file_output_dir, exist_ok=True)
                shutil.copy(os.path.join(root, mod_file), file_output_dir)
            
def get_gta_dat_filenames():
    gta_dat_file_names = []
    gta_dat_path = ''
    file_path_pattern = re.compile(r'[^\\]+\.[\w]+')
    
    for root, dirs, files in os.walk(INPUT_DIR):
        if 'gta.dat' in files:
            gta_dat_path = os.path.join(root, 'gta.dat')
            break
    
    if os.path.isfile(gta_dat_path):
        gta_dat_encoding = detect_file_encoding(gta_dat_path)
        
        with open(gta_dat_path, 'r', encoding=gta_dat_encoding) as file:
            for line in file:
                
                line = line.strip()
                match = file_path_pattern.search(line)
                
                if match and not line.startswith('#'):
                    file_name = os.path.basename(match.group())
                    gta_dat_file_names.append(file_name)

    return gta_dat_file_names

def uniquify_mod_files():
    global path_command
    global object_resources_renames
    global existent_binary_ipl_files
    unpacked_img_directories = []
    assets_directory = []
    files_directories = []
    col_file_paths = []
    dff_file_paths = []
    txd_file_paths = []
    map_file_paths = []
    node_file_paths = []
    other_file_paths = []
    
    # Unpack each IMG file
    if os.path.exists(OUTPUT_IMG_DIR):
        rename_duplicated_col_files()
        
        for root, dirs, files in os.walk(OUTPUT_IMG_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                unpack_img_file(file_path)
                
        # Check for binary IPL files
        ipl_binary_pattern = os.path.join(OUTPUT_IMG_DIR, '**', '*_stream*.ipl')
        
        if glob.glob(ipl_binary_pattern, recursive=True):
            existent_binary_ipl_files = True
                
    # Get every file path
    if os.path.exists(OUTPUT_IMG_DIR):
        unpacked_img_directories = [os.path.join(OUTPUT_IMG_DIR, d) for d in os.listdir(OUTPUT_IMG_DIR) if os.path.isdir(os.path.join(OUTPUT_IMG_DIR, d))]
        
        if len(unpacked_img_directories) == 1:
            files_directories.append(unpacked_img_directories[0])
        else:
            files_directories.extend(unpacked_img_directories)

    if os.path.exists(OUTPUT_ASSETS_DIR):
        assets_directory = OUTPUT_ASSETS_DIR
        files_directories.append(assets_directory)
    
    unique_files = {}
    
    for directory in files_directories:
        if os.path.exists(directory):
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    if file.lower() in unique_files:
                        print(f"Removing duplicated file: {file_path}")
                        os.remove(file_path)
                    else:
                        unique_files[file.lower()] = file_path
                    
                        if file.lower().endswith('.col'):
                            col_file_paths.append(file_path)
                        elif file.lower().endswith('.dff'):
                            dff_file_paths.append(file_path)
                        elif file.lower().endswith('.txd'):
                            txd_file_paths.append(file_path)
                        elif file.lower().endswith('.ide') or file.lower().endswith('.ipl'):
                            map_file_paths.append(file_path)
                        elif re.match(r'^nodes\d+\.dat$', file.lower()):
                            node_file_paths.append(file_path)
                        else:
                            other_file_paths.append(file_path)
    
    # Move every node file to a temporary location
    if os.path.exists(SA_PATHS_DATA_EXTENDER_INPUT_DIR) and os.path.isdir(SA_PATHS_DATA_EXTENDER_INPUT_DIR):
        shutil.rmtree(SA_PATHS_DATA_EXTENDER_INPUT_DIR)
        
    if os.path.exists(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR) and os.path.isdir(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR):
        shutil.rmtree(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR)
        
    if node_file_paths and map_command and path_command:
        os.makedirs(SA_PATHS_DATA_EXTENDER_INPUT_DIR, exist_ok=True)
        
        for file_path in node_file_paths:
            shutil.move(file_path, SA_PATHS_DATA_EXTENDER_INPUT_DIR)
    else:
        for file_path in node_file_paths:
            os.remove(file_path)
    
    # Uniquify every COL file
    for file_path in col_file_paths:
        uniquify_asset_file(file_path)
    
    # Uniquify every DFF file
    for file_path in dff_file_paths:
        uniquify_asset_file(file_path)
    
    # Uniquify every TXD file
    for file_path in txd_file_paths:
        uniquify_asset_file(file_path)

    # Uniquify every other file
    for file_path in other_file_paths:
        uniquify_asset_file(file_path)
    
    # Uniquify and move every leftover map file
    for file_path in map_file_paths:
        uniquified_file_path = uniquify_asset_file(file_path)
        
        if uniquified_file_path:
            map_file = os.path.basename(uniquified_file_path)
            os.makedirs(OUTPUT_MAP_DIR, exist_ok=True)
            new_file_path = os.path.join(OUTPUT_MAP_DIR, map_file)
            shutil.move(uniquified_file_path, new_file_path)
        
    # Repack and uniquify each IMG file
    if unpacked_img_directories:
        file_type = '.img'
        for directory in unpacked_img_directories:
            img_file_base_name = os.path.basename(directory)
            img_file_name = f'{img_file_base_name}{file_type}'
            img_file_path = os.path.join(OUTPUT_IMG_DIR, img_file_name)
            pack_img_file(img_file_path, directory)
            
            if os.path.isfile(img_file_path):
                img_file_new_name = rename_file(img_file_name)
                img_file_new_path = os.path.join(OUTPUT_IMG_DIR, img_file_new_name)
                os.rename(img_file_path, img_file_new_path)
                
                if img_file_name in inst_binary_files:
                    inst_binary_files[img_file_new_name] = inst_binary_files.pop(img_file_name)
        
    # Uniquify every map file
    if os.path.exists(OUTPUT_MAP_DIR):
        for root, dirs, files in os.walk(OUTPUT_MAP_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                uniquify_map_file(file_path)

def move_paths():
    global map_command_x
    global map_command_y
    global map_command_z
    
    for node_file in os.listdir(SA_PATHS_DATA_EXTENDER_INPUT_DIR):
        node_file_path = os.path.join(SA_PATHS_DATA_EXTENDER_INPUT_DIR, node_file)
        
        if is_vanilla_file(node_file_path) or is_fastman_node_format(node_file_path):
            os.remove(node_file_path)
            
    if any(os.scandir(SA_PATHS_DATA_EXTENDER_INPUT_DIR)):
        os.makedirs(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR, exist_ok=True)
        pathsExtender = SAPathsDataExtender()
        paths_moved = pathsExtender.run(map_command_x, map_command_y, map_command_z)
        
        if paths_moved:
            os.makedirs(OUTPUT_PATHS_DIR, exist_ok=True)
            
        for node_file in os.listdir(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR):
            node_file_path = os.path.join(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR, node_file)
            
            if os.path.isfile(node_file_path):
                shutil.move(node_file_path, os.path.join(OUTPUT_PATHS_DIR, node_file))
            
        if os.path.exists(SA_PATHS_DATA_EXTENDER_INPUT_DIR) and os.path.isdir(SA_PATHS_DATA_EXTENDER_INPUT_DIR):
            shutil.rmtree(SA_PATHS_DATA_EXTENDER_INPUT_DIR)
            
        if os.path.exists(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR) and os.path.isdir(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR):
            shutil.rmtree(SA_PATHS_DATA_EXTENDER_OUTPUT_DIR)

def uniquify_map_objects():
    global vanilla_dat_objects
    
    for file in mod_map_files:
        if isinstance(file, Ide):
            sections = [file.section_objs, file.section_tobj, file.section_anim, file.section_cars, file.section_hier, file.section_peds, file.section_weap]
            section_txdp = file.section_txdp
            
            for section in sections:
                if section:
                    for obj in section:
                        if obj.model in dff_renames:
                            obj.model = dff_renames[obj.model]
                        if obj.texture in txd_renames:
                            obj.texture = txd_renames[obj.texture]
            
            if section_txdp:
                for obj in section_txdp:
                    if obj.texture in txd_renames:
                        obj.texture = txd_renames[obj.texture]
                    if obj.texture_parent in txd_renames:
                        obj.texture_parent = txd_renames[obj.texture_parent]
                        
        elif isinstance(file, Ipl):
            if file.section_inst:
                for obj in file.section_inst:
                    if obj.model in dff_renames:
                        obj.model = dff_renames[obj.model]
                        
        elif isinstance(file, Dat):
            if file.section_datobj:
                for obj in file.section_datobj:
                    if obj.model in vanilla_dat_objects:
                        file.section_datobj.remove(obj)
                    elif obj.model in dff_renames:
                        obj.model = dff_renames[obj.model]

def unpack_img_file(file_path):
    img_file = os.path.basename(file_path)
    img_file_base_name = os.path.splitext(img_file)[0]
    img_file_directory = os.path.dirname(file_path)
    os.makedirs(img_file_directory, exist_ok=True)
    unpacked_img_file_path = os.path.join(img_file_directory, img_file_base_name)
    
    if img_file.lower().endswith('.img'):
        img_console.start()
        
        if img_console.open_img(file_path):
            img_console.export_all(file_path, unpacked_img_file_path)
            correct_unpacked_img_faulty_files(unpacked_img_file_path)
            img_console.delete_all(file_path)
            img_console.rebuild(file_path)
            
        img_console.close()
        
def correct_unpacked_img_faulty_files(unpacked_img_file_path):
    for file_name in os.listdir(unpacked_img_file_path):
        file_type = os.path.splitext(file_name)[1].lower()
        file_path = os.path.join(unpacked_img_file_path, file_name)
        file_size = os.path.getsize(file_path)
        wrong_file_type = False
        
        if file_size == 0:
            os.remove(file_path)
        else:
            if not file_type or len(file_type) < 4:
                os.remove(file_path)
            elif file_type == '.c' or file_type == '.co':
                wrong_file_type = True
                new_filename = file_name[:-3] + '.col'
            elif file_type == '.da':
                wrong_file_type = True
                new_filename = file_name[:-3] + '.dat'
            elif file_type == '.df':
                wrong_file_type = True
                new_filename = file_name[:-3] + '.dff'
            elif file_type == '.if':
                wrong_file_type = True
                new_filename = file_name[:-3] + '.ifp'
            elif file_type == '.ip':
                wrong_file_type = True
                new_filename = file_name[:-3] + '.ipl'
            
        if wrong_file_type:
            new_file_path = os.path.join(unpacked_img_file_path, new_filename)
            os.rename(file_path, new_file_path)
        
def pack_img_file(img_file_path, unpacked_img_path):
    img_file_name = os.path.basename(img_file_path)
    img_console.start()
    
    if img_console.open_img(img_file_path):
        directory_has_files = (any(os.path.isfile(os.path.join(unpacked_img_path, f)) and 
                                os.path.getsize(os.path.join(unpacked_img_path, f)) > 0 for f in os.listdir(unpacked_img_path)))
        
        if directory_has_files:
            correct_unpacked_img_faulty_files(unpacked_img_path)
            img_console.import_all(img_file_path, unpacked_img_path)
            img_console.rebuild(img_file_path)
            
        img_has_files = img_console.has_files(img_file_path)
    
    img_console.close()
    
    if not img_has_files and img_file_name not in inst_binary_files:
        os.remove(img_file_path)
        
    shutil.rmtree(unpacked_img_path)

def rename_duplicated_col_files():
    if os.path.exists(OUTPUT_IMG_DIR) and os.listdir(OUTPUT_IMG_DIR):
        img_console.start()
        
        for mod_file in os.listdir(OUTPUT_IMG_DIR):
            mod_file_path = f"{OUTPUT_IMG_DIR}\\{mod_file}"
            col_files = []
            duplicated_col_files = {}
            
            if img_console.open_img(mod_file_path):
                mod_img_entries = img_console.print_list_of_entries(mod_file_path)
                
                if mod_img_entries:
                    for entry in mod_img_entries:
                        if "Name:" in entry:
                            match = re.match(r'^[^\x00-\x1F]*', entry.split("Name:")[1].strip())
                            file_name = match.group(0) if match else entry.split("Name:")[1].strip()
                            base_name = os.path.splitext(file_name)[0]
                            file_type = os.path.splitext(file_name)[1].lower()
                            
                            if file_type == '.col':
                                if base_name not in col_files:
                                    col_files.append(base_name)
                                elif base_name in col_files and base_name not in duplicated_col_files:
                                    duplicated_col_files[base_name] = 2
                                elif base_name in col_files and base_name in duplicated_col_files:
                                    duplicated_col_files[base_name] += 1
                                    
                    for duplicated_col_file in duplicated_col_files:
                        file_name = f'{duplicated_col_file}.col'
                        for i in range(1, duplicated_col_files[duplicated_col_file] + 1):
                            file_new_name = f'{duplicated_col_file[:16]}_{i}.col'
                            img_console.rename(file_name, file_new_name)

def uniquify_img_file(file_path):
    mod_file = os.path.basename(file_path)
    directory = os.path.dirname(file_path)
    
    if mod_file.lower().endswith('.img'):
        # Opens .IMG file
        img_console.start()
        
        if img_console.open_img(file_path):
            img_console.export_all(file_path, IMG_CONSOLE_TEMP_DIR)
            img_console.delete_all(file_path)
            img_console.rebuild(file_path)
            
            for img_file_name in os.listdir(IMG_CONSOLE_TEMP_DIR):
                img_file_path = os.path.join(IMG_CONSOLE_TEMP_DIR, img_file_name)
                img_file_type = os.path.splitext(img_file_name)[1].lower()
                
                if img_file_type == '.ipl':
                    new_img_file_path = os.path.join(OUTPUT_MAP_DIR, img_file_name)
                    shutil.move(img_file_path, new_img_file_path)
                else:
                    uniquify_asset_file(img_file_path)
                    
            remove_files_without_collision(IMG_CONSOLE_TEMP_DIR)
                    
            img_console.import_all(file_path, IMG_CONSOLE_TEMP_DIR)
            img_console.rebuild(file_path)
            file_new_name = rename_file(mod_file)
            mod_new_file_path = os.path.join(directory, file_new_name)
        
        img_console.close()
        
        if not mod_file in VANILLA_IMG_FILE_NAMES:
            os.rename(file_path, mod_new_file_path)
        
        shutil.rmtree(IMG_CONSOLE_TEMP_DIR)

def remove_files_without_collision(directory):
    global new_col_files
    new_col_files_set = set(new_col_files)
            
    for img_file_name in os.listdir(directory):
        img_file_path = os.path.join(directory, img_file_name)
        img_file_base_name = os.path.splitext(img_file_name)[0].lower()
        img_file_type = os.path.splitext(img_file_name)[1].lower()
        
        if img_file_type == '.dff' and img_file_base_name not in new_col_files_set:
            os.remove(img_file_path)

def is_vanilla_file(file_path):
    global vanilla_files
    global vanilla_objects
    global vanilla_models
    
    file_name = os.path.basename(file_path)
    base_name = os.path.splitext(file_name)[0].lower()
    file_type = os.path.splitext(file_name)[1].lower()
    file_size = os.path.getsize(file_path)
    
    if file_name in vanilla_files:
        # A COL file should be considered vanilla only if it is identical, as it might have the same name
        # but contain new models. Same for NODES.DAT files, that might be new but can still be using vanilla names.
        if file_type == '.col' or re.match(r'^nodes\d+\.dat$', file_name.lower()):
            if ((isinstance(vanilla_files[file_name], list) and file_size in vanilla_files[file_name]) or 
                file_size == vanilla_files[file_name]):
                    return True
                
        # DFF and TXD Files should be considered vanilla only if they are also declared in a vanilla IDE 
        elif file_type == '.dff' or file_type == '.txd':
            if base_name in vanilla_models:
                return True
        else:
            return True
                
    return False

def uniquify_asset_file(file_path):
    mod_file = os.path.basename(file_path)
    file_name = mod_file
    file_type = os.path.splitext(file_name)[1].lower()
    directory_path = os.path.dirname(file_path)
    directory_name = os.path.basename(directory_path)
    base_name = os.path.splitext(file_name)[0]
    
    if file_type == '.ipl' and '_stream' in file_name:
        index = base_name.find('_stream')
        base_name_end = base_name[index:]
        base_name = base_name[:index]
    
    col_models_renames_lower = {k.lower(): v for k, v in col_models_renames.items()}
    to_be_removed = False
    to_get_new_name = False
    new_file_path = None
    
    if is_vanilla_file(file_path):
        to_be_removed = True
    else:
        if file_type != '.dff':
            # If another file with the same name has already been renamed, use its new name
            if base_name in object_resources_renames:
                base_new_name = object_resources_renames[base_name]
                
                if file_type == '.ipl' and '_stream' in file_name:
                    base_new_name = base_new_name + base_name_end
            else:
                to_get_new_name = True
        else:
            # In case of DFFs, if it has a respective COL file, use its new name
            if base_name in col_models_renames:
                base_new_name = col_models_renames[base_name]
            # If not, check again, but in lowercase
            elif base_name.lower() in col_models_renames_lower:
                base_new_name = col_models_renames_lower[base_name.lower()]
            # If no respective COL file has been found, give it a new name, as it might be a LOD object
            else:
                to_get_new_name = True

    if to_be_removed:
        os.remove(file_path)
    else:
        if to_get_new_name:
            file_new_name = rename_file(file_name)
            base_new_name = os.path.splitext(file_new_name)[0]
            
            if file_type == '.ipl' and '_stream' in file_name:
                index = base_new_name.find('_stream')
                object_resources_renames[base_name] = base_new_name[:index]
            else:
                object_resources_renames[base_name] = base_new_name
            
        if file_type == '.dff':
            dff_renames[base_name.lower()] = base_new_name
        elif file_type == '.txd':
            txd_renames[base_name.lower()] = base_new_name
            
        file_new_name = base_new_name + file_type
        new_file_path = os.path.join(directory_path, file_new_name)
        os.rename(file_path, new_file_path)
        
        if file_type == '.ipl' and '_stream' in file_name:
            img_file = f'{directory_name}.img'
            
            if img_file in inst_binary_files:
                inst_binary_files[img_file].append(file_new_name)
            else:
                inst_binary_files[img_file] = [file_new_name]
        
        if file_type == '.col':
            uniquify_col_models(new_file_path)
            
    if new_file_path:
        return new_file_path

def uniquify_col_models(file_path):
    col_file_content = read_file(file_path, 'binary')
    file_name = os.path.basename(file_path)
    # Create a Col object for this file, to gather its models' names
    col_file = Col(file_name, col_file_content)
    
    for col_entry in col_file.section_cols:
        col_entry_name = col_entry.model
        
        if col_entry_name in col_models_renames:
            col_entry_new_name = col_models_renames[col_entry_name]
        else:
            col_entry_file_new_name = rename_file(f'{col_entry_name}.col')
            col_entry_new_name = os.path.splitext(col_entry_file_new_name)[0]
            object_resources_renames[col_entry_name] = col_entry_new_name
            col_models_renames[col_entry_name] = col_entry_new_name
        
        col_entry.model = col_entry_new_name
        
    with open(file_path, 'wb') as modified_file:
        modified_file.write(col_file.write_file_sections())

def uniquify_map_file(file_path):
    mod_file = os.path.basename(file_path)
    base_name = os.path.splitext(mod_file)[0]
    file_type = os.path.splitext(mod_file)[1].lower()
    
    if (file_type == '.ide' or 
        (file_type == '.ipl' and detect_file_encoding(file_path) != 'binary')):
        directory = os.path.dirname(file_path)
        
        if base_name in object_resources_renames:
            file_new_name = f'{object_resources_renames[base_name]}{file_type}'
        else:
            file_new_name = rename_file(mod_file)
            
        mod_new_file_path = os.path.join(directory, file_new_name)
        os.rename(file_path, mod_new_file_path)

def generate_unique_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def rename_file(file_name):
    global existent_binary_ipl_files
    global dff_models
    global col_models
    unique_id = generate_unique_id()
    base_name = os.path.splitext(file_name)[0]
    base_name = unidecode.unidecode(base_name)
    file_type = os.path.splitext(file_name)[1].lower()
    
    # Names should have a max length of 19 characters. Since '_{unique ID}' takes 7 characters, and
    # the '_streamXX' sufix required for binary IPLs takes 9 characters, the original filenames for
    # object-related files can be preserved up to 3 characters only.
    if (existent_binary_ipl_files and (file_type == '.dff' or 
        file_type == '.col' or file_type == '.txd' or
        file_type =='.ipl' or file_type == '.ide')):
        base_name_start = base_name[:3]
    else:
        base_name_start = base_name[:12]
        
    if file_type == '.ipl' and '_stream' in file_name:
        index = base_name.find('_stream')
        base_name_end = base_name[index:]
        new_name = f"{base_name_start.lower()}_{unique_id}{base_name_end.lower()}{file_type}"
    else:
        new_name = f"{base_name_start.lower()}_{unique_id}{file_type}"
        
    base_new_name = os.path.splitext(new_name)[0]
        
    if file_type == '.dff':
        dff_models.append(base_new_name.lower())
    elif file_type == '.col':
        col_models.append(base_new_name.lower())
        
    return new_name

def build_mod_dat():
    mod_dat_path = os.path.join(OUTPUT_DIR, 'mod_dat.txt')
    
    with open(mod_dat_path, 'w', encoding='utf-8') as mod_dat:
        line_break_pending = False
        img_files, ide_files, ipl_files, col_files = [], [], [], []
        
        if os.path.exists(OUTPUT_IMG_DIR):
            img_files = sorted([f for f in os.listdir(OUTPUT_IMG_DIR) if f.lower().endswith('.img')])
        
        if os.path.exists(OUTPUT_MAP_DIR):
            ide_files = sorted([f for f in os.listdir(OUTPUT_MAP_DIR) if f.lower().endswith('.ide')])
            ipl_files = sorted([f for f in os.listdir(OUTPUT_MAP_DIR) if f.lower().endswith('.ipl')])
        
        if os.path.exists(OUTPUT_ASSETS_DIR):
            col_files = sorted([f for f in os.listdir(OUTPUT_ASSETS_DIR) if f.lower().endswith('.col')])
        
        if img_files:
            for img_file in img_files:
                mod_dat.write(f"IMG MODLOADER\\{img_file}\n")
            line_break_pending = True
            
        if line_break_pending:
            mod_dat.write("\n")
            line_break_pending = False
            
        if ide_files:
            for ide_file in ide_files:
                mod_dat.write(f"IDE MODLOADER\\{ide_file}\n")
            line_break_pending = True
            
        if line_break_pending:
            mod_dat.write("\n")
            line_break_pending = False
            
        if ipl_files:
            for ipl_file in ipl_files:
                mod_dat.write(f"IPL MODLOADER\\{ipl_file}\n")
            line_break_pending = True
            
        if line_break_pending:
            mod_dat.write("\n")
            line_break_pending = False

        if col_files:
            for col_file in col_files:
                mod_dat.write(f"COLFILE 0 MODLOADER\\{col_file}\n")
            line_break_pending = True

def get_vanilla_placements():
    global vanilla_placements
    vanilla_placements = set()
    
    with open(VANILLA_PLACEMENTS_PATH, 'r') as f:
        for line in f:
            elements = line.strip().split(',')
            elements = get_placement(elements)
            vanilla_placements.add(tuple(elements))

def repack_inst_binary_files():
    global inst_binary_files
    
    if inst_binary_files:
        img_console.start()
        
        for img_file in inst_binary_files:
            img_file_path = os.path.join(OUTPUT_IMG_DIR, img_file)
            
            if img_console.open_img(img_file_path):
                for inst_binary_file in inst_binary_files[img_file]:
                    temp_directory = os.path.join(OUTPUT_MAP_DIR, 'temp')
                    os.makedirs(temp_directory, exist_ok=True)
                    
                    inst_binary_file_path = os.path.join(OUTPUT_MAP_DIR, inst_binary_file)
                    inst_binary_temp_file_path = os.path.join(temp_directory, inst_binary_file)
                    shutil.move(inst_binary_file_path, inst_binary_temp_file_path)
                    
                img_console.import_all(img_file_path, temp_directory)
                img_console.rebuild(img_file_path)

        img_console.close()
        
        if os.path.exists(temp_directory):
            shutil.rmtree(temp_directory)
            
def read_mod_placement_files():
    placement_files = []
    
    if os.path.exists(OUTPUT_MAP_DIR):
        for file_name in os.listdir(OUTPUT_MAP_DIR):
            file_extension = os.path.splitext(file_name)[1][1:].lower()
            
            if file_extension == 'ipl':
                file_path = os.path.join(OUTPUT_MAP_DIR, file_name)
                file_encoding = detect_file_encoding(file_path)
                file_content = read_file(file_path, file_encoding)
                
                if file_encoding == 'binary':
                    file = IplBinary(file_name, file_content)
                else:
                    file = Ipl(file_name, file_content)
                        
                placement_files.append(file)
    
    return placement_files

def read_installed_placement_files():
    mods_placement_files = {}
    
    if os.path.exists(SA_MODLOADER_DIR):
        mods_directories = [modloader_item for modloader_item in os.listdir(SA_MODLOADER_DIR) if os.path.isdir(os.path.join(SA_MODLOADER_DIR, modloader_item))]

        for mod_directory in mods_directories:
            mod_name = mod_directory
            mod_directory_path = os.path.join(SA_MODLOADER_DIR, mod_directory)

            mod_ipl_filepaths = [str(filepath) for filepath in Path(mod_directory_path).rglob("*.ipl")]
            
            if mod_ipl_filepaths:
                mod_placement_files = []
                
                for mod_ipl_filepath in mod_ipl_filepaths:
                    file_name = os.path.basename(mod_ipl_filepath)
                    file_encoding = detect_file_encoding(mod_ipl_filepath)
                    file_content = read_file(mod_ipl_filepath, file_encoding)
                    
                    if file_encoding == 'binary':
                        file = IplBinary(file_name, file_content)
                    else:
                        file = Ipl(file_name, file_content)

                    mod_placement_files.append(file)
                
                if mod_placement_files:
                    mods_placement_files[mod_name] = mod_placement_files
    
    return mods_placement_files

def get_mod_coordinates(placement_files):
    coordinates = []
    for file in placement_files:
        if isinstance(file, Ipl):
            sections = [file.section_inst]
        else:
            sections = []
        
        for section in sections:
            if section:
                for obj in section:
                    if (get_placement(obj.get_content_elements()) not in vanilla_placements):
                        coordinates.append((obj.x_pos, obj.y_pos))

    return coordinates

def get_installed_mods_coordinates(installed_placement_files):
    installed_mods_coordinates = {}
    
    for mod in installed_placement_files:
        placement_files = installed_placement_files[mod]
        coordinates = []
    
        for file in placement_files:
            if isinstance(file, Ipl) and 'seabed' not in file.file_name:
                sections = [file.section_inst]
            else:
                sections = []
            
            for section in sections:
                if section:
                    for obj in section:
                        if (get_placement(obj.get_content_elements()) not in vanilla_placements and
                            'seabed' not in obj.model):
                            coordinates.append((obj.x_pos, obj.y_pos))
                            
        installed_mods_coordinates[mod] = coordinates

    return installed_mods_coordinates

def update_current_assets_names():
    global vanilla_files_basenames
    global dff_new_basenames
    global col_models_new_basenames
    global txd_new_basenames
    
    vanilla_files_basenames = set(os.path.splitext(key)[0] for key in vanilla_files.keys())
    dff_new_basenames = set(dff_renames.values())
    col_models_new_basenames = set(col_models_renames.values())
    txd_new_basenames = set(txd_renames.values())

def object_has_assets(gta_object):
    global vanilla_files_basenames
    global dff_new_basenames
    global col_models_new_basenames
    global txd_new_basenames
    file = gta_object.file
    
    if isinstance(file, Ide):
        # An IDE object's texture needs to have a respective TXD file, be it from the mod or from vanilla
        if (gta_object.texture in txd_new_basenames or gta_object.texture in vanilla_files_basenames):
            if isinstance(gta_object, (Objs, Tobj, Anim, CarsIde, Hier, Peds, Weap)):
                # In case of most IDE data entries, its model also needs to have a respective DFF file, be it from the mod or from vanilla.
                # It doesn't need to be checked for a respective COL file, as it could be used as LOD, and therefore use another object's COL file.
                if (gta_object.model in dff_new_basenames or gta_object.model in vanilla_files_basenames):
                    return True
            elif isinstance(gta_object, Txdp):
                # In case of TXDP data entries, its parent texture also needs to have a respective TXD file, be it from the mod or from vanilla
                if (gta_object.texture_parent in txd_new_basenames or gta_object.texture_parent in vanilla_files_basenames):
                    return True
    elif isinstance(file, Ipl):
        if isinstance(gta_object, Inst):
            # An INST object, when it is a LOD, will have its assets tied to its corresponding main object
            if gta_object.is_lod:
                asset_object = next((obj for obj in file.section_inst if obj.internal_lod_id == gta_object.internal_id), None)
            # And when it is not a LOD, it will have assets tied to itself
            else:
                asset_object = gta_object
                
            # Whichever is the asset object for an INST object, its model needs to have a respective DFF file, be it from the mod or from vanilla
            if ((asset_object.model in dff_new_basenames and asset_object.model in col_models_new_basenames) or asset_object.model in vanilla_files_basenames):
                return True
            
    return False
                
def get_placement(line_elements):
    normalized_elements = []

    try:
        float(line_elements[1])
        is_second_element_number = True
    except ValueError:
        is_second_element_number = False

    for index, element in enumerate(line_elements):
        if '.' in element or 'e' in element.lower():
            try:
                # Every numeric number needs to be rounded so minimal differences in value between
                # vanilla and mod placements can be ignored
                element = str(round(float(element), 2))
            except ValueError:
                pass

        normalized_elements.append(element)
    
    if is_second_element_number:
        return tuple(normalized_elements)
    else:
        # In case of INST objects, their ID, model and coordinates alone are enough to identify a placement
        return tuple(normalized_elements[i] for i in [0, 1, 3, 4, 5])

def file_is_empty(file):
    section_names = [
        '_section_objs',
        '_section_tobj',
        '_section_path',
        '_section_2dfx',
        '_section_anim',
        '_section_txdp',
        '_section_cars',
        '_section_hier',
        '_section_peds',
        '_section_weap',
        '_section_inst',
        '_section_cull',
        '_section_grge',
        '_section_enex',
        '_section_pick',
        '_section_jump',
        '_section_tcyc',
        '_section_auzo',
        '_section_mult',
        '_section_occl',
        '_section_zone',
        '_section_water',
        '_section_datobj'
    ]

    return all(
        not hasattr(file, name) or
        not getattr(file, name) or
        (isinstance(getattr(file, name), list) and len(getattr(file, name)) == 0)
        for name in section_names
    )

#region Main
if __name__ == '__main__':
    print("Starting toolset!")
    
    parser = argparse.ArgumentParser(description = 'GTASA Map Tools')
    parser.add_argument('-fix', action='store_true', help='Remove unused game objects')
    parser.add_argument('-id', action='store_true', help='Replace game objects IDs')
    parser.add_argument('-path', action='store_true', help='Move paths')
    parser.add_argument('-map', nargs = 3, metavar=('X', 'Y', 'Z'), type = float, help = 'Move game objects coordinates')
    parser.add_argument('-rot', nargs = 4, metavar=('X', 'Y', 'Z', 'W'), type = float, help = 'Rotate game objects coordinates')
    args = parser.parse_args()
    fix_command = args.fix
    id_command = args.id
    path_command = args.path
    map_command = args.map is not None
    map_command_x = args.map[0] if map_command else None
    map_command_y = args.map[1] if map_command else None
    map_command_z = args.map[2] if map_command else None
    rot_command = args.rot is not None
    rot_command_x = args.rot[0] if rot_command else None
    rot_command_y = args.rot[1] if rot_command else None
    rot_command_z = args.rot[2] if rot_command else None
    rot_command_w = args.rot[3] if rot_command else None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    get_vanilla_placements()
    list_vanilla_files()
    get_vanilla_objects()
    get_vanilla_dat_objects()
    get_free_ids()
    get_installed_mods_coordinates(read_installed_placement_files())
    process_files()
    build_mod_dat()
    print('Finished processing files!')
#endregion