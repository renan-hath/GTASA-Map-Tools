from application.data_entry_types.str.data_entry_str import DataEntryStr

class Jump(DataEntryStr):
    
    X_START_LOWER_POS_INDEX = 0
    Y_START_LOWER_POS_INDEX = 1
    Z_START_LOWER_POS_INDEX = 2
    X_START_UPPER_POS_INDEX = 3
    Y_START_UPPER_POS_INDEX = 4
    Z_START_UPPER_POS_INDEX = 5
    X_TARGET_LOWER_POS_INDEX = 6
    Y_TARGET_LOWER_POS_INDEX = 7
    Z_TARGET_LOWER_POS_INDEX = 8
    X_TARGET_UPPER_POS_INDEX = 9
    Y_TARGET_UPPER_POS_INDEX = 10
    Z_TARGET_UPPER_POS_INDEX = 11
    X_CAMERA_POS_INDEX = 12
    Y_CAMERA_POS_INDEX = 13
    Z_CAMERA_POS_INDEX = 14
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        
        self._x_start_lower_pos = float(elements[self.X_START_LOWER_POS_INDEX])
        self._y_start_lower_pos = float(elements[self.Y_START_LOWER_POS_INDEX])
        self._z_start_lower_pos = float(elements[self.Z_START_LOWER_POS_INDEX])
        self._x_start_upper_pos = float(elements[self.X_START_UPPER_POS_INDEX])
        self._y_start_upper_pos = float(elements[self.Y_START_UPPER_POS_INDEX])
        self._z_start_upper_pos = float(elements[self.Z_START_UPPER_POS_INDEX])
        self._x_target_lower_pos = float(elements[self.X_TARGET_LOWER_POS_INDEX])
        self._y_target_lower_pos = float(elements[self.Y_TARGET_LOWER_POS_INDEX])
        self._z_target_lower_pos = float(elements[self.Z_TARGET_LOWER_POS_INDEX])
        self._x_target_upper_pos = float(elements[self.X_TARGET_UPPER_POS_INDEX])
        self._y_target_upper_pos = float(elements[self.Y_TARGET_UPPER_POS_INDEX])
        self._z_target_upper_pos = float(elements[self.Z_TARGET_UPPER_POS_INDEX])
        self._x_camera_pos = float(elements[self.X_CAMERA_POS_INDEX])
        self._y_camera_pos = float(elements[self.Y_CAMERA_POS_INDEX])
        self._z_camera_pos = float(elements[self.Z_CAMERA_POS_INDEX])

    @property
    def x_start_lower_pos(self):
        return self._x_start_lower_pos
    
    @x_start_lower_pos.setter
    def x_start_lower_pos(self, x_start_lower_pos):
        self._x_start_lower_pos = x_start_lower_pos
        super().update_content_element(str(self._x_start_lower_pos), self.X_START_LOWER_POS_INDEX)
    
    @property
    def y_start_lower_pos(self):
        return self._y_start_lower_pos
    
    @y_start_lower_pos.setter
    def y_start_lower_pos(self, y_start_lower_pos):
        self._y_start_lower_pos = y_start_lower_pos
        super().update_content_element(str(self._y_start_lower_pos), self.Y_START_LOWER_POS_INDEX)
    
    @property
    def z_start_lower_pos(self):
        return self._z_start_lower_pos
    
    @z_start_lower_pos.setter
    def z_start_lower_pos(self, z_start_lower_pos):
        self._z_start_lower_pos = z_start_lower_pos
        super().update_content_element(str(self._z_start_lower_pos), self.Z_START_LOWER_POS_INDEX)
        
    @property
    def x_start_upper_pos(self):
        return self._x_start_upper_pos
    
    @x_start_upper_pos.setter
    def x_start_upper_pos(self, x_start_upper_pos):
        self._x_start_upper_pos = x_start_upper_pos
        super().update_content_element(str(self._x_start_upper_pos), self.X_START_UPPER_POS_INDEX)
        
    @property
    def y_start_upper_pos(self):
        return self._y_start_upper_pos
    
    @y_start_upper_pos.setter
    def y_start_upper_pos(self, y_start_upper_pos):
        self._y_start_upper_pos = y_start_upper_pos
        super().update_content_element(str(self._y_start_upper_pos), self.Y_START_UPPER_POS_INDEX)
        
    @property
    def z_start_upper_pos(self):
        return self._z_start_upper_pos
    
    @z_start_upper_pos.setter
    def z_start_upper_pos(self, z_start_upper_pos):
        self._z_start_upper_pos = z_start_upper_pos
        super().update_content_element(str(self._z_start_upper_pos), self.Z_START_UPPER_POS_INDEX)
        
    @property
    def x_target_lower_pos(self):
        return self._x_target_lower_pos
    
    @x_target_lower_pos.setter
    def x_target_lower_pos(self, x_target_lower_pos):
        self._x_target_lower_pos = x_target_lower_pos
        super().update_content_element(str(self._x_target_lower_pos), self.X_TARGET_LOWER_POS_INDEX)
        
    @property
    def y_target_lower_pos(self):
        return self._y_target_lower_pos
    
    @y_target_lower_pos.setter
    def y_target_lower_pos(self, y_target_lower_pos):
        self._y_target_lower_pos = y_target_lower_pos
        super().update_content_element(str(self._y_target_lower_pos), self.Y_TARGET_LOWER_POS_INDEX)
        
    @property
    def z_target_lower_pos(self):
        return self._z_target_lower_pos
    
    @z_target_lower_pos.setter
    def z_target_lower_pos(self, z_target_lower_pos):
        self._z_target_lower_pos = z_target_lower_pos
        super().update_content_element(str(self._z_target_lower_pos), self.Z_TARGET_LOWER_POS_INDEX)
        
    @property
    def x_target_upper_pos(self):
        return self._x_target_upper_pos
    
    @x_target_upper_pos.setter
    def x_target_upper_pos(self, x_target_upper_pos):
        self._x_target_upper_pos = x_target_upper_pos
        super().update_content_element(str(self._x_target_upper_pos), self.X_TARGET_UPPER_POS_INDEX)
        
    @property
    def y_target_upper_pos(self):
        return self._y_target_upper_pos
    
    @y_target_upper_pos.setter
    def y_target_upper_pos(self, y_target_upper_pos):
        self._y_target_upper_pos = y_target_upper_pos
        super().update_content_element(str(self._y_target_upper_pos), self.Y_TARGET_UPPER_POS_INDEX)
        
    @property
    def z_target_upper_pos(self):
        return self._z_target_upper_pos
    
    @z_target_upper_pos.setter
    def z_target_upper_pos(self, z_target_upper_pos):
        self._z_target_upper_pos = z_target_upper_pos
        super().update_content_element(str(self._z_target_upper_pos), self.Z_TARGET_UPPER_POS_INDEX)
        
    @property
    def x_camera_pos(self):
        return self._x_camera_pos
    
    @x_camera_pos.setter
    def x_camera_pos(self, x_camera_pos):
        self._x_camera_pos = x_camera_pos
        super().update_content_element(str(self._x_camera_pos), self.X_CAMERA_POS_INDEX)
        
    @property
    def y_camera_pos(self):
        return self._y_camera_pos
    
    @y_camera_pos.setter
    def y_camera_pos(self, y_camera_pos):
        self._y_camera_pos = y_camera_pos
        super().update_content_element(str(self._y_camera_pos), self.Y_CAMERA_POS_INDEX)
        
    @property
    def z_camera_pos(self):
        return self._z_camera_pos
    
    @z_camera_pos.setter
    def z_camera_pos(self, z_camera_pos):
        self._z_camera_pos = z_camera_pos
        super().update_content_element(str(self._z_camera_pos), self.Z_CAMERA_POS_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.x_start_lower_pos += x
        self.x_start_upper_pos += x
        self.x_target_lower_pos += x
        self.x_target_upper_pos += x
        self.x_camera_pos += x
        self.y_start_lower_pos += y
        self.y_start_upper_pos += y
        self.y_target_lower_pos += y
        self.y_target_upper_pos += y
        self.y_camera_pos += y
        self.z_start_lower_pos += z
        self.z_start_upper_pos += z
        self.z_target_lower_pos += z
        self.z_target_upper_pos += z
        self.z_camera_pos += z