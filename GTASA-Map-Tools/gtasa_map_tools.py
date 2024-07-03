import argparse
import os
import chardet
from collections import defaultdict
from data_entry_types.data_entry import DataEntry
from data_entry_types.ide.anim import Anim
from data_entry_types.ide.objs import Objs
from data_entry_types.ide.tobj import Tobj
from data_entry_types.ipl.auzo import Auzo
from data_entry_types.ipl.cars import Cars
from data_entry_types.ipl.cull import Cull
from data_entry_types.ipl.enex import Enex
from data_entry_types.ipl.grge import Grge
from data_entry_types.ipl.inst import Inst
from data_entry_types.ipl.occl import Occl
from data_entry_types.ipl.pick import Pick
from data_entry_types.ipl.tcyc import Tcyc

#region Constants
INPUT_DIR = "files"
OUTPUT_DIR = "modified_files"
RESOURCES_DIR = "resources"
VANILLA_OBJECTS_FILE_PATH = os.path.join(RESOURCES_DIR, "vanilla_objects.txt")
FREE_IDS_FILE_PATH = os.path.join(RESOURCES_DIR, "Free IDs List.txt")
IDS_IN_USE_FILE_PATH = os.path.join(RESOURCES_DIR, "ids_in_use.txt")
IDE_FILE_EXTENSION = 'ide'
IPL_FILE_EXTENSION = 'ipl'
#endregion

#region Global variables
id_command = False
map_command = False
map_command_x = 0
map_command_y = 0
map_command_z = 0
vanilla_objects = {}
free_ids = []
ids_in_use = []
replaced_ids = {}
input_ide_objects = {}
input_ipl_objects = defaultdict(list)
#endregion

#region Functions
def detect_file_encoding(file_path):
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']

def read_file(file_path):
    encoding = detect_file_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
        return f.readlines()

def modify_lines(lines, file_extension):
    modified_lines = []
    current_section = None
    line_position = -1
    
    if (file_extension == IDE_FILE_EXTENSION or file_extension == IPL_FILE_EXTENSION):
        for line in lines:
            modified_line = None
            data_entry = DataEntry(line, None, file_extension)
            
            if data_entry.is_comment():
                modified_lines.append(data_entry.line.rstrip("\n"))
                continue
            
            if data_entry.is_section_starter():
                modified_lines.append(data_entry.formated_line())
                data_entry.section = data_entry.formated_line()
                current_section = data_entry.section
                continue
                
            if data_entry.is_section_finalizer():
                modified_lines.append(data_entry.formated_line())
                data_entry.section = None
                current_section = data_entry.section
                line_position = -1
                continue
            
            if not current_section is None:
                data_entry.section = current_section
            
            if data_entry.is_object_in_valid_session():
                line_position += 1
                
                if current_section == 'objs':
                    gta_object = Objs(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'tobj':
                    gta_object = Tobj(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'anim':
                    gta_object = Anim(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'inst':
                    gta_object = Inst(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'cull':
                    gta_object = Cull(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'grge':
                    gta_object = Grge(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'enex':
                    gta_object = Enex(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'pick':
                    gta_object = Pick(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'tcyc':
                    gta_object = Tcyc(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'auzo':
                    gta_object = Auzo(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'cars':
                    gta_object = Cars(data_entry.line, data_entry.section, data_entry.file_type) 
                elif current_section == 'occl':
                    gta_object = Occl(data_entry.line, data_entry.section, data_entry.file_type) 
                else:
                    modified_lines.append(data_entry.formated_line())
                    continue
                
                # If the object has an ID
                if (isinstance(gta_object, Objs) or isinstance(gta_object, Tobj) or 
                    isinstance(gta_object, Anim) or isinstance(gta_object, Inst)):
                    
                    if id_command:
                        gta_object = update_id(gta_object)
                
                # If the object has coordinates
                if (isinstance(gta_object, Inst) or isinstance(gta_object, Cull) or
                    isinstance(gta_object, Grge) or isinstance(gta_object, Enex) or
                    isinstance(gta_object, Pick) or isinstance(gta_object, Tcyc) or
                    isinstance(gta_object, Auzo) or isinstance(gta_object, Cars) or
                    isinstance(gta_object, Occl)):
                    
                    if map_command:
                        gta_object = move_coordinates(gta_object)
                        
                modified_lines.append(gta_object.formated_line())
                
    else:
        print(f"File type not supported: {file_extension}")
        
    return modified_lines

def update_id(gta_object):
    global vanilla_objects
    global free_ids
    
    gta_object.line = gta_object.formated_line()
    line_was_corrected = False
    
    for vanilla_object_id, vanilla_object_model in vanilla_objects.items():
        # If the object model is a vanilla model,
        if gta_object.model == vanilla_object_model:
            # and it uses the same ID,
            if gta_object.obj_id == int(vanilla_object_id):
                if not isinstance(gta_object, Inst):
                    # remove the object declaration, in case it's an IDE file
                    gta_object.line = f'# removed vanilla object declaration ({gta_object.obj_id}, {gta_object.model})'
            # and it uses a wrong ID,
            else:
                # remove the object declaration, in case it's an IDE file
                if not isinstance(gta_object, Inst):
                    gta_object.line = f'# removed vanilla object declaration with wrong ID ({gta_object.obj_id}, {gta_object.model})'
                # correct the ID, in case it's an IPL file
                else:
                    gta_object = replace_id(gta_object, vanilla_object_id)
                    
            line_was_corrected = True
            break
    
    if not line_was_corrected:
        # If the object model isn't a vanilla model, give it a new ID
        gta_object = replace_id(gta_object, free_ids[0])
        
    return gta_object

def move_coordinates(gta_object):
    gta_object.line = gta_object.formated_line()
    gta_object.move_coordinates(map_command_x, map_command_y, map_command_z)
    
    return gta_object

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

def get_vanilla_objects(vanilla_objects_file_path):
    lines = read_file(vanilla_objects_file_path)
    global vanilla_objects
    
    for line in lines:
        elements = [element.strip().lower() for element in line.split(',')]
        vanilla_object_id = elements[0]
        vanilla_object_model = elements[1]

        vanilla_objects[vanilla_object_id] = vanilla_object_model
        
    return vanilla_objects
        
def get_ids_in_use():
    if os.path.exists(IDS_IN_USE_FILE_PATH) and os.path.getsize(IDS_IN_USE_FILE_PATH) > 0:
        lines = read_file(IDS_IN_USE_FILE_PATH)
        global ids_in_use
        
        for line in lines:
            line = line.strip()
            
            if line.isdigit():
                ids_in_use.append(int(line))
            elif '-' in line:
                line_parts = line.split('-')
                first_id = int(line_parts[0].strip())
                last_part = line_parts[1].strip()
                
                if any(not char.isdigit() for char in last_part):
                    delimiter = next((char for char in last_part if not char.isdigit()), None)
                    last_id = int(last_part.split(delimiter)[0].strip())
                else:
                    last_id = int(last_part)
                    
                ids_in_use = ids_in_use + list(range(first_id, last_id + 1))
        
    return ids_in_use

def get_free_ids():
    if os.path.exists(FREE_IDS_FILE_PATH) and os.path.getsize(FREE_IDS_FILE_PATH) > 0:
        lines = read_file(FREE_IDS_FILE_PATH)
        global free_ids
        global ids_in_use
        
        for line in lines:
            if line.startswith('Total Free IDs'):
                continue
            
            line = line.strip().rstrip(',')
            
            if line.isdigit():
                free_ids.append(int(line))
            elif '-' in line:
                line_parts = line.split('-')
                first_id = int(line_parts[0].strip())
                last_part = line_parts[1].strip()
                
                if any(not char.isdigit() for char in last_part):
                    delimiter = next((char for char in last_part if not char.isdigit()), None)
                    last_id = int(last_part.split(delimiter)[0].strip())
                else:
                    last_id = int(last_part)
                    
                free_ids = free_ids + list(range(first_id, last_id + 1))
    else:
        free_ids = list(range(1, 65531))
        
    ids_in_use = get_ids_in_use()
    available_ids = [object_id for object_id in free_ids if object_id not in ids_in_use]
    
    return available_ids

def process_file(file_input_path):
    file_name = os.path.basename(file_input_path)
    file_extension = os.path.splitext(file_name)[1][1:].lower()
    lines = read_file(file_input_path)
    modified_lines = modify_lines(lines, file_extension)
    
    return modified_lines

def process_files():
    for file_name in os.listdir(INPUT_DIR):
        file_path = os.path.join(INPUT_DIR, file_name)
        modified_file = process_file(file_path)
        save_modified_file(modified_file, file_path, OUTPUT_DIR)

def save_modified_file(modified_lines, original_filepath, output_dir='modified_files'):
    original_filename = os.path.basename(original_filepath)
    modified_filepath = os.path.join(output_dir, original_filename)
    os.makedirs(output_dir, exist_ok=True)
    
    with open(modified_filepath, 'w', encoding='utf-8') as modified_file:
        modified_file.write('\n'.join(modified_lines))
    
    print(f"Saved {original_filename} at: {modified_filepath}")
    
def save_ids_in_use_file():
    global ids_in_use
    ids_in_use_to_be_saved = [str(id) for id in ids_in_use]
    
    with open(IDS_IN_USE_FILE_PATH, 'w', encoding='utf-8') as ids_in_use_file:
        ids_in_use_file.write('\n'.join(ids_in_use_to_be_saved))
    
    print(f"Updated IDs in use at: {IDS_IN_USE_FILE_PATH}")
#endregion

#region Main
if __name__ == '__main__':
    print("Starting the mod tool debug!")
    
    parser = argparse.ArgumentParser(description = 'GTASA Map Tools')
    parser.add_argument('-id', action='store_true', help='Replace game objects IDs')
    parser.add_argument('-map', nargs = 3, metavar=('X', 'Y', 'Z'), type = float, help = 'Move game objects coordinates')
    args = parser.parse_args()
    id_command = args.id
    map_command = args.map is not None
    map_command_x = args.map[0] if map_command else None
    map_command_y = args.map[1] if map_command else None
    map_command_z = args.map[2] if map_command else None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    vanilla_objects = get_vanilla_objects(VANILLA_OBJECTS_FILE_PATH)
    free_ids = get_free_ids()
    process_files()
    save_ids_in_use_file()
#endregion