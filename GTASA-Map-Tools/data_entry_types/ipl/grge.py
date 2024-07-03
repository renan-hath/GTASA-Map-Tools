from data_entry_types.data_entry import DataEntry

class Grge(DataEntry):
    
    X_POS_INDEX = 0
    Y_POS_INDEX = 1
    Z_POS_INDEX = 2
    LINE_X_INDEX = 3
    LINE_Y_INDEX = 4
    CUBE_X_INDEX = 5
    CUBE_Y_INDEX = 6
    CUBE_Z_INDEX = 7
    
    def __init__(self, line):
        super().__init__(line)
        self._x_pos = float(super().get_line_elements()[self.X_POS_INDEX])
        self._y_pos = float(super().get_line_elements()[self.Y_POS_INDEX])
        self._z_pos = float(super().get_line_elements()[self.Z_POS_INDEX])
        self._line_x = float(super().get_line_elements()[self.LINE_X_INDEX])
        self._line_y = float(super().get_line_elements()[self.LINE_Y_INDEX])
        self._cube_x = float(super().get_line_elements()[self.CUBE_X_INDEX])
        self._cube_y = float(super().get_line_elements()[self.CUBE_Y_INDEX])
        self._cube_z = float(super().get_line_elements()[self.CUBE_Z_INDEX])

    @property
    def x_pos(self):
        return self._x_pos
    
    @x_pos.setter
    def x_pos(self, id):
        self._x_pos = id
        super().update_line_element(str(self._x_pos), self.X_POS_INDEX)
    
    @property
    def y_pos(self):
        return self._y_pos
    
    @y_pos.setter
    def y_pos(self, model):
        self._y_pos = model
        super().update_line_element(str(self._y_pos, self.Y_POS_INDEX))
    
    @property
    def z_pos(self):
        return self._z_pos
    
    @z_pos.setter
    def z_pos(self, x_pos):
        self._z_pos = x_pos
        super().update_line_element(str(self._z_pos, self.Z_POS_INDEX))
        
    @property
    def line_x(self):
        return self._line_x
    
    @line_x.setter
    def line_x(self, y_pos):
        self._line_x = y_pos
        super().update_line_element(str(self._line_x, self.LINE_X_INDEX))
        
    @property
    def line_y(self):
        return self._line_y
    
    @line_y.setter
    def line_y(self, z_pos):
        self._line_y = z_pos
        super().update_line_element(str(self._line_y, self.LINE_Y_INDEX))
        
    @property
    def cube_x(self):
        return self._cube_x
    
    @cube_x.setter
    def cube_x(self, x_rot):
        self._cube_x = x_rot
        super().update_line_element(str(self._cube_x, self.CUBE_X_INDEX))
        
    @property
    def cube_y(self):
        return self._cube_y
    
    @cube_y.setter
    def cube_y(self, y_rot):
        self._cube_y = y_rot
        super().update_line_element(str(self._cube_y, self.CUBE_Y_INDEX))
        
    @property
    def cube_z(self):
        return self._cube_z
    
    @cube_z.setter
    def cube_z(self, z_rot):
        self._cube_z = z_rot
        super().update_line_element(str(self._cube_z, self.CUBE_Z_INDEX))