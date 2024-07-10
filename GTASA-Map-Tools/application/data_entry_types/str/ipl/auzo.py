from application.data_entry_types.str.data_entry_str import DataEntryStr

class Auzo(DataEntryStr):
    
    X1_POS_INDEX = 3
    Y1_POS_INDEX = 4
    Z1_POS_INDEX = 5
    X2_POS_INDEX = 6
    Y2_POS_INDEX = 7
    Z2_POS_INDEX = 8
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        
        self._x1_pos = float(elements[self.X1_POS_INDEX])
        self._y1_pos = float(elements[self.Y1_POS_INDEX])
        self._z1_pos = float(elements[self.Z1_POS_INDEX])
        
        if (elements.len() > 7):
            self._x2_pos = float(elements[self.X2_POS_INDEX])
            self._y2_pos = float(elements[self.Y2_POS_INDEX])
            self._z2_pos = float(elements[self.Z2_POS_INDEX])
        else:
            self._x2_pos = None
            self._y2_pos = None
            self._z2_pos = None

    @property
    def x1_pos(self):
        return self._x1_pos
    
    @x1_pos.setter
    def x1_pos(self, x1_pos):
        self._x1_pos = x1_pos
        super().update_content_element(str(self._x1_pos), self.X1_POS_INDEX)
    
    @property
    def y1_pos(self):
        return self._y1_pos
    
    @y1_pos.setter
    def y1_pos(self, y1_pos):
        self._y1_pos = y1_pos
        super().update_content_element(str(self._y1_pos), self.Y1_POS_INDEX)
    
    @property
    def z1_pos(self):
        return self._z1_pos
    
    @z1_pos.setter
    def z1_pos(self, z1_pos):
        self._z1_pos = z1_pos
        super().update_content_element(str(self._z1_pos), self.Z1_POS_INDEX)
        
    @property
    def x2_pos(self):
        return self._x2_pos
    
    @x2_pos.setter
    def x2_pos(self, x2_pos):
        self._x2_pos = x2_pos
        super().update_content_element(str(self._x2_pos), self.X2_POS_INDEX)
        
    @property
    def y2_pos(self):
        return self._y2_pos
    
    @y2_pos.setter
    def y2_pos(self, y2_pos):
        self._y2_pos = y2_pos
        super().update_content_element(str(self._y2_pos), self.Y2_POS_INDEX)
        
    @property
    def z2_pos(self):
        return self._z2_pos
    
    @z2_pos.setter
    def z2_pos(self, z2_pos):
        self._z2_pos = z2_pos
        super().update_content_element(str(self._z2_pos), self.Z2_POS_INDEX)
        
    def move_coordinates(self, x, y, z):
        elements = super().get_content_elements()
        
        self.x1_pos += x
        self.y1_pos += y
        self.z1_pos += z
        
        if (elements.len() > 7):
            self.x2_pos += x
            self.y2_pos += y
            self.z2_pos += z