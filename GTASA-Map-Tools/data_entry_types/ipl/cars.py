from data_entry_types.data_entry import DataEntry

class Cars(DataEntry):
    
    X_POS_INDEX = 0
    Y_POS_INDEX = 1
    Z_POS_INDEX = 2
    
    def __init__(self, line, line_position, section, file_name):
        super().__init__(line, line_position, section, file_name)
        elements = super().get_line_elements()
        
        self._x_pos = float(elements[self.X_POS_INDEX])
        self._y_pos = float(elements[self.Y_POS_INDEX])
        self._z_pos = float(elements[self.Z_POS_INDEX])
    
    @property
    def x_pos(self):
        return self._x_pos
    
    @x_pos.setter
    def x_pos(self, model):
        self._x_pos = model
        super().update_line_element(str(self._x_pos), self.X_POS_INDEX)
    
    @property
    def y_pos(self):
        return self._y_pos
    
    @y_pos.setter
    def y_pos(self, x_pos):
        self._y_pos = x_pos
        super().update_line_element(str(self._y_pos), self.Y_POS_INDEX)
        
    @property
    def z_pos(self):
        return self._z_pos
    
    @z_pos.setter
    def z_pos(self, y_pos):
        self._z_pos = y_pos
        super().update_line_element(str(self._z_pos), self.Z_POS_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.x_pos += x
        self.y_pos += y
        self.z_pos += z