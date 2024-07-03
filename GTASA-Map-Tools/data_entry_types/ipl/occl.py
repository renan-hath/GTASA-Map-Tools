from data_entry_types.data_entry import DataEntry

class Occl(DataEntry):
    
    X_MID_POS_INDEX = 0
    Y_MID_POS_INDEX = 1
    Z_BOTTOM_POS_INDEX = 2
    
    def __init__(self, line):
        super().__init__(line)
        self._x_mid_pos = float(super().get_line_elements()[self.X_MID_POS_INDEX])
        self._y_mid_pos = float(super().get_line_elements()[self.Y_MID_POS_INDEX])
        self._z_bottom_pos = float(super().get_line_elements()[self.Z_BOTTOM_POS_INDEX])
    
    @property
    def x_mid_pos(self):
        return self._x_mid_pos
    
    @x_mid_pos.setter
    def x_mid_pos(self, model):
        self._x_mid_pos = model
        super().update_line_element(str(self._x_mid_pos, self.X_MID_POS_INDEX))
    
    @property
    def y_mid_pos(self):
        return self._y_mid_pos
    
    @y_mid_pos.setter
    def y_mid_pos(self, x_pos):
        self._y_mid_pos = x_pos
        super().update_line_element(str(self._y_mid_pos, self.Y_MID_POS_INDEX))
        
    @property
    def z_bottom_pos(self):
        return self._z_bottom_pos
    
    @z_bottom_pos.setter
    def z_bottom_pos(self, y_pos):
        self._z_bottom_pos = y_pos
        super().update_line_element(str(self._z_bottom_pos, self.Z_BOTTOM_POS_INDEX))