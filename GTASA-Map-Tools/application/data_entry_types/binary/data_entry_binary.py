import struct
from application.data_entry_types.data_entry import DataEntry

class DataEntryBinary(DataEntry):
    ELEMENT_LENGTH = 4

    def __init__(self, content, index, section, file):
        super().__init__(content, index, section, file)

    def get_content_elements(self):
        elements = [self.content[i:i + self.ELEMENT_LENGTH] for i in range(0, len(self.content), self.ELEMENT_LENGTH)]
        return elements
    
    def update_content_element(self, element, element_type, element_index):
        elements = self.get_content_elements()
        elements[element_index] = struct.pack(element_type, element)
        self._content = b''.join(elements)
        
    def to_int(self, element):
        return struct.unpack('i', element)[0]
    
    def to_float(self, element):
        return round(struct.unpack('f', element)[0], 5)