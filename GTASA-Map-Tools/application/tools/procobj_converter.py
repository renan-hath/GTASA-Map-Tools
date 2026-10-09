import math
import struct


class ProcObjConverter:
    """
    Converts the rules of a procobj.dat file into static object placements.

    At runtime the game walks the collision triangles of the buildings around the camera and, for
    every triangle whose surface has rules in procobj.dat, spawns objects on it. The amount of
    objects comes from the triangle area and the rule spacing, and their position, rotation and
    height offset come from the C runtime rand(), which the game seeds with the triangle vertices
    and the object ID. That makes the result reproducible, so this class runs the same steps
    over every triangle instead of only the ones near the camera. Because of the seed, the result
    is only the same as in the game when the objects keep the IDs and the map keeps the position
    the mod was made with, so the conversion has to happen before any of them is changed.

    What cannot be carried over to an IPL file:
    - MINDIST, which only exists because of the camera
    - MINSCL, MAXSCL, MINSCLZ and MAXSCLZ, as INST objects have no scale. The game itself only
      scales the objects that are listed in object.dat
    """

    COL_NAME_LENGTH = 22
    COL_HEADER_LENGTH = 32
    COL_VERTEX_SCALE = 128.0

    INST_FLAG_FORCE_MATRIX = 512
    INST_FLAG_UNDERWATER = 1024

    # Objects are only aligned to surfaces steeper than this
    ALIGN_MAX_NORMAL_Z = 0.95
    RAND_TO_FLOAT = struct.unpack('<f', struct.pack('<f', 1.0 / 32767.0))[0]

    _FLOAT = struct.Struct('<f')

    def __init__(self, surface_ids, object_surfaces, water_surfaces):
        self.surface_ids = surface_ids
        self.object_surfaces = object_surfaces
        self.water_surfaces = water_surfaces
        self._rand_state = 0

    # Data files

    @staticmethod
    def read_surfaces(file_path):
        # Each line has the surface ID, its name and whether it creates objects and is water
        surface_ids = {}
        object_surfaces = set()
        water_surfaces = set()

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                elements = line.strip().split(',')

                if len(elements) < 4:
                    continue

                surface_id = int(elements[0])
                surface_ids[elements[1].upper()] = surface_id

                if int(elements[2]):
                    object_surfaces.add(surface_id)
                if int(elements[3]):
                    water_surfaces.add(surface_id)

        return surface_ids, object_surfaces, water_surfaces

    def read_surfinfo(self, file_path):
        # A mod can ship its own surfinfo.dat, changing which surfaces create objects
        SURFACE_NAME_INDEX = 0
        WATER_INDEX = 10
        PROC_OBJ_INDEX = 33

        object_surfaces = set()
        water_surfaces = set()

        with open(file_path, 'r', encoding='latin-1') as f:
            for line in f:
                elements = line.split()

                if len(elements) <= PROC_OBJ_INDEX or elements[0].startswith('#'):
                    continue

                surface_id = self.surface_ids.get(elements[SURFACE_NAME_INDEX].upper(), 0)

                try:
                    if int(elements[PROC_OBJ_INDEX]):
                        object_surfaces.add(surface_id)
                    if int(elements[WATER_INDEX]):
                        water_surfaces.add(surface_id)
                except ValueError:
                    continue

        self.object_surfaces = object_surfaces
        self.water_surfaces = water_surfaces

    def read_rules(self, file_path):
        rules = []

        with open(file_path, 'r', encoding='latin-1') as f:
            for line in f:
                elements = line.split()

                if len(elements) < 14 or elements[0].startswith('#'):
                    continue

                try:
                    rules.append({
                        'surface': elements[0].upper(),
                        # Unknown names fall back to the default surface, as the game does
                        'surface_id': self.surface_ids.get(elements[0].upper(), 0),
                        'model': elements[1],
                        'spacing': float(elements[2]),
                        'min_rot': math.radians(int(float(elements[4]))),
                        'max_rot': math.radians(int(float(elements[5]))),
                        'z_off_min': float(elements[10]),
                        'z_off_max': float(elements[11]),
                        'align': int(float(elements[12])) != 0,
                        'use_grid': int(float(elements[13])) != 0,
                    })
                except ValueError:
                    print(f'Invalid procobj.dat entry, skipping: "{line.strip()}"')

        return rules

    # Collision

    @classmethod
    def read_collisions(cls, content, surfaces):
        """
        Reads every model of a collision file, returning for each one its name, the lowest point of
        its bounding box and its triangles that use any of the given surfaces.
        """
        collisions = []
        offset = 0

        while offset + cls.COL_HEADER_LENGTH <= len(content):
            fourcc = bytes(content[offset:offset + 4])

            if fourcc not in (b'COLL', b'COL2', b'COL3', b'COL4'):
                break

            size = struct.unpack_from('<I', content, offset + 4)[0]
            model = bytes(content[offset + 8:offset + 8 + cls.COL_NAME_LENGTH]).split(b'\x00')[0]
            model = model.decode('ascii', errors='replace')
            body = content[offset:offset + 8 + size]

            try:
                if fourcc == b'COLL':
                    min_z, triangles = cls._read_collision_v1(body, surfaces)
                else:
                    min_z, triangles = cls._read_collision_v2(body, surfaces)

                collisions.append((model, min_z, triangles))
            except struct.error:
                print(f'Could not read the collision of {model}, skipping...')

            offset += 8 + size

        return collisions

    @classmethod
    def _read_collision_v1(cls, body, surfaces):
        SPHERE_LENGTH = 20
        BOX_LENGTH = 28
        FACE_LENGTH = 16

        # Radius, center, min and max
        min_z = struct.unpack_from('<f', body, cls.COL_HEADER_LENGTH + 24)[0]
        offset = cls.COL_HEADER_LENGTH + 40

        spheres_count = struct.unpack_from('<I', body, offset)[0]
        offset += 4 + spheres_count * SPHERE_LENGTH
        # Unused section
        offset += 4
        boxes_count = struct.unpack_from('<I', body, offset)[0]
        offset += 4 + boxes_count * BOX_LENGTH
        vertices_count = struct.unpack_from('<I', body, offset)[0]
        vertices_offset = offset + 4
        offset = vertices_offset + vertices_count * 12
        faces_count = struct.unpack_from('<I', body, offset)[0]
        offset += 4

        triangles = []

        for a, b, c, surface in struct.iter_unpack('<3IB3x', body[offset:offset + faces_count * FACE_LENGTH]):
            if surface in surfaces:
                triangles.append((struct.unpack_from('<3f', body, vertices_offset + a * 12),
                                  struct.unpack_from('<3f', body, vertices_offset + b * 12),
                                  struct.unpack_from('<3f', body, vertices_offset + c * 12),
                                  surface))

        return min_z, triangles

    @classmethod
    def _read_collision_v2(cls, body, surfaces):
        FACE_LENGTH = 8

        # Min, max, center and radius
        min_z = struct.unpack_from('<f', body, cls.COL_HEADER_LENGTH + 8)[0]
        faces_count = struct.unpack_from('<H', body, cls.COL_HEADER_LENGTH + 44)[0]
        # Offsets are relative to the end of the fourcc
        vertices_offset = struct.unpack_from('<I', body, cls.COL_HEADER_LENGTH + 64)[0] + 4
        faces_offset = struct.unpack_from('<I', body, cls.COL_HEADER_LENGTH + 68)[0] + 4

        triangles = []

        if not faces_count:
            return min_z, triangles

        for a, b, c, surface in struct.iter_unpack('<3HBx', body[faces_offset:faces_offset + faces_count * FACE_LENGTH]):
            if surface in surfaces:
                triangles.append((cls._read_compressed_vertex(body, vertices_offset + a * 6),
                                  cls._read_compressed_vertex(body, vertices_offset + b * 6),
                                  cls._read_compressed_vertex(body, vertices_offset + c * 6),
                                  surface))

        return min_z, triangles

    @classmethod
    def _read_compressed_vertex(cls, body, offset):
        x, y, z = struct.unpack_from('<3h', body, offset)
        return (x / cls.COL_VERTEX_SCALE, y / cls.COL_VERTEX_SCALE, z / cls.COL_VERTEX_SCALE)

    # Game arithmetic

    @classmethod
    def _f32(cls, value):
        # The game works with single precision floats, which matters for the random seed
        return cls._FLOAT.unpack(cls._FLOAT.pack(value))[0]

    def _srand(self, seed):
        self._rand_state = seed & 0xFFFFFFFF

    def _rand(self):
        self._rand_state = (self._rand_state * 214013 + 2531011) & 0xFFFFFFFF
        return (self._rand_state >> 16) & 0x7FFF

    def _random(self, minimum=0.0, maximum=1.0):
        return (maximum - minimum) * (self._rand() * self.RAND_TO_FLOAT) + minimum

    @staticmethod
    def _normalized(vector):
        length = math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2])

        if length == 0.0:
            return (0.0, 0.0, 0.0)

        return (vector[0] / length, vector[1] / length, vector[2] / length)

    @staticmethod
    def _cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    @staticmethod
    def get_instance_matrix(rotation):
        """
        Returns the right, forward and up vectors the game gives to an INST object. Its quaternion
        is stored inverted, and only its heading is used when the object is barely tilted.
        """
        x, y, z, w = rotation

        if abs(x) > 0.05 or abs(y) > 0.05:
            x, y, z = -x, -y, -z
            return ((1.0 - 2.0 * (z * z + y * y), 2.0 * (z * w + y * x), 2.0 * (z * x - y * w)),
                    (2.0 * (y * x - z * w), 1.0 - 2.0 * (z * z + x * x), 2.0 * (x * w + z * y)),
                    (2.0 * (y * w + z * x), 2.0 * (z * y - x * w), 1.0 - 2.0 * (y * y + x * x)))

        heading = math.acos(max(-1.0, min(1.0, w))) * (2.0 if z < 0.0 else -2.0)
        return ((math.cos(heading), math.sin(heading), 0.0),
                (-math.sin(heading), math.cos(heading), 0.0),
                (0.0, 0.0, 1.0))

    @staticmethod
    def _matrix_to_quaternion(right, forward, up):
        trace = right[0] + forward[1] + up[2]

        if trace > 0.0:
            s = math.sqrt(trace + 1.0) * 2.0
            return ((forward[2] - up[1]) / s, (up[0] - right[2]) / s, (right[1] - forward[0]) / s, s / 4.0)
        if right[0] > forward[1] and right[0] > up[2]:
            s = math.sqrt(1.0 + right[0] - forward[1] - up[2]) * 2.0
            return (s / 4.0, (forward[0] + right[1]) / s, (up[0] + right[2]) / s, (forward[2] - up[1]) / s)
        if forward[1] > up[2]:
            s = math.sqrt(1.0 + forward[1] - right[0] - up[2]) * 2.0
            return ((forward[0] + right[1]) / s, s / 4.0, (up[1] + forward[2]) / s, (up[0] - right[2]) / s)

        s = math.sqrt(1.0 + up[2] - right[0] - forward[1]) * 2.0
        return ((up[0] + right[2]) / s, (up[1] + forward[2]) / s, s / 4.0, (right[1] - forward[0]) / s)

    # Generation

    def transform_triangle(self, triangle, position, matrix):
        right, forward, up = matrix
        vertices = []

        for x, y, z in triangle[:3]:
            vertices.append((self._f32(position[0] + right[0] * x + forward[0] * y + up[0] * z),
                             self._f32(position[1] + right[1] * x + forward[1] * y + up[1] * z),
                             self._f32(position[2] + right[2] * x + forward[2] * y + up[2] * z)))

        return vertices

    def _get_seed(self, vertices, object_id):
        f32 = self._f32
        v1, v2, v3 = vertices
        seed = f32(f32(v3[2] + v3[1]) + v3[0])
        seed = f32(seed + f32(f32(v2[2] + v2[1]) + v2[0]))
        seed = f32(seed + f32(f32(v1[2] + v1[1]) + v1[0]))
        return int(f32(seed + object_id))

    def generate_objects(self, rule, object_id, min_z, vertices):
        """
        Returns the position, INST rotation and INST flags of every object the given rule creates
        on a triangle, whose vertices must already be in world coordinates.
        """
        v1, v2, v3 = vertices
        vec1 = (v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2])
        vec2 = (v3[0] - v2[0], v3[1] - v2[1], v3[2] - v2[2])
        vec3 = (v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2])
        normal = self._cross(vec3, vec1)
        area = math.sqrt(normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2]) * 0.5
        normal = self._normalized(normal)
        objects = []

        self._srand(self._get_seed(vertices, object_id))

        if not rule['use_grid']:
            density = area / (rule['spacing'] * rule['spacing'])

            while density > 0.0:
                cut_off = self._random() if density < 1.0 else 1.0

                if cut_off < density:
                    offset1 = self._random()
                    offset2 = offset1 * self._random()
                    position = (v1[0] + vec1[0] * offset1 + vec2[0] * offset2,
                                v1[1] + vec1[1] * offset1 + vec2[1] * offset2,
                                v1[2] + vec1[2] * offset1 + vec2[2] * offset2)
                    objects.append(self._place_object(rule, min_z, position, normal))

                density -= 1.0
        elif normal[2] != 0.0:
            spacing = rule['spacing']
            step = 1.0 / spacing
            x_start = float(int(int(min(v1[0], v2[0], v3[0]) * step) * spacing))
            x_end = float(int((int(max(v1[0], v2[0], v3[0]) * step) + 1) * spacing))
            y_start = float(int(int(min(v1[1], v2[1], v3[1]) * step) * spacing))
            y_end = float(int((int(max(v1[1], v2[1], v3[1]) * step) + 1) * spacing))

            x = x_start
            while x < x_end:
                y = y_start
                while y < y_end:
                    if self._is_point_in_triangle(x, y, v1, v2, v3):
                        z = (-(normal[0] * x) - normal[1] * y +
                             (v1[2] * normal[2] + normal[1] * v1[1] + normal[0] * v1[0])) / normal[2]
                        objects.append(self._place_object(rule, min_z, (x, y, z), normal))
                    y += spacing
                x += spacing

        return objects

    @staticmethod
    def _is_point_in_triangle(x, y, v1, v2, v3):
        return not ((v1[0] - v2[0]) * (v1[1] - y) + (v2[1] - v1[1]) * (v1[0] - x) > 0.0 or
                    (v2[0] - v3[0]) * (v2[1] - y) + (v3[1] - v2[1]) * (v2[0] - x) > 0.0 or
                    (v1[1] - v3[1]) * (v3[0] - x) + (v3[0] - v1[0]) * (v3[1] - y) > 0.0)

    def _place_object(self, rule, min_z, position, normal):
        # Creating the object draws a random number for it, and both scales are drawn even when
        # the game does not use them
        self._rand()
        self._rand()
        self._rand()
        rotation = self._random(rule['min_rot'], rule['max_rot'])
        z_offset = self._random(rule['z_off_min'], rule['z_off_max'])
        flags = self.INST_FLAG_UNDERWATER if rule['surface_id'] in self.water_surfaces else 0

        if rule['align'] and normal[2] < self.ALIGN_MAX_NORMAL_Z:
            forward = self._normalized(self._cross(normal, (math.cos(rotation), math.sin(rotation), 0.0)))
            right = self._normalized(self._cross(forward, normal))
            height = z_offset - min_z
            position = (position[0] + normal[0] * height,
                        position[1] + normal[1] * height,
                        position[2] + normal[2] * height)
            x, y, z, w = self._matrix_to_quaternion(right, forward, normal)
            # Without this flag the game discards the tilt of barely tilted objects
            return position, (-x, -y, -z, w), flags | self.INST_FLAG_FORCE_MATRIX

        position = (position[0], position[1], position[2] + z_offset - min_z)
        return position, (0.0, 0.0, -math.sin(rotation / 2.0), math.cos(rotation / 2.0)), flags
