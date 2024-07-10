from application.data_entry_types.str.data_entry_str import DataEntryStr

class Grge(DataEntryStr):
    
    X_POS_INDEX = 0
    Y_POS_INDEX = 1
    Z_POS_INDEX = 2
    LINE_X_INDEX = 3
    LINE_Y_INDEX = 4
    CUBE_X_INDEX = 5
    CUBE_Y_INDEX = 6
    CUBE_Z_INDEX = 7
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        
        self._x_pos = float(elements[self.X_POS_INDEX])
        self._y_pos = float(elements[self.Y_POS_INDEX])
        self._z_pos = float(elements[self.Z_POS_INDEX])
        self._line_x = float(elements[self.LINE_X_INDEX])
        self._line_y = float(elements[self.LINE_Y_INDEX])
        self._cube_x = float(elements[self.CUBE_X_INDEX])
        self._cube_y = float(elements[self.CUBE_Y_INDEX])
        self._cube_z = float(elements[self.CUBE_Z_INDEX])
        

    @property
    def x_pos(self):
        return self._x_pos
    
    @x_pos.setter
    def x_pos(self, x_pos):
        self._x_pos = x_pos
        super().update_content_element(str(self._x_pos), self.X_POS_INDEX)
    
    @property
    def y_pos(self):
        return self._y_pos
    
    @y_pos.setter
    def y_pos(self, y_pos):
        self._y_pos = y_pos
        super().update_content_element(str(self._y_pos), self.Y_POS_INDEX)
    
    @property
    def z_pos(self):
        return self._z_pos
    
    @z_pos.setter
    def z_pos(self, z_pos):
        self._z_pos = z_pos
        super().update_content_element(str(self._z_pos), self.Z_POS_INDEX)
        
    @property
    def line_x(self):
        return self._line_x
    
    @line_x.setter
    def line_x(self, line_x):
        self._line_x = line_x
        super().update_content_element(str(self._line_x), self.LINE_X_INDEX)
        
    @property
    def line_y(self):
        return self._line_y
    
    @line_y.setter
    def line_y(self, line_y):
        self._line_y = line_y
        super().update_content_element(str(self._line_y), self.LINE_Y_INDEX)
        
    @property
    def cube_x(self):
        return self._cube_x
    
    @cube_x.setter
    def cube_x(self, cube_x):
        self._cube_x = cube_x
        super().update_content_element(str(self._cube_x), self.CUBE_X_INDEX)
        
    @property
    def cube_y(self):
        return self._cube_y
    
    @cube_y.setter
    def cube_y(self, cube_y):
        self._cube_y = cube_y
        super().update_content_element(str(self._cube_y), self.CUBE_Y_INDEX)
        
    @property
    def cube_z(self):
        return self._cube_z
    
    @cube_z.setter
    def cube_z(self, cube_z):
        self._cube_z = cube_z
        super().update_content_element(str(self._cube_z), self.CUBE_Z_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.x_pos += x
        self.line_x += x
        self.cube_x += x
        self.y_pos += y
        self.line_y += y
        self.cube_y += y
        self.z_pos += z
        self.cube_z += z