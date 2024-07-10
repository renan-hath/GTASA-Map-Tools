from application.data_entry_types.str.data_entry_str import DataEntryStr

class Occl(DataEntryStr):
    
    X_MID_POS_INDEX = 0
    Y_MID_POS_INDEX = 1
    Z_BOTTOM_POS_INDEX = 2
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        
        self._x_mid_pos = float(elements[self.X_MID_POS_INDEX])
        self._y_mid_pos = float(elements[self.Y_MID_POS_INDEX])
        self._z_bottom_pos = float(elements[self.Z_BOTTOM_POS_INDEX])
    
    @property
    def x_mid_pos(self):
        return self._x_mid_pos
    
    @x_mid_pos.setter
    def x_mid_pos(self, x_mid_pos):
        self._x_mid_pos = x_mid_pos
        super().update_content_element(str(self._x_mid_pos), self.X_MID_POS_INDEX)
    
    @property
    def y_mid_pos(self):
        return self._y_mid_pos
    
    @y_mid_pos.setter
    def y_mid_pos(self, y_mid_pos):
        self._y_mid_pos = y_mid_pos
        super().update_content_element(str(self._y_mid_pos), self.Y_MID_POS_INDEX)
        
    @property
    def z_bottom_pos(self):
        return self._z_bottom_pos
    
    @z_bottom_pos.setter
    def z_bottom_pos(self, z_bottom_pos):
        self._z_bottom_pos = z_bottom_pos
        super().update_content_element(str(self._z_bottom_pos), self.Z_BOTTOM_POS_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.x_mid_pos += x
        self.y_mid_pos += y
        self.z_bottom_pos += z