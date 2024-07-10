import argparse
import os
import chardet
from itertools import chain
from application.file_types.str.ide import Ide
from application.file_types.str.ipl import Ipl
from application.file_types.binary.ipl_binary import IplBinary
from application.data_entry_types.str.ide.anim import Anim
from application.data_entry_types.str.ide.objs import Objs
from application.data_entry_types.str.ide.tobj import Tobj

#region Constants
INPUT_DIR = "files"
OUTPUT_DIR = "modified_files"
BINARY_OUTPUT_DIR = OUTPUT_DIR + "\\" + "ipl_stream"
RESOURCES_DIR = "resources"
VANILLA_OBJECTS_FILE_NAME = "vanilla_objects.txt"
VANILLA_OBJECTS_FILE_PATH = os.path.join(RESOURCES_DIR, VANILLA_OBJECTS_FILE_NAME)
FREE_IDS_FILE_NAME = "Free IDs List.txt"
FREE_IDS_FILE_PATH = os.path.join(RESOURCES_DIR, FREE_IDS_FILE_NAME)
IDS_IN_USE_FILE_NAME = "ids_in_use.txt"
IDS_IN_USE_FILE_PATH = os.path.join(RESOURCES_DIR, IDS_IN_USE_FILE_NAME)
IDE_FILE_EXTENSION = 'ide'
IPL_FILE_EXTENSION = 'ipl'
SUPPORTED_FILE_EXTENSIONS = [IDE_FILE_EXTENSION, IPL_FILE_EXTENSION]
#endregion

#region Global variables
fix_command = False
id_command = False
map_command = False
map_command_x = 0
map_command_y = 0
map_command_z = 0

files = []
vanilla_objects = {}
free_ids = []

ids_in_use = []
replaced_ids = {}

ide_objects = []
inst_objects = []
inst_binary_objects = []
inst_total_objects = []
coordinate_objects = []

def get_vanilla_objects():
    global vanilla_objects
    
    file_encoding = detect_file_encoding(VANILLA_OBJECTS_FILE_PATH)
    file_content = read_file(VANILLA_OBJECTS_FILE_PATH, file_encoding)
    
    for line in file_content:
        elements = [element.strip().lower() for element in line.split(',')]
        vanilla_object_id = int(elements[0])
        vanilla_object_model = elements[1]

        vanilla_objects[vanilla_object_id] = vanilla_object_model

def get_free_ids():
    global ids_in_use
    global free_ids
    
    if os.path.exists(FREE_IDS_FILE_PATH) and os.path.getsize(FREE_IDS_FILE_PATH) > 0:
        
        file_encoding = detect_file_encoding(FREE_IDS_FILE_PATH)
        file_content = read_file(FREE_IDS_FILE_PATH, file_encoding)
        
        for line in file_content:
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
    free_ids = [object_id for object_id in free_ids if object_id not in ids_in_use]

def get_ids_in_use():
    global ids_in_use
    
    if os.path.exists(IDS_IN_USE_FILE_PATH) and os.path.getsize(IDS_IN_USE_FILE_PATH) > 0:
        
        file_encoding = detect_file_encoding(IDS_IN_USE_FILE_PATH)
        file_content = read_file(IDS_IN_USE_FILE_PATH, file_encoding)
        
        for line in file_content:
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

def process_files():
    read_files()
    list_objects_to_modify()
    modify_files()
    write_files()

def read_files():
    global files
    
    for file_name in os.listdir(INPUT_DIR):
        file_extension = os.path.splitext(file_name)[1][1:].lower()
        
        if file_extension in SUPPORTED_FILE_EXTENSIONS:
            file_path = os.path.join(INPUT_DIR, file_name)
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
                    
            files.append(file)
            
def detect_file_encoding(file_path):
    with open(file_path, 'rb') as f:
        if f.read(4) == b"bnry":
            return 'binary'
        else:
            f.seek(0)
            result = chardet.detect(f.read())
            return result['encoding']

def read_file(file_path, encoding):
    
    if encoding == 'binary':
        with open(file_path, 'rb') as f:
            return bytearray(f.read())
    else:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.readlines()

def list_objects_to_modify():
    global ide_objects
    global inst_objects
    global inst_binary_objects
    global inst_total_objects
    global coordinate_objects
    
    ide_objects = []
    inst_objects = []
    inst_binary_objects = []
    inst_total_objects = []
    coordinate_objects = []
    
    for file in files:
        if isinstance(file, Ide):
            if file.section_objs:
                ide_objects.extend(file.section_objs)
            if file.section_tobj:
                ide_objects.extend(file.section_tobj)
            if file.section_anim:
                ide_objects.extend(file.section_anim)
        elif isinstance(file, Ipl):
            if file.section_inst:
                inst_objects.extend(file.section_inst)
                coordinate_objects.extend(file.section_inst)
            if file.section_auzo:
                coordinate_objects.extend(file.section_auzo)
            if file.section_cars:
                coordinate_objects.extend(file.section_cars)
            if file.section_cull:
                coordinate_objects.extend(file.section_cull)
            if file.section_enex:
                coordinate_objects.extend(file.section_enex)
            if file.section_grge:
                coordinate_objects.extend(file.section_grge)
            if file.section_jump:
                coordinate_objects.extend(file.section_jump)
            if file.section_occl:
                coordinate_objects.extend(file.section_occl)
            if file.section_pick:
                coordinate_objects.extend(file.section_pick)
            if file.section_tcyc:
                coordinate_objects.extend(file.section_tcyc)
        elif isinstance(file, IplBinary):
            if file.section_inst:
                inst_binary_objects.extend(file.section_inst)
                coordinate_objects.extend(file.section_inst)
            if file.section_cars:
                coordinate_objects.extend(file.section_cars)
                
    inst_total_objects = inst_objects + inst_binary_objects

def modify_files():
    global fix_command
    global id_command
    global map_command
    
    if fix_command:
        remove_unreferenced_objects()
    if id_command:
        update_ids()
    if map_command:
        modify_coordinates()

    return

def remove_unreferenced_objects():
    global files
    global ide_objects
    global inst_objects
    global inst_binary_objects
    
    correct_inst_binary_models()
    vanilla_ids = set(vanilla_objects.keys())
    
    # Identify undeclared IPL and IPL Binary objects
    ide_ids = {gta_object.obj_id for gta_object in ide_objects}
    
    for inst_object in chain(inst_objects, inst_binary_objects):
        if inst_object.obj_id not in ide_ids and inst_object.obj_id not in vanilla_ids:
            print(f"({inst_object.file_name}) [{inst_object.obj_id},{inst_object.model}] not found in any IDE or in vanilla objects")
        elif inst_object.obj_id not in ide_ids and inst_object.obj_id in vanilla_ids and inst_object.model.lower() != vanilla_objects[inst_object.obj_id].lower():
            print(f"Different model used: ({inst_object.file_name}) [{inst_object.obj_id},{inst_object.model}] x [{inst_object.obj_id},{vanilla_objects[inst_object.obj_id]}] (Vanilla)")

    undeclared_inst_objects = [gta_object for gta_object in inst_objects if gta_object.obj_id not in ide_ids and gta_object.obj_id not in vanilla_ids]
    undeclared_inst_binary_objects = [gta_object for gta_object in inst_binary_objects if gta_object.obj_id not in ide_ids and gta_object.obj_id not in vanilla_ids]
    total_undeclared_inst_objects = undeclared_inst_objects + undeclared_inst_binary_objects

    if total_undeclared_inst_objects:
        for undeclared_inst_object in total_undeclared_inst_objects:
            file = undeclared_inst_object.file
            if isinstance(file, Ipl):
                file.remove_from_section_inst(undeclared_inst_object)
                inst_objects.remove(undeclared_inst_object)
            elif isinstance(file, IplBinary):
                file.section_inst.remove(undeclared_inst_object)
                inst_binary_objects.remove(undeclared_inst_object)

    # Identify unused IDE objects
    total_inst_ids = {gta_object.obj_id for gta_object in inst_objects} | {gta_object.obj_id for gta_object in inst_binary_objects}
    
    for ide_object in ide_objects:
        if ide_object.obj_id not in total_inst_ids and ide_object.obj_id not in vanilla_ids:
            print(f"({ide_object.file_name}) [{ide_object.obj_id},{ide_object.model}] not found in any IPL or in vanilla objects")
        elif ide_object.obj_id not in total_inst_ids and ide_object.obj_id in vanilla_ids and ide_object.model.lower() != vanilla_objects[ide_object.obj_id].lower():
            print(f"Different model used: ({ide_object.file_name}) [{ide_object.obj_id},{ide_object.model}] x [{ide_object.obj_id},{vanilla_objects[ide_object.obj_id]}] (Vanilla)")
    
    unused_ide_objects = [gta_object for gta_object in ide_objects if gta_object.obj_id not in total_inst_ids]
    
    if unused_ide_objects:
        for unused_ide_object in unused_ide_objects:
            file = unused_ide_object.file
            if isinstance(unused_ide_object, Objs):
                file.section_objs.remove(unused_ide_object)
            elif isinstance(unused_ide_object, Tobj):
                file.section_tobj.remove(unused_ide_object)
            elif isinstance(unused_ide_object, Anim):
                file.section_anim.remove(unused_ide_object)
                
def correct_inst_binary_models():
    global vanilla_objects
    global ide_objects
    global inst_binary_objects
    
    ide_ids_to_models = {gta_object.obj_id: gta_object.model for gta_object in ide_objects}
    
    for inst_binary_object in inst_binary_objects:
        if inst_binary_object.obj_id in ide_ids_to_models:
            inst_binary_object.model = ide_ids_to_models[inst_binary_object.obj_id]
        elif inst_binary_object.obj_id in vanilla_objects:
            inst_binary_object.model = vanilla_objects[inst_binary_object.obj_id]

def update_ids():
    global vanilla_objects
    global free_ids
    global ide_objects
    global inst_total_objects
    
    list_objects_to_modify()
    vanilla_models = set(vanilla_objects.values())
    
    for gta_object in ide_objects:
        found_match = False
        
        if gta_object.model in vanilla_models:
            print(f"({gta_object.file_name}) {gta_object.obj_id},{gta_object.model} is a vanilla object - Removing IDE declaration...")
            file = gta_object.file
            if isinstance(gta_object, Objs):
                file.section_objs.remove(gta_object)
            elif isinstance(gta_object, Tobj):
                file.section_tobj.remove(gta_object)
            elif isinstance(gta_object, Anim):
                file.section_anim.remove(gta_object)
        else:
            print(f"({gta_object.file_name}) Giving new ID for {gta_object.obj_id},{gta_object.model}: ", end = '')
            replace_id(gta_object, free_ids[0])
            print(f"{gta_object.obj_id}")
    
    list_objects_to_modify()
    ide_models = [gta_object.model for gta_object in ide_objects]
                
    for gta_object in inst_total_objects:
        found_match = False
        
        for vanilla_obj_id, vanilla_model in vanilla_objects.items():
            if (vanilla_obj_id == gta_object.obj_id and 
                # 1,chair == 1,chair --> Keep it
                ((vanilla_model.lower() == gta_object.model.lower()) or
                 # 1,redchair == 1,chair when it has a vanilla substring and is not IDE declared --> Keep it
                (vanilla_model.lower() in gta_object.model.lower() and gta_object.model.lower() not in ide_models))):
                found_match = True
                break
            # 500,chair == 1,chair --> Get vanilla ID
            elif (vanilla_model.lower() == gta_object.model.lower() and vanilla_obj_id != gta_object.obj_id):
                print(f"({gta_object.file_name}) {gta_object.obj_id},{gta_object.model} is a vanilla object - Correcting ID to {vanilla_obj_id}...")
                replace_id(gta_object, vanilla_obj_id)
                found_match = True
                break
            
        # Get new ID:
        # 1,table      != 1,chair
        # 500,table    != 1,chair
        # 500,redchair != 1,chair
        # 1,redchair   != 1,chair if it's IDE declared
        if not found_match:
            print(f"({gta_object.file_name}) Giving new ID for {gta_object.obj_id},{gta_object.model}: ", end = '')
            replace_id(gta_object, free_ids[0])
            print(f"{gta_object.obj_id}")

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

def write_files():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for file in files:
        original_filename = file.file_name
        
        if isinstance(file, IplBinary):
            os.makedirs(BINARY_OUTPUT_DIR, exist_ok=True)
            modified_filepath = os.path.join(BINARY_OUTPUT_DIR, original_filename)
            
            with open(modified_filepath, 'wb') as modified_file:
                modified_file.write(file.write_file_sections())
        else:
            modified_filepath = os.path.join(OUTPUT_DIR, original_filename)
            
            with open(modified_filepath, 'w', encoding='utf-8') as modified_file:
                modified_file.write(file.write_file_sections())
                
        print(f"Saved {original_filename} at: {modified_filepath}")

def save_ids_in_use_file():
    global ids_in_use
    ids_in_use_to_be_saved = [str(id) for id in ids_in_use]
    
    with open(IDS_IN_USE_FILE_PATH, 'w', encoding='utf-8') as ids_in_use_file:
        ids_in_use_file.write('\n'.join(ids_in_use_to_be_saved))
    
    print(f"Updated IDs in use at: {IDS_IN_USE_FILE_PATH}")


#region Main
if __name__ == '__main__':
    print("Starting the mod tool debug!")
    
    parser = argparse.ArgumentParser(description = 'GTASA Map Tools')
    parser.add_argument('-fix', action='store_true', help='Remove unused game objects')
    parser.add_argument('-id', action='store_true', help='Replace game objects IDs')
    parser.add_argument('-map', nargs = 3, metavar=('X', 'Y', 'Z'), type = float, help = 'Move game objects coordinates')
    args = parser.parse_args()
    fix_command = args.fix
    id_command = args.id
    map_command = args.map is not None
    map_command_x = args.map[0] if map_command else None
    map_command_y = args.map[1] if map_command else None
    map_command_z = args.map[2] if map_command else None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    get_vanilla_objects()
    get_free_ids()
    process_files()
    save_ids_in_use_file()
    print('Finished processing files!')
#endregion