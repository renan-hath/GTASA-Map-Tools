from data_entry_types.data_entry import DataEntry

class Anim(DataEntry):
    
    ID_INDEX = 0
    MODEL_INDEX = 1
    TEXTURE_INDEX = 2
    
    def __init__(self, line):
        super().__init__(line)
        self._obj_id = int(super().get_line_elements()[self.ID_INDEX])
        self._model = super().get_line_elements()[self.MODEL_INDEX]
        self._texture = super().get_line_elements()[self.TEXTURE_INDEX]
        self._line = super().formated_line()

    @property
    def obj_id(self):
        return self._obj_id
    
    @obj_id.setter
    def obj_id(self, id):
        self._obj_id = id
        super().update_line_element(str(self._obj_id), self.ID_INDEX)
    
    @property
    def model(self):
        return self._model
    
    @model.setter
    def model(self, model):
        self._model = model
        super().update_line_element(self._model, self.MODEL_INDEX)
    
    @property
    def texture(self):
        return self._texture
    
    @texture.setter
    def texture(self, texture):
        self._texture = texture
        super().update_line_element(self._texture, self.TEXTURE_INDEX)