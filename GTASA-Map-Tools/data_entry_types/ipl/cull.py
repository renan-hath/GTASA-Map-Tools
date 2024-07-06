from data_entry_types.data_entry import DataEntry

class Cull(DataEntry):
    
    CENTER_X_INDEX = 0
    CENTER_Y_INDEX = 1
    CENTER_Z_INDEX = 2
    BOTTOM_Z_INDEX = 5
    
    def __init__(self, line, line_position, section, file_name):
        super().__init__(line, line_position, section, file_name)
        elements = super().get_line_elements()
        
        self._center_x = float(elements[self.CENTER_X_INDEX])
        self._center_y = float(elements[self.CENTER_Y_INDEX])
        self._center_z = float(elements[self.CENTER_Z_INDEX])
        self._bottom_z = float(elements[self.BOTTOM_Z_INDEX])

    @property
    def center_x(self):
        return self._center_x
    
    @center_x.setter
    def center_x(self, id):
        self._center_x = id
        super().update_line_element(str(self._center_x), self.CENTER_X_INDEX)
    
    @property
    def center_y(self):
        return self._center_y
    
    @center_y.setter
    def center_y(self, model):
        self._center_y = model
        super().update_line_element(str(self._center_y), self.CENTER_Y_INDEX)
    
    @property
    def center_z(self):
        return self._center_z
    
    @center_z.setter
    def center_z(self, x_pos):
        self._center_z = x_pos
        super().update_line_element(str(self._center_z), self.CENTER_Z_INDEX)
        
    @property
    def bottom_z(self):
        return self._bottom_z
    
    @bottom_z.setter
    def bottom_z(self, y_pos):
        self._bottom_z = y_pos
        super().update_line_element(str(self._bottom_z), self.BOTTOM_Z_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.center_x += x
        self.center_y += y
        self.center_z += z
        self.bottom_z += z