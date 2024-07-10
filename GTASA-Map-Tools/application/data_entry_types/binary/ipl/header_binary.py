from application.data_entry_types.binary.data_entry_binary import DataEntryBinary

class HeaderBinary(DataEntryBinary):
    
    INST_OBJECTS_COUNT_INDEX = 1
    CARS_OBJECTS_COUNT_INDEX = 5
    
    def __init__(self, content, index, section, file):
        super().__init__(content, index, section, file)
        elements = super().get_content_elements()
        
        self._inst_objects_count = super().to_int(elements[self.INST_OBJECTS_COUNT_INDEX])
        self._cars_objects_count = super().to_int(elements[self.CARS_OBJECTS_COUNT_INDEX])

    @property
    def inst_objects_count(self):
        return self._inst_objects_count
    
    @inst_objects_count.setter
    def inst_objects_count(self, inst_objects_count):
        self._inst_objects_count = inst_objects_count
        super().update_content_element(self._inst_objects_count, 'i', self.INST_OBJECTS_COUNT_INDEX)
    
    @property
    def cars_objects_count(self):
        return self._cars_objects_count
    
    @cars_objects_count.setter
    def cars_objects_count(self, cars_objects_count):
        self._cars_objects_count = cars_objects_count
        super().update_content_element(self._cars_objects_count, 'i', self.CARS_OBJECTS_COUNT_INDEX)