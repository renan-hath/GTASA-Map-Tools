from application.data_entry_types.str.data_entry_str import DataEntryStr

class Hier(DataEntryStr):
    
    ID_INDEX = 0
    MODEL_INDEX = 1
    TEXTURE_INDEX = 2
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        
        self._obj_id = int(elements[self.ID_INDEX])
        self._model = elements[self.MODEL_INDEX]
        self._texture = elements[self.TEXTURE_INDEX]

    @property
    def obj_id(self):
        return self._obj_id
    
    @obj_id.setter
    def obj_id(self, id):
        self._obj_id = id
        super().update_content_element(str(self._obj_id), self.ID_INDEX)
    
    @property
    def model(self):
        return self._model
    
    @model.setter
    def model(self, model):
        self._model = model
        super().update_content_element(self._model, self.MODEL_INDEX)
    
    @property
    def texture(self):
        return self._texture
    
    @texture.setter
    def texture(self, texture):
        self._texture = texture
        super().update_content_element(self._texture, self.TEXTURE_INDEX)