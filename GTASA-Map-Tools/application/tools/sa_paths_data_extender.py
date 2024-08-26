import subprocess
import os

class SAPathsDataExtender:
    
    RESOURCES_DIR = "resources"
    SA_PATHS_DATA_EXTENDER_DIR = os.path.join(RESOURCES_DIR, "SAPathsDataExtender")
    SA_PATHS_DATA_EXTENDER_NAME = "sa-pathsdata-extender.exe"
    SA_PATHS_DATA_EXTENDER_PATH = os.path.abspath(os.path.join(SA_PATHS_DATA_EXTENDER_DIR, SA_PATHS_DATA_EXTENDER_NAME))
    SA_PATHS_DATA_EXTENDER_INPUT_DIR = os.path.abspath(os.path.join(SA_PATHS_DATA_EXTENDER_DIR, "Input"))
    SA_PATHS_DATA_EXTENDER_OUTPUT_DIR = os.path.abspath(os.path.join(SA_PATHS_DATA_EXTENDER_DIR, "Output"))
    TILE_SIZE = 750

    def __init__(self):
        pass

    def run(self, map_command_x, map_command_y, map_command_z):
        x_tile_offset = str(round(map_command_x / self.TILE_SIZE))
        y_tile_offset = str(round(map_command_y / self.TILE_SIZE))
        z_tile_offset = str(map_command_z)
        
        args = ['--source-path-nodes', self.SA_PATHS_DATA_EXTENDER_INPUT_DIR, 
                '--output-path-nodes', self.SA_PATHS_DATA_EXTENDER_OUTPUT_DIR,
                '--x-tile-offset', x_tile_offset, '--y-tile-offset', y_tile_offset, 
                '--z-unit-offset', z_tile_offset]
        
        command = [self.SA_PATHS_DATA_EXTENDER_PATH] + list(args)
        
        print(f"SA Paths Data Extender command: {' '.join(command)}")

        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if 'Copying successful' in result.stdout:
                return True
            else:
                print(f"Error while executing SA Paths Data Extender: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error while executing SA Paths Data Extender: {e}")
            return False