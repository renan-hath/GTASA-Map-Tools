from application.data_entry_types.binary.data_entry_binary import DataEntryBinary

class InstBinary(DataEntryBinary):
    
    X_POS_INDEX = 0
    Y_POS_INDEX = 1
    Z_POS_INDEX = 2
    X_ROT_INDEX = 3
    Y_ROT_INDEX = 4
    Z_ROT_INDEX = 5
    W_ROT_INDEX = 6
    ID_INDEX = 7
    LOD_INDEX = 9
    
    def __init__(self, content, index, section, file):
        super().__init__(content, index, section, file)
        elements = super().get_content_elements()

        self._model = 'dummy'
        self._x_pos = super().to_float(elements[self.X_POS_INDEX])
        self._y_pos = super().to_float(elements[self.Y_POS_INDEX])
        self._z_pos = super().to_float(elements[self.Z_POS_INDEX])
        self._x_rot = super().to_float(elements[self.X_ROT_INDEX])
        self._y_rot = super().to_float(elements[self.Y_ROT_INDEX])
        self._z_rot = super().to_float(elements[self.Z_ROT_INDEX])
        self._w_rot = super().to_float(elements[self.W_ROT_INDEX])
        self._obj_id = super().to_int(elements[self.ID_INDEX])
        self._lod = super().to_int(elements[self.LOD_INDEX])
    
    @property
    def model(self):
        return self._model
    
    @model.setter
    def model(self, model):
        self._model = model

    @property
    def x_pos(self):
        
        return self._x_pos
    
    @x_pos.setter
    def x_pos(self, x_pos):
        self._x_pos = x_pos
        super().update_content_element(self._x_pos, 'f', self.X_POS_INDEX)
        
    @property
    def y_pos(self):
        return self._y_pos
    
    @y_pos.setter
    def y_pos(self, y_pos):
        self._y_pos = y_pos
        super().update_content_element(self._y_pos, 'f', self.Y_POS_INDEX)
        
    @property
    def z_pos(self):
        return self._z_pos
    
    @z_pos.setter
    def z_pos(self, z_pos):
        self._z_pos = z_pos
        super().update_content_element(self._z_pos, 'f', self.Z_POS_INDEX)
        
    @property
    def x_rot(self):
        return self._x_rot
    
    @x_rot.setter
    def x_rot(self, x_rot):
        self._x_rot = x_rot
        super().update_content_element(self._x_rot, 'f', self.X_ROT_INDEX)
        
    @property
    def y_rot(self):
        return self._y_rot
    
    @y_rot.setter
    def y_rot(self, y_rot):
        self._y_rot = y_rot
        super().update_content_element(self._y_rot, 'f', self.Y_ROT_INDEX)
        
    @property
    def z_rot(self):
        return self._z_rot
    
    @z_rot.setter
    def z_rot(self, z_rot):
        self._z_rot = z_rot
        super().update_content_element(self._z_rot, 'f', self.Z_ROT_INDEX)
        
    @property
    def w_rot(self):
        return self._w_rot
    
    @w_rot.setter
    def w_rot(self, w_rot):
        self._w_rot = w_rot
        super().update_content_element(self._w_rot, 'f', self.W_ROT_INDEX)
        
    @property
    def obj_id(self):
        return self._obj_id
    
    @obj_id.setter
    def obj_id(self, obj_id):
        self._obj_id = obj_id
        super().update_content_element(self._obj_id, 'i', self.ID_INDEX)
        
    @property
    def lod(self):
        return self._lod
    
    @lod.setter
    def lod(self, lod):
        self._lod = lod
        super().update_content_element(self._lod, 'i', self.LOD_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.x_pos += x
        self.y_pos += y
        self.z_pos += z
        
    def move_rotations(self, x, y, z, w):
        self.x_rot += x
        self.y_rot += y
        self.z_rot += z
        self.w_rot += w