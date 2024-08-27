from application.file_types.objects_file import ObjectsFile
from application.data_entry_types.str.data_entry_str import DataEntryStr
from application.data_entry_types.str.dat.water import Water

class Dat(ObjectsFile):
    
    def __init__(self, file_name, file_content):
        super().__init__(file_name, file_content)
        self._section_water = []
        
        self.read_file_sections()
            
    @property
    def section_water(self):
        return self._section_water

    @section_water.setter
    def section_water(self, water_objects):
        if all(isinstance(water_object, Water) for water_object in water_objects):
            self._section_water = water_objects
        else:
            print(f'Called section_water setter but {water_objects} is not a list of Water.')
            
    def add_to_section_water(self, water_object):
        if isinstance(water_object, Water):
            self._section_water.append(water_object)
        else:
            print(f'Called add_to_section_water but {water_object} is not a Water object.')
            
    def read_file_sections(self):
        line_position = -1
        
        for line in self.file_content:
            data_entry = DataEntryStr(line, line_position, None, self)
            
            if data_entry.is_valid_dat_object():
                data_entry.index += 1
                line_position = data_entry.index
                
                if self.is_water_section():
                    gta_object = Water(*data_entry.get_attributes())
                    self.add_to_section_water(gta_object)
                    
    def write_file_sections(self):
        file_content = ''
        
        if self.section_water:
            file_content += 'processed' + '\n'
            for gta_object in self.section_water:
                file_content += gta_object.content + '\n'
            
        self.file_modified_content = file_content
        return self.file_modified_content
    
    def is_water_section(self):
        if self.file_name == 'water.dat':
            return True