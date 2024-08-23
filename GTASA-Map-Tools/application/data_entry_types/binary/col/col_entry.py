import struct
from application.data_entry_types.binary.data_entry_binary import DataEntryBinary

class ColEntry(DataEntryBinary):
    
    INTRO_INDEX = 0
    MODEL_NAME_INDEX = 1
    MODEL_DATA_INDEX = 2
    
    def __init__(self, content, index, section, file):
        super().__init__(content, index, section, file)
        
        elements = self.get_content_elements()

        self._model = super().to_str(elements[self.MODEL_NAME_INDEX].split(b'\x00')[0])

    @property
    def model(self):
        return self._model
    
    @model.setter
    def model(self, model):
        self._model = model
        self.update_model(self._model)

    def update_model(self, model):
        elements = self.get_content_elements()
        
        if isinstance(model, str):
            element_type = f'{len(model)}s'
            model = model.encode('ascii')
        
        model_padded = struct.pack(element_type, model) + b'\x00' * (20 - len(model))

        elements[self.MODEL_NAME_INDEX] = model_padded
        self._content = b''.join(elements)

    def get_content_elements(self):
        elements = []

        # First element: 8 first bytes
        elements.append(self.content[:8])

        # Second element (name): 20 next bytes
        elements.append(self.content[8:28])

        # Third element (content): next bytes until 'COL' or the end of the file
        col_index = self.content.find(b'COL', 28)
        if col_index != -1:
            elements.append(self.content[28:col_index])
        else:
            elements.append(self.content[28:])

        return elements