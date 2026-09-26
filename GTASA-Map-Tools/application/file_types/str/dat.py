from application.file_types.objects_file import ObjectsFile
from application.data_entry_types.str.data_entry_str import DataEntryStr
from application.data_entry_types.str.dat.water import Water
from application.data_entry_types.str.dat.dat_object import DatObject
from application.data_entry_types.str.dat.tracks import Tracks

class Dat(ObjectsFile):
    
    def __init__(self, file_name, file_content):
        super().__init__(file_name, file_content)
        self._section_water = []
        self._section_datobj = []
        self._section_tracks = []
        
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
            
    @property
    def section_datobj(self):
        return self._section_datobj

    @section_datobj.setter
    def section_datobj(self, datobj_objects):
        if all(isinstance(datobj_object, DatObject) for datobj_object in datobj_objects):
            self._section_datobj = datobj_objects
        else:
            print(f'Called section_datobj setter but {datobj_objects} is not a list of DatObject.')
            
    def add_to_section_datobj(self, datobj_object):
        if isinstance(datobj_object, DatObject):
            self._section_datobj.append(datobj_object)
        else:
            print(f'Called add_to_section_datobj but {datobj_object} is not a DatObject object.')
            
    @property
    def section_tracks(self):
        return self._section_tracks

    @section_tracks.setter
    def section_tracks(self, tracks_objects):
        if all(isinstance(tracks_object, Tracks) for tracks_object in tracks_objects):
            self._section_tracks = tracks_objects
        else:
            print(f'Called section_tracks setter but {tracks_objects} is not a list of Tracks.')
            
    def add_to_section_tracks(self, tracks_object):
        if isinstance(tracks_object, Tracks):
            self._section_tracks.append(tracks_object)
        else:
            print(f'Called add_to_section_tracks but {tracks_object} is not a Tracks object.')
            
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
                elif self.is_datobj_section():
                    gta_object = DatObject(*data_entry.get_attributes())
                    self.add_to_section_datobj(gta_object)
                elif self.is_tracks_section():
                    gta_object = Tracks(*data_entry.get_attributes())
                    self.add_to_section_tracks(gta_object)
                    
    def write_file_sections(self):
        file_content = ''
        
        if self.section_water:
            file_content += 'processed' + '\n'
            for gta_object in self.section_water:
                file_content += gta_object.content + '\n'
        elif self.section_datobj:
            for gta_object in self.section_datobj:
                file_content += gta_object.content + '\n'
        elif self.section_tracks:
            file_content += str(len(self.section_tracks)) + '\n'
            for gta_object in self.section_tracks:
                file_content += gta_object.content + '\n'
            
        self.file_modified_content = file_content
        return self.file_modified_content
    
    def is_water_section(self):
        if self.file_name == 'water.dat':
            return True
        
    def is_datobj_section(self):
        if self.file_name == 'object.dat':
            return True
    
    def is_tracks_section(self):
        if (self.file_name.lower() == 'tracks.dat' or
            (self.file_name.lower().startswith('tracks') and
             self.file_name.lower().endswith('.dat') and
             self.file_name.lower()[6:-4].isdigit())):
            return True