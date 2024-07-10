from application.file_types.objects_file import ObjectsFile
from application.data_entry_types.binary.ipl.header_binary import HeaderBinary
from application.data_entry_types.binary.ipl.inst_binary import InstBinary
from application.data_entry_types.binary.ipl.cars_binary import CarsBinary

class IplBinary(ObjectsFile):
    SECTIONS = ['header', 'inst', 'cars']
    
    HEADER_INDEX = 0
    HEADER_LENGTH = 76
    HEADER_END = HEADER_LENGTH + HEADER_INDEX
    
    INST_SECTION_INDEX = HEADER_END
    INST_ENTRY_LENGTH = 40
    
    CARS_ENTRY_LENGTH = 48
    
    def __init__(self, file_name, file_content):
        super().__init__(file_name, file_content)
        self.header = HeaderBinary(self.get_section_content(self.HEADER_INDEX, self.HEADER_END), self.HEADER_INDEX, self.SECTIONS[0], self)
        self.inst_section_length = self.INST_ENTRY_LENGTH * self.header.inst_objects_count
        self.inst_section_end = self.INST_SECTION_INDEX + self.inst_section_length
        self.cars_section_index = self.inst_section_end
        self.cars_section_length = self.CARS_ENTRY_LENGTH * self.header.cars_objects_count
        self.cars_section_end = self.cars_section_index + self.cars_section_length
        
        self._section_inst = []
        self._section_cars = []
        
        self.read_file_sections()

    @property
    def section_inst(self):
        return self._section_inst

    @section_inst.setter
    def section_inst(self, inst_binary_list):
        if all(isinstance(inst_binary, InstBinary) for inst_binary in inst_binary_list):
            self._section_inst = inst_binary_list
        else:
            print(f'Called section_inst setter but {inst_binary_list} is not a list of Inst.')
            
    def add_to_section_inst(self, inst_binary_object):
        if isinstance(inst_binary_object, InstBinary):
            self._section_inst.append(inst_binary_object)
        else:
            print(f'Called add_to_section_inst but {inst_binary_object} is not a Inst object.')

    @property
    def section_cars(self):
        return self._section_cars

    @section_cars.setter
    def section_cars(self, cars_binary_list):
        if all(isinstance(cars_binary, CarsBinary) for cars_binary in cars_binary_list):
            self._section_cars = cars_binary_list
        else:
            print(f'Called section_cars setter but {cars_binary_list} is not a list of Cars.')
            
    def add_to_section_cars(self, cars_binary_object):
        if isinstance(cars_binary_object, CarsBinary):
            self._section_cars.append(cars_binary_object)
        else:
            print(f'Called add_to_section_cars but {cars_binary_object} is not a Cars object.')
            
    def get_section_content(self, section_index, section_end):
        return self.file_content[section_index:section_end]
    
    def get_entries_content(self, section_index, section_end, entry_length):
        section_content = self.get_section_content(section_index, section_end)
        return [section_content[i:i + entry_length] for i in range(0, len(section_content), entry_length)]
            
    def read_file_sections(self):
        
        if self.header.inst_objects_count:
            current_section = self.SECTIONS[1]
            inst_entries = self.get_entries_content(self.INST_SECTION_INDEX, self.inst_section_end, self.INST_ENTRY_LENGTH)
            
            for i in range(0, len(inst_entries)):
                gta_object = InstBinary(inst_entries[i], i, current_section, self)
                self.add_to_section_inst(gta_object)
                
        if self.header.cars_objects_count:
            current_section = self.SECTIONS[2]
            cars_entries = self.get_entries_content(self.cars_section_index, self.cars_section_end, self.CARS_ENTRY_LENGTH)
            
            for i in range(0, len(cars_entries)):
                gta_object = CarsBinary(cars_entries[i], i, current_section, self)
                self.add_to_section_cars(gta_object)
                
    def write_file_sections(self):
        file_content = bytearray()
        
        if self.header:
            file_content += self.header.content
        if self.section_inst:
            for gta_object in self.section_inst:
                file_content += gta_object.content
        if self.section_cars:
            for gta_object in self.section_cars:
                file_content += gta_object.content
                
        self.file_modified_content = file_content
        return self.file_modified_content