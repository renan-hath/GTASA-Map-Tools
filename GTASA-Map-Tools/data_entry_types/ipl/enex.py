from data_entry_types.data_entry import DataEntry

class Enex(DataEntry):
    
    X1_POS_INDEX = 0
    Y1_POS_INDEX = 1
    Z1_POS_INDEX = 2
    X2_POS_INDEX = 7
    Y2_POS_INDEX = 8
    Z2_POS_INDEX = 9
    
    def __init__(self, line, line_position, section, file_name):
        super().__init__(line, line_position, section, file_name)
        elements = super().get_line_elements()
        
        self._x1_pos = float(elements[self.X1_POS_INDEX])
        self._y1_pos = float(elements[self.Y1_POS_INDEX])
        self._z1_pos = float(elements[self.Z1_POS_INDEX])
        self._x2_pos = float(elements[self.X2_POS_INDEX])
        self._y2_pos = float(elements[self.Y2_POS_INDEX])
        self._z2_pos = float(elements[self.Z2_POS_INDEX])

    @property
    def x1_pos(self):
        return self._x1_pos
    
    @x1_pos.setter
    def x1_pos(self, id):
        self._x1_pos = id
        super().update_line_element(str(self._x1_pos), self.X1_POS_INDEX)
    
    @property
    def y1_pos(self):
        return self._y1_pos
    
    @y1_pos.setter
    def y1_pos(self, model):
        self._y1_pos = model
        super().update_line_element(str(self._y1_pos), self.Y1_POS_INDEX)
    
    @property
    def z1_pos(self):
        return self._z1_pos
    
    @z1_pos.setter
    def z1_pos(self, x_pos):
        self._z1_pos = x_pos
        super().update_line_element(str(self._z1_pos), self.Z1_POS_INDEX)
        
    @property
    def x2_pos(self):
        return self._x2_pos
    
    @x2_pos.setter
    def x2_pos(self, y_pos):
        self._x2_pos = y_pos
        super().update_line_element(str(self._x2_pos), self.X2_POS_INDEX)
        
    @property
    def y2_pos(self):
        return self._y2_pos
    
    @y2_pos.setter
    def y2_pos(self, z_pos):
        self._y2_pos = z_pos
        super().update_line_element(str(self._y2_pos), self.Y2_POS_INDEX)
        
    @property
    def z2_pos(self):
        return self._z2_pos
    
    @z2_pos.setter
    def z2_pos(self, x_rot):
        self._z2_pos = x_rot
        super().update_line_element(str(self._z2_pos), self.Z2_POS_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.x1_pos += x
        self.x2_pos += x
        self.y1_pos += y
        self.y2_pos += y
        self.z1_pos += z
        self.z2_pos += z