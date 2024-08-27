from application.data_entry_types.str.data_entry_str import DataEntryStr

class Water(DataEntryStr):
    
    POINT_1_X_INDEX = 0
    POINT_1_Y_INDEX = 1
    POINT_1_Z_INDEX = 2

    POINT_2_X_INDEX = 7
    POINT_2_Y_INDEX = 8
    POINT_2_Z_INDEX = 9

    POINT_3_X_INDEX = 14
    POINT_3_Y_INDEX = 15
    POINT_3_Z_INDEX = 16
    
    POINT_4_X_INDEX = 21
    POINT_4_Y_INDEX = 22
    POINT_4_Z_INDEX = 23
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        self.elements = elements
        
        self._point_1_x = float(elements[self.POINT_1_X_INDEX])
        self._point_1_y = float(elements[self.POINT_1_Y_INDEX])
        self._point_1_z = float(elements[self.POINT_1_Z_INDEX])
        self._point_2_x = float(elements[self.POINT_2_X_INDEX])
        self._point_2_y = float(elements[self.POINT_2_Y_INDEX])
        self._point_2_z = float(elements[self.POINT_2_Z_INDEX])
        self._point_3_x = float(elements[self.POINT_3_X_INDEX])
        self._point_3_y = float(elements[self.POINT_3_Y_INDEX])
        self._point_3_z = float(elements[self.POINT_3_Z_INDEX])
        
        if len(elements) == 29:
            self._point_4_x = float(elements[self.POINT_4_X_INDEX])
            self._point_4_y = float(elements[self.POINT_4_Y_INDEX])
            self._point_4_z = float(elements[self.POINT_4_Z_INDEX])

    @property
    def point_1_x(self):
        return self._point_1_x
    
    @point_1_x.setter
    def point_1_x(self, x):
        self._point_1_x = x
        super().update_content_element(str(self._point_1_x), self.POINT_1_X_INDEX)

    @property
    def point_1_y(self):
        return self._point_1_y
    
    @point_1_y.setter
    def point_1_y(self, y):
        self._point_1_y = y
        super().update_content_element(str(self._point_1_y), self.POINT_1_Y_INDEX)
        
    @property
    def point_1_z(self):
        return self._point_1_z
    
    @point_1_z.setter
    def point_1_z(self, z):
        self._point_1_z = z
        super().update_content_element(str(self._point_1_z), self.POINT_1_Z_INDEX)
        
    @property
    def point_2_x(self):
        return self._point_2_x
    
    @point_2_x.setter
    def point_2_x(self, x):
        self._point_2_x = x
        super().update_content_element(str(self._point_2_x), self.POINT_2_X_INDEX)

    @property
    def point_2_y(self):
        return self._point_2_y
    
    @point_2_y.setter
    def point_2_y(self, y):
        self._point_2_y = y
        super().update_content_element(str(self._point_2_y), self.POINT_2_Y_INDEX)

    @property
    def point_2_z(self):
        return self._point_2_z
    
    @point_2_z.setter
    def point_2_z(self, z):
        self._point_2_z = z
        super().update_content_element(str(self._point_2_z), self.POINT_2_Z_INDEX)

    @property
    def point_3_x(self):
        return self._point_3_x
    
    @point_3_x.setter
    def point_3_x(self, x):
        self._point_3_x = x
        super().update_content_element(str(self._point_3_x), self.POINT_3_X_INDEX)

    @property
    def point_3_y(self):
        return self._point_3_y
    
    @point_3_y.setter
    def point_3_y(self, y):
        self._point_3_y = y
        super().update_content_element(str(self._point_3_y), self.POINT_3_Y_INDEX)

    @property
    def point_3_z(self):
        return self._point_3_z
    
    @point_3_z.setter
    def point_3_z(self, z):
        self._point_3_z = z
        super().update_content_element(str(self._point_3_z), self.POINT_3_Z_INDEX)
        
    @property
    def point_4_x(self):
        return self._point_4_x
    
    @point_4_x.setter
    def point_4_x(self, x):
        self._point_4_x = x
        super().update_content_element(str(self._point_4_x), self.POINT_4_X_INDEX)

    @property
    def point_4_y(self):
        return self._point_4_y
    
    @point_4_y.setter
    def point_4_y(self, y):
        self._point_4_y = y
        super().update_content_element(str(self._point_4_y), self.POINT_4_Y_INDEX)

    @property
    def point_4_z(self):
        return self._point_4_z
    
    @point_4_z.setter
    def point_4_z(self, z):
        self._point_4_z = z
        super().update_content_element(str(self._point_4_z), self.POINT_4_Z_INDEX)

    def move_coordinates(self, x, y, z):
        self.point_1_x += x
        self.point_2_x += x
        self.point_3_x += x
        self.point_1_y += y
        self.point_2_y += y
        self.point_3_y += y
        self.point_1_z += z
        self.point_2_z += z
        self.point_3_z += z
        
        if len(self.elements) == 29:
            self.point_4_x += x
            self.point_4_y += y
            self.point_4_z += z