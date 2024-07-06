from data_entry_types.data_entry import DataEntry

class Inst(DataEntry):
    
    ID_INDEX = 0
    MODEL_INDEX = 1
    X_POS_INDEX = 3
    Y_POS_INDEX = 4
    Z_POS_INDEX = 5
    X_ROT_INDEX = 6
    Y_ROT_INDEX = 7
    Z_ROT_INDEX = 8
    W_ROT_INDEX = 9
    LOD_INDEX = 10
    
    def __init__(self, line, line_position, section, file_name):
        super().__init__(line, line_position, section, file_name)
        elements = super().get_line_elements()
        
        self._obj_id = int(elements[self.ID_INDEX])
        self._model = elements[self.MODEL_INDEX]
        self._x_pos = float(elements[self.X_POS_INDEX])
        self._y_pos = float(elements[self.Y_POS_INDEX])
        self._z_pos = float(elements[self.Z_POS_INDEX])
        self._x_rot = float(elements[self.X_ROT_INDEX])
        self._y_rot = float(elements[self.Y_ROT_INDEX])
        self._z_rot = float(elements[self.Z_ROT_INDEX])
        self._w_rot = float(elements[self.W_ROT_INDEX])
        self._lod = int(elements[self.LOD_INDEX])

    @property
    def obj_id(self):
        return self._obj_id
    
    @obj_id.setter
    def obj_id(self, id):
        self._obj_id = id
        super().update_line_element(str(self._obj_id), self.ID_INDEX)
    
    @property
    def model(self):
        return self._model
    
    @model.setter
    def model(self, model):
        self._model = model
        super().update_line_element(self._model, self.MODEL_INDEX)
    
    @property
    def x_pos(self):
        return self._x_pos
    
    @x_pos.setter
    def x_pos(self, x_pos):
        self._x_pos = x_pos
        super().update_line_element(str(self._x_pos), self.X_POS_INDEX)
        
    @property
    def y_pos(self):
        return self._y_pos
    
    @y_pos.setter
    def y_pos(self, y_pos):
        self._y_pos = y_pos
        super().update_line_element(str(self._y_pos), self.Y_POS_INDEX)
        
    @property
    def z_pos(self):
        return self._z_pos
    
    @z_pos.setter
    def z_pos(self, z_pos):
        self._z_pos = z_pos
        super().update_line_element(str(self._z_pos), self.Z_POS_INDEX)
        
    @property
    def x_rot(self):
        return self._x_rot
    
    @x_rot.setter
    def x_rot(self, x_rot):
        self._x_rot = x_rot
        super().update_line_element(str(self._x_rot), self.X_ROT_INDEX)
        
    @property
    def y_rot(self):
        return self._y_rot
    
    @y_rot.setter
    def y_rot(self, y_rot):
        self._y_rot = y_rot
        super().update_line_element(str(self._y_rot), self.Y_ROT_INDEX)
        
    @property
    def z_rot(self):
        return self._z_rot
    
    @z_rot.setter
    def z_rot(self, z_rot):
        self._z_rot = z_rot
        super().update_line_element(str(self._z_rot), self.Z_ROT_INDEX)
        
    @property
    def w_rot(self):
        return self._w_rot
    
    @w_rot.setter
    def w_rot(self, w_rot):
        self._w_rot = w_rot
        super().update_line_element(str(self._w_rot), self.W_ROT_INDEX)
        
    @property
    def lod(self):
        return self._lod
    
    @lod.setter
    def lod(self, lod):
        self._lod = lod
        super().update_line_element(str(self._lod), self.LOD_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.x_pos += x
        self.y_pos += y
        self.z_pos += z
        
    def move_rotations(self, x, y, z, w):
        self.x_rot += x
        self.y_rot += y
        self.z_rot += z
        self.w_rot += w