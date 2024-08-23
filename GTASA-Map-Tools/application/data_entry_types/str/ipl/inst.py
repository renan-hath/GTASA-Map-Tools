import uuid
from application.data_entry_types.str.data_entry_str import DataEntryStr

class Inst(DataEntryStr):
    
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
    
    def __init__(self, line, line_position, section, file):
        super().__init__(line, line_position, section, file)
        elements = super().get_content_elements()
        
        self._internal_id = uuid.uuid4()
        self._internal_lod_id = None
        
        self._obj_id = int(elements[self.ID_INDEX])
        self._model = elements[self.MODEL_INDEX]
        self._x_pos = float(elements[self.X_POS_INDEX])
        self._y_pos = float(elements[self.Y_POS_INDEX])
        self._z_pos = float(elements[self.Z_POS_INDEX])
        self._x_rot = float(elements[self.X_ROT_INDEX])
        self._y_rot = float(elements[self.Y_ROT_INDEX])
        self._z_rot = float(elements[self.Z_ROT_INDEX])
        self._w_rot = float(elements[self.W_ROT_INDEX])
        try:
            self._lod = int(elements[self.LOD_INDEX])
        except ValueError:
            print(f'Invalid LOD for {self._obj_id},{self._model} ({file.file_name}): "{elements[self.LOD_INDEX]}". Setting LOD as -1...')
            self._lod = -1
        
        self._is_lod = False
        self._has_lod = self.lod > -1

    @property
    def internal_id(self):
        return self._internal_id
        
    @property
    def internal_lod_id(self):
        return self._internal_lod_id
    
    @internal_lod_id.setter
    def internal_lod_id(self, internal_lod_id):
        self._internal_lod_id = internal_lod_id
    
    @property
    def has_lod(self):
        return self._has_lod
    
    @property
    def is_lod(self):
        return self._is_lod
    
    @is_lod.setter
    def is_lod(self, is_lod):
        self._is_lod = is_lod
    
    def remove_lod(self):
        if self.has_lod:
            self._has_lod = False
            self.internal_lod_id = None
            self.lod = -1

    @property
    def obj_id(self):
        return self._obj_id
    
    @obj_id.setter
    def obj_id(self, obj_id):
        self._obj_id = obj_id
        super().update_content_element(str(self._obj_id), self.ID_INDEX)
    
    @property
    def model(self):
        return self._model
    
    @model.setter
    def model(self, model):
        self._model = model
        super().update_content_element(self._model, self.MODEL_INDEX)
    
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
    def x_rot(self):
        return self._x_rot
    
    @x_rot.setter
    def x_rot(self, x_rot):
        self._x_rot = x_rot
        super().update_content_element(str(self._x_rot), self.X_ROT_INDEX)
        
    @property
    def y_rot(self):
        return self._y_rot
    
    @y_rot.setter
    def y_rot(self, y_rot):
        self._y_rot = y_rot
        super().update_content_element(str(self._y_rot), self.Y_ROT_INDEX)
        
    @property
    def z_rot(self):
        return self._z_rot
    
    @z_rot.setter
    def z_rot(self, z_rot):
        self._z_rot = z_rot
        super().update_content_element(str(self._z_rot), self.Z_ROT_INDEX)
        
    @property
    def w_rot(self):
        return self._w_rot
    
    @w_rot.setter
    def w_rot(self, w_rot):
        self._w_rot = w_rot
        super().update_content_element(str(self._w_rot), self.W_ROT_INDEX)
        
    @property
    def lod(self):
        return self._lod
    
    @lod.setter
    def lod(self, lod):
        self._lod = lod
        super().update_content_element(str(self._lod), self.LOD_INDEX)
        
    def move_coordinates(self, x, y, z):
        self.x_pos += x
        self.y_pos += y
        self.z_pos += z
        
    def move_rotations(self, x, y, z, w):
        x1 = self.x_rot
        y1 = self.y_rot
        z1 = self.z_rot
        w1 = self.w_rot
        
        x2 = x
        y2 = y
        z2 = z
        w2 = w
        
        new_x_rot = (w1 * x2) + (x1 * w2) + (y1 * z2) - (z1 * y2)
        new_y_rot = (w1 * y2) - (x1 * z2) + (y1 * w2) + (z1 * x2)
        new_z_rot = (w1 * z2) + (x1 * y2) - (y1 * x2) + (z1 * w2)
        new_w_rot = (w1 * w2) - (x1 * x2) - (y1 * y2) - (z1 * z2)
        
        self.x_rot = new_x_rot
        self.y_rot = new_y_rot
        self.z_rot = new_z_rot
        self.w_rot = new_w_rot