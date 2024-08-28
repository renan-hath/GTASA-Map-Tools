from application.data_entry_types.str.data_entry_str import DataEntryStr

class DatObject(DataEntryStr):
    
    MODEL_INDEX = 0
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        self.elements = elements
        
        self._model = elements[self.MODEL_INDEX]

    @property
    def model(self):
        return self._model
    
    @model.setter
    def model(self, model):
        self._model = model
        super().update_content_element(self._model, self.MODEL_INDEX)