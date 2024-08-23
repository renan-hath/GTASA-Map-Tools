from application.data_entry_types.str.data_entry_str import DataEntryStr

class Txdp(DataEntryStr):
    
    TEXTURE_INDEX = 0
    TEXTURE_PARENT_INDEX = 1
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        
        self._texture = elements[self.TEXTURE_INDEX]
        self._texture_parent = elements[self.TEXTURE_PARENT_INDEX]

    @property
    def texture(self):
        return self._texture
    
    @texture.setter
    def texture(self, texture):
        self._texture = texture
        super().update_content_element(self._texture, self.TEXTURE_INDEX)
    
    @property
    def texture_parent(self):
        return self._texture_parent
    
    @texture_parent.setter
    def texture_parent(self, texture_parent):
        self._texture_parent = texture_parent
        super().update_content_element(self._texture_parent, self.TEXTURE_PARENT_INDEX)