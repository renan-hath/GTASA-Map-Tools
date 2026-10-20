import math
import os
import re
import struct

import numpy as np

from application.tools.path_positioner import PathPositioner
from application.tools.procobj_converter import ProcObjConverter
from application.tools.radar_generator import ImgArchive


class PathGenerator:
    """
    Generates the path nodes (nodes*.dat) of a map from the collision of its objects.

    Where vehicles and pedestrians should go is read from the surfaces of the collision: tarmac
    and dirt tracks are roads, and pavements are where pedestrians walk. Those surfaces are drawn
    from above on a grid of 1 unit, leaving out the ones with something solid right on top of
    them, then thinned down to their middle lines, which are turned into linked nodes.

    The nodes follow the logic of the paths of the game:
    - each file covers a tile of 750x750 units, with its vehicle nodes before its pedestrian nodes
    - links go both ways, vehicle nodes only link to vehicle nodes and pedestrian nodes only to
      pedestrian nodes
    - each pair of linked vehicle nodes shares a navi node halfway between them, which keeps the
      direction of the road and its lanes, one lane each way for every 10 units of road width
    - the nodes that can reach each other share the same flood fill group
    - pedestrians cross the roads near the junctions, through links marked as road crossings

    The new nodes are added to the node files the game already loads for the same tiles, so the
    paths of the original map and of other mods in those tiles are kept. Node files of an older
    version of the same map, recognised by having nodes on top of its roads or pavements, are
    left out instead.
    """

    TILE_SIZE = PathPositioner.TILE_SIZE
    COORD_SCALE = PathPositioner.COORD_SCALE
    VANILLA_GRID_WIDTH = PathPositioner.VANILLA_GRID_WIDTH
    NODE_FILE_PATTERN = PathPositioner.NODE_FILE_PATTERN

    # Interior 13 is shown everywhere, including outside
    EXTERIOR_INTERIORS = (0, 13)

    COL_FOURCCS = (b'COLL', b'COL2', b'COL3', b'COL4')
    COL_HEADER_LENGTH = 32
    COL_VERTEX_SCALE = 128.0

    RASTER_TILE_CELLS = 256
    RASTER_CHUNK_SAMPLES = 1 << 20

    VEHICLE_SURFACES = ('TARMAC', 'TARMAC_FUCKED', 'TARMAC_REALLYFUCKED')
    DIRT_ROAD_SURFACES = ('DIRTTRACK',)
    PEDESTRIAN_SURFACES = ('PAVEMENT', 'PAVEMENT_FUCKED', 'P_CONCRETE', 'P_CONCRETELITTER',
                           'CONCRETE_BEACH', 'STAIRSSTONE')
    SURFACE_OTHER = 0
    SURFACE_ROAD = 1
    SURFACE_DIRT_ROAD = 2
    SURFACE_PAVEMENT = 3

    # Steeper surfaces are walls, not floors
    MIN_FLOOR_NORMAL_Z = 0.7
    # Room needed above a floor for anyone to be on it
    HEADROOM = 2.5
    # Floors closer to each other than this are the same floor
    SAME_FLOOR_HEIGHT = 0.3
    # Highest step between neighbouring cells of the same road or pavement
    MAX_STEP = 1.5
    # Where a road and a pavement overlap, the one on top is kept
    OVERLAP_HEIGHT = 1.0
    MAX_HALF_WIDTH = 40
    MAX_DIRT_TRACK_HALF_WIDTH = 10

    VEHICLE_PATHS = {
        'name': 'vehicle',
        # Fills the seams between pieces of collision and removes tarmac too narrow to drive on
        'closing_radius': 2,
        'opening_radius': 2,
        'simplify_tolerance': 1.0,
        'min_link_length': 5.0,
        'max_link_length': 30.0,
        'junction_merge_length': 8.0,
        'min_spur_length': 6.0,
        'gap_length': 40.0,
        'gap_off_floor_length': 12.0,
        'min_network_length': 40.0,
    }
    PEDESTRIAN_PATHS = {
        'name': 'pedestrian',
        'closing_radius': 1,
        'opening_radius': 0,
        'simplify_tolerance': 0.5,
        'min_link_length': 2.0,
        'max_link_length': 12.0,
        'junction_merge_length': 3.0,
        'min_spur_length': 2.5,
        'gap_length': 6.0,
        'gap_off_floor_length': 4.0,
        'min_network_length': 12.0,
    }
    SPUR_WIDTH_FACTOR = 1.5
    GAP_MAX_ANGLE = math.radians(35)
    GAP_MAX_HOPS = 6

    CROSSING_MIN_LENGTH = 5.0
    CROSSING_MAX_LENGTH = 25.0
    # Crossings are placed near the junctions, across the road they cross
    CROSSING_JUNCTION_DISTANCE = 30.0
    CROSSING_MIN_ANGLE = math.radians(60)
    CROSSING_MIN_ROAD_SHARE = 0.4
    CROSSING_SPACING = 10.0

    # Values the game uses in its own node files
    HEURISTIC_COST = 0x7FFE
    LINK_COUNT_MASK = 0xF
    TRAFFIC_LEVEL_SHIFT = 4
    DIRT_ROAD_TRAFFIC_LEVEL = 2
    NOT_HIGHWAY = 1 << 12
    SPAWN_PROBABILITY = 0xF << 16
    LEFT_LANES_SHIFT = 8
    RIGHT_LANES_SHIFT = 11
    LANE_WIDTH = 5.0
    MAX_LANES = 3
    PEDESTRIAN_WIDTH = 16
    ROAD_CROSSING = 1
    MAX_LINKS = 15
    MAX_LINK_LENGTH = 255
    MAX_FLOOD_FILL = 255
    VANILLA_MAX_NAVIS = 1 << 10
    VANILLA_NAVI_AREA_SHIFT = 10
    # An older version of the map has most of its nodes on the roads and pavements of the map,
    # while another map next to it or even on top of it has few
    OLDER_VERSION_SHARE = 0.4
    OLDER_VERSION_MIN_NODES = 20
    # Kept in the first field of the generated nodes, which the game only uses once loaded
    GENERATED_NODE_MARKER = b'MTGP'
    FILLER = b'\xff\xff\x00\x00' * (PathPositioner.FILLER_SIZE // 4)

    class GenerationError(Exception):
        pass

    def __init__(self, game_dir, surfaces_path):
        self.game_dir = game_dir
        self.models_dir = os.path.join(game_dir, 'models') if game_dir else ''
        self.modloader_dir = os.path.join(game_dir, 'modloader') if game_dir else ''
        self.surface_ids = ProcObjConverter.read_surfaces(surfaces_path)[0]
        self._positioner = PathPositioner()
        self._archives = []

        self._surface_kinds = np.zeros(256, dtype=np.uint8)

        for names, kind in ((self.VEHICLE_SURFACES, self.SURFACE_ROAD),
                            (self.DIRT_ROAD_SURFACES, self.SURFACE_DIRT_ROAD),
                            (self.PEDESTRIAN_SURFACES, self.SURFACE_PAVEMENT)):
            for name in names:
                if name in self.surface_ids:
                    self._surface_kinds[self.surface_ids[name]] = kind

    # Main

    def run(self, instances, collision_files, output_dir, map_size=6000):
        """
        Generates the paths of the given objects, each one a model name, a position and an INST
        rotation, whose collision is in the given COL and IMG files or in the original game.
        """
        try:
            return self._generate(instances, collision_files, output_dir, map_size)
        except (self.GenerationError, PathPositioner.UnsupportedFormatError, OSError) as e:
            print(f'Error while generating paths: {e}')
            return False
        finally:
            for archive in self._archives:
                archive.close()
            self._archives = []

    def _generate(self, instances, collision_files, output_dir, map_size):
        paths_map_size = self.get_paths_map_size() or int(map_size)
        grid_width = paths_map_size // self.TILE_SIZE

        if grid_width not in PathPositioner.GRID_WIDTHS:
            raise self.GenerationError(f'{paths_map_size} is not a supported map size for paths.')

        print(f'(paths) Paths map size: {paths_map_size}')

        if not os.path.isdir(self.models_dir):
            print('(paths) WARNING: the GTA San Andreas folder is not set or was not found, so the paths the game '
                  'already has in the same tiles will be replaced, and objects of the original game have no collision.')

        meshes = self._read_collisions({model for model, position, rotation in instances}, collision_files)
        triangles, surfaces, walkable = self._place_triangles(instances, meshes)

        if not (walkable & (surfaces != self.SURFACE_OTHER)).any():
            print('(paths) No roads or pavements were found in the collision of the map, '
                  f'so no paths were generated. Roads need one of the surfaces {", ".join(self.VEHICLE_SURFACES + self.DIRT_ROAD_SURFACES)}, '
                  f'and pavements one of {", ".join(self.PEDESTRIAN_SURFACES)}.')
            return False

        print('(paths) Finding the roads and pavements...')
        grid = self._rasterize_floors(triangles, surfaces, walkable)

        print('(paths) Laying the vehicle nodes...')
        vehicles = self._find_paths(grid['road'], grid['road_heights'], grid, self.VEHICLE_PATHS)
        vehicles['dirt'] = self._sample(grid['dirt'], grid, vehicles['positions'])

        print('(paths) Laying the pedestrian nodes...')
        pedestrians = self._find_paths(grid['pavement'], grid['pavement_heights'], grid, self.PEDESTRIAN_PATHS)
        pedestrians['crossings'] = self._add_crossings(pedestrians, vehicles, grid)

        print(f"(paths) {len(vehicles['positions'])} vehicle nodes and {len(pedestrians['positions'])} pedestrian nodes generated, "
              f"with {len(pedestrians['crossings'])} road crossings.")

        if not len(vehicles['positions']) and not len(pedestrians['positions']):
            return False

        written = self._write_node_files(vehicles, pedestrians, grid, grid_width, output_dir)
        print(f'(paths) {written} node files saved at: {output_dir}')
        return written > 0

    def get_paths_map_size(self):
        # The paths map size of fastman92 Limit Adjuster sets how many node files the game loads
        ini_path = os.path.join(self.game_dir, 'fastman92limitAdjuster_GTASA.ini')

        if self.game_dir and os.path.isfile(ini_path):
            with open(ini_path, 'r', encoding='latin-1') as ini_file:
                for line in ini_file:
                    match = re.match(r'^\s*Paths map size\s*=\s*(\d+)', line, re.IGNORECASE)
                    if match:
                        return int(match.group(1))

        return 0

    # Collision

    def _read_collisions(self, models, collision_files):
        models = {model.lower() for model in models}
        meshes = {}

        for file_path in collision_files:
            if file_path.lower().endswith('.img'):
                archive = ImgArchive(file_path)
                self._archives.append(archive)

                for name in archive.entries:
                    if name.endswith('.col'):
                        self._read_collision_file(archive.read(name), models, meshes)
            elif file_path.lower().endswith('.col'):
                with open(file_path, 'rb') as col_file:
                    self._read_collision_file(col_file.read(), models, meshes)

        # The objects of the original game have their collision in its own IMG file
        missing = models - set(meshes)
        gta3_path = os.path.join(self.models_dir, 'gta3.img')

        if missing and os.path.isfile(gta3_path):
            archive = ImgArchive(gta3_path)
            self._archives.append(archive)

            for name in archive.entries:
                if name.endswith('.col'):
                    self._read_collision_file(archive.read(name), missing, meshes)

        print(f'(paths) Collision found for {len(meshes)} of {len(models)} models')
        return meshes

    def _read_collision_file(self, content, models, meshes):
        for model, body, fourcc in self.iter_collision_models(content):
            if model in models and model not in meshes:
                try:
                    mesh = self._read_collision_mesh(body, fourcc)
                except (struct.error, ValueError, IndexError):
                    print(f'(paths) Could not read the collision of {model}, skipping...')
                    mesh = None

                if mesh is not None:
                    meshes[model] = mesh

    @classmethod
    def iter_collision_models(cls, content):
        # A collision file is a sequence of models, each one with its name in its header
        offset = 0

        while offset + cls.COL_HEADER_LENGTH <= len(content):
            fourcc = bytes(content[offset:offset + 4])

            if fourcc not in cls.COL_FOURCCS:
                break

            size = struct.unpack_from('<I', content, offset + 4)[0]
            model = bytes(content[offset + 8:offset + 30]).split(b'\x00')[0].decode('ascii', errors='replace').lower()
            yield model, content[offset:offset + 8 + size], fourcc

            offset += 8 + size

    def _read_collision_mesh(self, body, fourcc):
        model = self.read_collision_model(body, fourcc)

        if model is None or not len(model['faces']):
            return None

        return {'vertices': model['vertices'], 'faces': model['faces'],
                'surfaces': self._surface_kinds[model['surfaces']]}

    @classmethod
    def read_collision_model(cls, body, fourcc):
        """
        Returns the vertices, the faces and the surface of each face of a collision model, and
        the corners and the surface of each one of its boxes.
        """
        BOUNDS_LENGTH = 40
        BOX_TYPE = np.dtype([('min', '<f4', 3), ('max', '<f4', 3), ('surface', 'u1'), ('rest', 'V3')])
        offset = cls.COL_HEADER_LENGTH + BOUNDS_LENGTH

        if fourcc == b'COLL':
            SPHERE_LENGTH = 20

            spheres_count = struct.unpack_from('<I', body, offset)[0]
            # Spheres, then an unused section
            offset += 4 + spheres_count * SPHERE_LENGTH + 4
            boxes_count = struct.unpack_from('<I', body, offset)[0]
            boxes = np.frombuffer(body, dtype=BOX_TYPE, count=boxes_count, offset=offset + 4)
            offset += 4 + boxes_count * BOX_TYPE.itemsize
            vertices_count = struct.unpack_from('<I', body, offset)[0]
            vertices = np.frombuffer(body, dtype='<f4', count=vertices_count * 3, offset=offset + 4).reshape(-1, 3)
            offset += 4 + vertices_count * 12
            faces_count = struct.unpack_from('<I', body, offset)[0]
            faces = np.frombuffer(body, dtype=np.dtype([('vertices', '<u4', 3), ('surface', 'u1'), ('rest', 'V3')]),
                                  count=faces_count, offset=offset + 4)
        else:
            boxes_count, faces_count = struct.unpack_from('<HH', body, offset + 2)
            # Offsets are relative to the end of the fourcc
            boxes_offset = struct.unpack_from('<I', body, offset + 16)[0] + 4
            vertices_offset = struct.unpack_from('<I', body, offset + 24)[0] + 4
            faces_offset = struct.unpack_from('<I', body, offset + 28)[0] + 4

            boxes = np.frombuffer(body, dtype=BOX_TYPE, count=boxes_count, offset=boxes_offset)
            faces = np.frombuffer(body, dtype=np.dtype([('vertices', '<u2', 3), ('surface', 'u1'), ('light', 'u1')]),
                                  count=faces_count, offset=faces_offset)
            # The amount of vertices is not stored, the faces tell how many there are
            vertices_count = int(faces['vertices'].max()) + 1 if faces_count else 0
            vertices = np.frombuffer(body, dtype='<i2', count=vertices_count * 3,
                                     offset=vertices_offset).reshape(-1, 3) / cls.COL_VERTEX_SCALE

        indices = faces['vertices'].astype(np.int64)

        if len(indices) and indices.max() >= len(vertices):
            return None

        return {'vertices': vertices.astype(np.float32), 'faces': indices, 'surfaces': faces['surface'],
                'box_mins': boxes['min'], 'box_maxs': boxes['max'], 'box_surfaces': boxes['surface']}

    def _place_triangles(self, instances, meshes):
        triangles = []
        surfaces = []

        for model, position, rotation in instances:
            mesh = meshes.get(model.lower())

            if mesh is None:
                continue

            matrix = np.array(ProcObjConverter.get_instance_matrix(rotation), dtype=np.float32)
            vertices = mesh['vertices'] @ matrix + np.array(position, dtype=np.float32)
            triangles.append(vertices[mesh['faces']])
            surfaces.append(mesh['surfaces'])

        if not triangles:
            return np.zeros((0, 3, 3), dtype=np.float32), np.zeros(0, dtype=np.uint8), np.zeros(0, dtype=bool)

        triangles = np.concatenate(triangles)
        surfaces = np.concatenate(surfaces)

        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        lengths = np.linalg.norm(normals, axis=1)
        normal_z = np.abs(normals[:, 2]) / np.maximum(lengths, 1e-12)

        # Walls cannot be seen from above, so they neither are floors nor cover them
        seen_from_above = normal_z > 0.05
        triangles, surfaces, normal_z = triangles[seen_from_above], surfaces[seen_from_above], normal_z[seen_from_above]

        return triangles, surfaces, normal_z >= self.MIN_FLOOR_NORMAL_Z

    # Floors

    def _rasterize_floors(self, triangles, surfaces, walkable):
        """
        Returns, for each cell of 1x1 unit around the roads and pavements of the map, the height
        of the highest road, pavement and floor of any surface with enough room above it.
        """
        MARGIN = 4

        floors = walkable & (surfaces != self.SURFACE_OTHER)
        floor_triangles = triangles[floors]
        origin = np.floor(floor_triangles[:, :, :2].reshape(-1, 2).min(axis=0)) - MARGIN
        end = np.ceil(floor_triangles[:, :, :2].reshape(-1, 2).max(axis=0)) + MARGIN
        width, height = (end - origin).astype(np.int64)

        if width * height > 100_000_000:
            print(f'(paths) The map is {width}x{height} units wide, generating its paths will take a lot of memory...')

        cell_x = triangles[:, :, 0] - np.float32(origin[0])
        cell_y = triangles[:, :, 1] - np.float32(origin[1])
        inside = ((cell_x.max(axis=1) >= 0) & (cell_x.min(axis=1) < width) &
                  (cell_y.max(axis=1) >= 0) & (cell_y.min(axis=1) < height))
        cell_x, cell_y, cell_z = cell_x[inside], cell_y[inside], triangles[inside][:, :, 2]
        surfaces, floors, walkable = surfaces[inside], floors[inside], walkable[inside]

        heights = {kind: np.full((height, width), -np.inf, dtype=np.float32)
                   for kind in (self.SURFACE_ROAD, self.SURFACE_DIRT_ROAD, self.SURFACE_PAVEMENT)}
        ground_heights = np.full((height, width), -np.inf, dtype=np.float32)

        # Each triangle goes to every tile its bounding box touches
        tile = self.RASTER_TILE_CELLS
        tiles_x = math.ceil(width / tile)
        tiles_y = math.ceil(height / tile)
        first_x = np.clip(cell_x.min(axis=1) // tile, 0, tiles_x - 1).astype(np.int64)
        last_x = np.clip(cell_x.max(axis=1) // tile, 0, tiles_x - 1).astype(np.int64)
        first_y = np.clip(cell_y.min(axis=1) // tile, 0, tiles_y - 1).astype(np.int64)
        last_y = np.clip(cell_y.max(axis=1) // tile, 0, tiles_y - 1).astype(np.int64)
        columns = last_x - first_x + 1
        counts = columns * (last_y - first_y + 1)
        triangle_indices = np.repeat(np.arange(len(counts)), counts)
        offsets = np.arange(counts.sum()) - np.repeat(np.cumsum(counts) - counts, counts)
        tile_ids = ((np.repeat(first_y, counts) + offsets // np.repeat(columns, counts)) * tiles_x +
                    np.repeat(first_x, counts) + offsets % np.repeat(columns, counts))

        order = np.argsort(tile_ids, kind='stable')
        tile_ids, triangle_indices = tile_ids[order], triangle_indices[order]
        boundaries = np.flatnonzero(np.diff(tile_ids)) + 1

        for group in np.split(np.arange(len(tile_ids)), boundaries):
            if not len(group):
                continue

            tile_y, tile_x = divmod(int(tile_ids[group[0]]), tiles_x)
            x0, y0 = tile_x * tile, tile_y * tile
            size_x, size_y = min(tile, width - x0), min(tile, height - y0)
            indices = triangle_indices[group]

            # Only tiles with roads or pavements matter
            if not floors[indices].any():
                continue

            cells, sample_triangles, sample_z = self._rasterize(cell_x[indices] - x0, cell_y[indices] - y0,
                                                                cell_z[indices], size_x, size_y)

            if not len(cells):
                continue

            order = np.lexsort((sample_z, cells))
            cells, sample_triangles, sample_z = cells[order], indices[sample_triangles[order]], sample_z[order]

            # A floor is covered when the next surface above it, in the same cell, is too close
            keys = cells.astype(np.float64) * 1e6 + sample_z
            next_samples = np.searchsorted(keys, keys + self.SAME_FLOOR_HEIGHT, side='right')
            covered = np.zeros(len(cells), dtype=bool)
            has_next = next_samples < len(cells)
            next_samples = next_samples[has_next]
            covered[has_next] = ((cells[next_samples] == cells[has_next]) &
                                 (sample_z[next_samples] < sample_z[has_next] + self.HEADROOM))

            free = walkable[sample_triangles] & ~covered
            sample_surfaces = surfaces[sample_triangles]

            for kind, kind_heights in list(heights.items()) + [(None, ground_heights)]:
                selected = free & (sample_surfaces == kind) if kind is not None else free

                if selected.any():
                    tile_heights = np.full(size_x * size_y, -np.inf, dtype=np.float32)
                    np.maximum.at(tile_heights, cells[selected], sample_z[selected])
                    kind_heights[y0:y0 + size_y, x0:x0 + size_x] = tile_heights.reshape(size_y, size_x)

        # Wide dirt is open ground, not a track
        dirt = heights[self.SURFACE_DIRT_ROAD] > heights[self.SURFACE_ROAD]
        open_ground = self._dilate(self._half_widths(dirt) > self.MAX_DIRT_TRACK_HALF_WIDTH,
                                   self.MAX_DIRT_TRACK_HALF_WIDTH) & dirt
        heights[self.SURFACE_DIRT_ROAD][open_ground] = -np.inf
        dirt &= ~open_ground

        road_heights = np.maximum(heights[self.SURFACE_ROAD], heights[self.SURFACE_DIRT_ROAD])
        pavement_heights = heights[self.SURFACE_PAVEMENT]

        # Kerbs and pavements laid over the tarmac belong to the pedestrians
        with np.errstate(invalid='ignore'):
            overlap = ((road_heights > -np.inf) & (pavement_heights > -np.inf) &
                       (np.abs(road_heights - pavement_heights) < self.OVERLAP_HEIGHT))
        pavement_on_top = overlap & (pavement_heights >= road_heights - 0.05)
        road_heights[pavement_on_top] = -np.inf
        pavement_heights[overlap & ~pavement_on_top] = -np.inf

        return {
            'origin': origin,
            'road': road_heights > -np.inf,
            'road_heights': road_heights,
            'pavement': pavement_heights > -np.inf,
            'pavement_heights': pavement_heights,
            'ground_heights': ground_heights,
            'dirt': dirt,
        }

    def _rasterize(self, x, y, z, size_x, size_y):
        """
        Returns the cell, triangle and height of every cell center covered by the triangles,
        seen from above.
        """
        min_x = np.maximum(np.ceil(x.min(axis=1) - 0.5), 0)
        max_x = np.minimum(np.floor(x.max(axis=1) - 0.5), size_x - 1)
        min_y = np.maximum(np.ceil(y.min(axis=1) - 0.5), 0)
        max_y = np.minimum(np.floor(y.max(axis=1) - 0.5), size_y - 1)

        area = (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        visible = (width > 0) & (height > 0) & (np.abs(area) > 1e-6)

        all_cells, all_triangles, all_z = [], [], []

        if not visible.any():
            return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32)

        # Triangles are drawn in groups of similar size, testing every cell of their bounding box
        width_bucket = np.ceil(np.log2(np.maximum(width, 1))).astype(np.int32)
        height_bucket = np.ceil(np.log2(np.maximum(height, 1))).astype(np.int32)

        for bucket in np.unique(np.stack((width_bucket[visible], height_bucket[visible]), axis=1), axis=0):
            bucket_width, bucket_height = 1 << int(bucket[0]), 1 << int(bucket[1])
            indices = np.nonzero(visible & (width_bucket == bucket[0]) & (height_bucket == bucket[1]))[0]
            offset_y, offset_x = np.divmod(np.arange(bucket_width * bucket_height, dtype=np.float32), bucket_width)
            chunk_size = max(1, self.RASTER_CHUNK_SAMPLES // (bucket_width * bucket_height))

            for chunk_start in range(0, len(indices), chunk_size):
                chunk = indices[chunk_start:chunk_start + chunk_size]
                cell_x = min_x[chunk, None] + offset_x[None, :]
                cell_y = min_y[chunk, None] + offset_y[None, :]
                inside = (cell_x <= max_x[chunk, None]) & (cell_y <= max_y[chunk, None])

                center_x = cell_x + 0.5
                center_y = cell_y + 0.5
                x0, x1, x2 = (x[chunk, i, None] for i in range(3))
                y0, y1, y2 = (y[chunk, i, None] for i in range(3))
                chunk_area = area[chunk, None]
                weight0 = ((x1 - center_x) * (y2 - center_y) - (x2 - center_x) * (y1 - center_y)) / chunk_area
                weight1 = ((x2 - center_x) * (y0 - center_y) - (x0 - center_x) * (y2 - center_y)) / chunk_area
                weight2 = 1.0 - weight0 - weight1
                inside &= (weight0 >= 0) & (weight1 >= 0) & (weight2 >= 0)

                triangle_indices, sample_indices = np.nonzero(inside)

                if not len(triangle_indices):
                    continue

                triangles = chunk[triangle_indices]
                all_cells.append(cell_y[triangle_indices, sample_indices].astype(np.int64) * size_x +
                                 cell_x[triangle_indices, sample_indices].astype(np.int64))
                all_triangles.append(triangles)
                all_z.append(weight0[triangle_indices, sample_indices] * z[triangles, 0] +
                             weight1[triangle_indices, sample_indices] * z[triangles, 1] +
                             weight2[triangle_indices, sample_indices] * z[triangles, 2])

        if not all_cells:
            return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32)

        return np.concatenate(all_cells), np.concatenate(all_triangles), np.concatenate(all_z).astype(np.float32)

    # Grid operations

    @staticmethod
    def _shift(grid, dy, dx, fill):
        # Each cell gets the value of its neighbour at (dy, dx)
        height, width = grid.shape
        shifted = np.full_like(grid, fill)
        shifted[max(0, -dy):height - max(0, dy), max(0, -dx):width - max(0, dx)] = \
            grid[max(0, dy):height - max(0, -dy), max(0, dx):width - max(0, -dx)]
        return shifted

    NEIGHBOURS_4 = ((0, 1), (-1, 0), (0, -1), (1, 0))
    NEIGHBOURS_8 = ((0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0), (1, 1))

    @classmethod
    def _erode(cls, mask, radius=1, neighbours=NEIGHBOURS_8):
        for _ in range(radius):
            eroded = mask.copy()
            for dy, dx in neighbours:
                eroded &= cls._shift(mask, dy, dx, False)
            mask = eroded
        return mask

    @classmethod
    def _dilate(cls, mask, radius=1):
        for _ in range(radius):
            dilated = mask.copy()
            for dy, dx in cls.NEIGHBOURS_8:
                dilated |= cls._shift(mask, dy, dx, False)
            mask = dilated
        return mask

    @classmethod
    def _half_widths(cls, mask):
        # How many cells each cell is from the edge, alternating straight and diagonal steps
        distances = mask.astype(np.uint8)
        current = mask

        for i in range(cls.MAX_HALF_WIDTH):
            current = cls._erode(current, 1, cls.NEIGHBOURS_8 if i % 2 else cls.NEIGHBOURS_4)

            if not current.any():
                break

            distances += current

        return distances

    _thinning_tables = None

    @classmethod
    def _get_thinning_tables(cls):
        """
        Returns the cells to remove in each half of an iteration of the thinning algorithm of Guo
        and Hall, by the code of their 8 neighbours, which keeps lines one cell wide and connected.
        """
        if cls._thinning_tables is None:
            tables = (np.zeros(256, dtype=bool), np.zeros(256, dtype=bool))

            for code in range(256):
                # Neighbours from the east, counterclockwise
                p = [(code >> i) & 1 for i in range(8)]
                crossings = sum(1 for i in (0, 2, 4, 6) if not p[i] and (p[i + 1] or p[(i + 2) % 8]))
                n1 = sum(1 for k in (1, 3, 5, 7) if p[k] or p[k - 1])
                n2 = sum(1 for k in (1, 3, 5, 7) if p[k] or p[(k + 1) % 8])

                if crossings == 1 and 2 <= min(n1, n2) <= 3:
                    tables[0][code] = not ((p[1] or p[2] or not p[7]) and p[0])
                    tables[1][code] = not ((p[5] or p[6] or not p[3]) and p[4])

            cls._thinning_tables = tables

        return cls._thinning_tables

    @classmethod
    def _thin(cls, mask):
        tables = cls._get_thinning_tables()
        skeleton = np.pad(mask, 1)
        ys, xs = np.nonzero(skeleton)

        while True:
            removed = False

            for table in tables:
                # Only cells missing a straight neighbour can be removed
                border = ~(skeleton[ys - 1, xs] & skeleton[ys + 1, xs] & skeleton[ys, xs - 1] & skeleton[ys, xs + 1])
                border_ys, border_xs = ys[border], xs[border]
                codes = np.zeros(len(border_ys), dtype=np.uint8)

                # East, north-east, north, north-west, west, south-west, south and south-east
                for bit, (dy, dx) in enumerate(((0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0), (1, 1))):
                    codes |= skeleton[border_ys + dy, border_xs + dx].astype(np.uint8) << bit

                deleted = table[codes]

                if deleted.any():
                    skeleton[border_ys[deleted], border_xs[deleted]] = False
                    kept = np.ones(len(ys), dtype=bool)
                    kept[np.flatnonzero(border)[deleted]] = False
                    ys, xs = ys[kept], xs[kept]
                    removed = True

            if not removed:
                return skeleton[1:-1, 1:-1]

    @staticmethod
    def _to_cells(grid, positions):
        cells = np.floor(np.asarray(positions)[:, :2] - grid['origin']).astype(np.int64)
        height, width = grid['road'].shape
        inside = (cells[:, 0] >= 0) & (cells[:, 0] < width) & (cells[:, 1] >= 0) & (cells[:, 1] < height)
        return cells, inside

    @classmethod
    def _sample(cls, values, grid, positions):
        if not len(positions):
            return np.zeros(0, dtype=values.dtype)

        cells, inside = cls._to_cells(grid, positions)
        sampled = np.zeros(len(cells), dtype=values.dtype)
        sampled[inside] = values[cells[inside, 1], cells[inside, 0]]
        return sampled

    @classmethod
    def _is_line_on(cls, mask, grid, start, end):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        steps = max(2, int(length * 2) + 1)
        t = np.linspace(0.0, 1.0, steps)[:, None]
        points = np.asarray(start[:2])[None, :] * (1 - t) + np.asarray(end[:2])[None, :] * t
        cells, inside = cls._to_cells(grid, points)
        return bool(inside.all() and mask[cells[:, 1], cells[:, 0]].all())

    # Paths

    def _find_paths(self, floor, floor_heights, grid, settings):
        """
        Returns the nodes along the middle of the given floor and the links between them.
        """
        floor_heights = floor_heights.copy()
        mask = floor.copy()

        if settings['closing_radius']:
            radius = settings['closing_radius']
            closed = self._erode(self._dilate(mask, radius), radius)
            filled = closed & ~mask

            # Filled cells take the height of their highest neighbour
            for _ in range(radius):
                neighbour_heights = floor_heights.copy()
                for dy, dx in self.NEIGHBOURS_8:
                    neighbour_heights = np.maximum(neighbour_heights, self._shift(floor_heights, dy, dx, -np.inf))
                floor_heights[filled] = neighbour_heights[filled]

            mask = closed & (floor_heights > -np.inf)

        if settings['opening_radius']:
            radius = settings['opening_radius']
            mask &= self._dilate(self._erode(mask, radius), radius)

        # Where a floor passes over another one, the lower one is cut, so they are not joined
        heights = np.where(mask, floor_heights, np.nan)
        cut = np.zeros_like(mask)

        for dy, dx in self.NEIGHBOURS_4:
            with np.errstate(invalid='ignore'):
                cut |= self._shift(heights, dy, dx, np.nan) - heights > self.MAX_STEP

        mask &= ~cut

        half_widths = self._half_widths(mask)
        skeleton = self._thin(mask)
        graph = self._trace_skeleton(skeleton, floor_heights, half_widths, grid['origin'])
        self._prune_graph(graph, settings)
        positions, half_widths, links = self._lay_nodes(graph, settings)

        raw_mask = floor | mask
        links = self._close_gaps(positions, links, raw_mask, grid, settings)
        positions, half_widths, links = self._remove_small_networks(positions, half_widths, links,
                                                                     settings['min_network_length'])

        return {'positions': positions, 'half_widths': half_widths, 'links': links}

    def _trace_skeleton(self, skeleton, floor_heights, half_widths, origin):
        """
        Turns the cells of the skeleton into a graph whose nodes are its junctions and ends, and
        whose edges are the chains of cells between them.
        """
        height, width = skeleton.shape
        ys, xs = np.nonzero(skeleton)
        count = len(ys)
        index = np.full(skeleton.shape, -1, dtype=np.int64)
        index[ys, xs] = np.arange(count)
        z = floor_heights[ys, xs]

        def lookup(dy, dx):
            ny, nx = ys + dy, xs + dx
            inside = (ny >= 0) & (ny < height) & (nx >= 0) & (nx < width)
            found = np.full(count, -1, dtype=np.int64)
            found[inside] = index[ny[inside], nx[inside]]
            return found

        neighbours = [[] for _ in range(count)]

        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            other = lookup(dy, dx)
            linked = other >= 0

            # Diagonal neighbours are only linked when no straight neighbour links them already
            if dy and dx:
                linked &= (lookup(0, dx) < 0) & (lookup(dy, 0) < 0)

            linked[linked] &= np.abs(z[other[linked]] - z[linked]) <= self.MAX_STEP

            for a, b in zip(np.flatnonzero(linked).tolist(), other[linked].tolist()):
                neighbours[a].append(b)
                neighbours[b].append(a)

        degrees = [len(cell_neighbours) for cell_neighbours in neighbours]

        # Junction cells next to each other are the same junction
        parents = list(range(count))

        def find(cell):
            while parents[cell] != cell:
                parents[cell] = parents[parents[cell]]
                cell = parents[cell]
            return cell

        for cell in range(count):
            if degrees[cell] >= 3:
                for other in neighbours[cell]:
                    if degrees[other] >= 3:
                        parents[find(cell)] = find(other)

        graph_nodes = []
        node_of_cell = {}
        node_of_root = {}

        def add_node(cell):
            root = find(cell)

            if root not in node_of_root:
                node_of_root[root] = len(graph_nodes)
                graph_nodes.append([])

            node_of_cell[cell] = node_of_root[root]
            graph_nodes[node_of_root[root]].append(cell)

        for cell in range(count):
            if degrees[cell] != 2:
                add_node(cell)

        edges = []
        in_chain = np.zeros(count, dtype=bool)
        followed = set()

        def follow(start, first):
            chain = [start, first]
            previous, current = start, first

            while current not in node_of_cell:
                current_neighbours = neighbours[current]
                previous, current = current, (current_neighbours[0] if current_neighbours[0] != previous else current_neighbours[1])
                chain.append(current)

            followed.add((current, previous))
            in_chain[chain] = True
            return chain

        for start in list(node_of_cell):
            for first in neighbours[start]:
                if (start, first) in followed:
                    continue

                followed.add((start, first))
                chain = follow(start, first)
                a, b = node_of_cell[chain[0]], node_of_cell[chain[-1]]

                # Links between the cells of the same junction
                if a == b and len(chain) <= 3:
                    continue

                edges.append([a, b, chain])

        # Rings without any junction or end
        for cell in range(count):
            if not in_chain[cell] and degrees[cell] == 2:
                add_node(cell)
                followed.add((cell, neighbours[cell][0]))
                chain = follow(cell, neighbours[cell][0])
                edges.append([node_of_cell[cell], node_of_cell[cell], chain])

        cell_positions = np.stack((origin[0] + xs + 0.5, origin[1] + ys + 0.5, z), axis=1)
        node_positions = np.array([cell_positions[cells].mean(axis=0) for cells in graph_nodes]).reshape(-1, 3)
        node_half_widths = np.array([half_widths[ys[cells], xs[cells]].max() for cells in graph_nodes], dtype=np.float32)

        return {'cell_positions': cell_positions, 'cell_half_widths': half_widths[ys, xs].astype(np.float32),
                'node_positions': node_positions, 'node_half_widths': node_half_widths, 'edges': edges}

    @staticmethod
    def _chain_length(cell_positions, chain):
        points = cell_positions[chain, :2]
        return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())

    def _prune_graph(self, graph, settings):
        cell_positions = graph['cell_positions']
        node_half_widths = graph['node_half_widths']
        edges = graph['edges']

        for edge in edges:
            edge.append(self._chain_length(cell_positions, edge[2]))

        for _ in range(3):
            degrees = np.zeros(len(graph['node_positions']), dtype=np.int64)

            for a, b, chain, length in edges:
                degrees[a] += 1
                degrees[b] += 1

            # Short branches out of a junction come from its corners, not from a road
            kept = []

            for edge in edges:
                a, b, chain, length = edge
                ends = sorted((a, b), key=lambda node: degrees[node])

                if a != b and degrees[ends[0]] == 1 and degrees[ends[1]] >= 3:
                    if length < max(settings['min_spur_length'], self.SPUR_WIDTH_FACTOR * node_half_widths[ends[1]]):
                        continue

                kept.append(edge)

            # Junctions joined by a short edge are the same junction
            parents = list(range(len(degrees)))

            def find(node):
                while parents[node] != node:
                    parents[node] = parents[parents[node]]
                    node = parents[node]
                return node

            for a, b, chain, length in kept:
                if a != b and degrees[a] >= 3 and degrees[b] >= 3 and length < settings['junction_merge_length']:
                    parents[find(a)] = find(b)

            # Of several edges between the same two nodes, which come from holes in the floor,
            # only the shortest one is kept
            shortest = {}

            for edge in kept:
                a, b = find(edge[0]), find(edge[1])
                edge[0], edge[1] = a, b

                if a == b and edge[3] < 4 * settings['junction_merge_length']:
                    continue

                key = (min(a, b), max(a, b))

                if a == b:
                    key = (a, b, len(shortest))

                if key not in shortest or edge[3] < shortest[key][3]:
                    shortest[key] = edge

            merged_positions = graph['node_positions'].copy()

            for node in range(len(parents)):
                root = find(node)

                if root != node:
                    merged_positions[root, :2] = (merged_positions[root, :2] + graph['node_positions'][node, :2]) / 2
                    node_half_widths[root] = max(node_half_widths[root], node_half_widths[node])

            graph['node_positions'] = merged_positions
            pruned = len(shortest) != len(edges)
            edges = list(shortest.values())

            if not pruned:
                break

        graph['edges'] = edges

    def _lay_nodes(self, graph, settings):
        cell_positions = graph['cell_positions']
        cell_half_widths = graph['cell_half_widths']
        positions = []
        half_widths = []
        node_of_graph_node = {}
        links = set()

        def add_node(position, half_width):
            positions.append(position)
            half_widths.append(half_width)
            return len(positions) - 1

        def graph_node(node):
            if node not in node_of_graph_node:
                node_of_graph_node[node] = add_node(graph['node_positions'][node], graph['node_half_widths'][node])
            return node_of_graph_node[node]

        for a, b, chain, length in graph['edges']:
            points = cell_positions[chain]
            kept = self._space_points(points, self._simplify(points[:, :2], settings['simplify_tolerance']),
                                      settings['min_link_length'], settings['max_link_length'])

            # Rings need at least three nodes
            if a == b and len(kept) < 4:
                continue

            nodes = [graph_node(a)]
            nodes += [add_node(points[i], cell_half_widths[chain[i]]) for i in kept[1:-1]]
            nodes.append(graph_node(b))

            for start, end in zip(nodes, nodes[1:]):
                if start != end:
                    links.add((min(start, end), max(start, end)))

        return (np.array(positions, dtype=np.float64).reshape(-1, 3),
                np.array(half_widths, dtype=np.float32), links)

    @staticmethod
    def _simplify(points, tolerance):
        # Douglas-Peucker, returning the indices of the points that are kept
        kept = {0, len(points) - 1}
        stack = [(0, len(points) - 1)]

        while stack:
            first, last = stack.pop()

            if last - first < 2:
                continue

            start, end = points[first], points[last]
            direction = end - start
            length = math.hypot(direction[0], direction[1])
            between = points[first + 1:last] - start

            if length > 1e-9:
                distances = np.abs(between[:, 0] * direction[1] - between[:, 1] * direction[0]) / length
            else:
                distances = np.linalg.norm(between, axis=1)

            farthest = int(np.argmax(distances))

            if distances[farthest] > tolerance:
                middle = first + 1 + farthest
                kept.add(middle)
                stack.append((first, middle))
                stack.append((middle, last))

        return sorted(kept)

    @staticmethod
    def _space_points(points, kept, min_length, max_length):
        distances = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(points[:, :2], axis=0), axis=1))))

        # Long stretches are split evenly, so no link is longer than the maximum
        spaced = [kept[0]]

        for start, end in zip(kept, kept[1:]):
            length = distances[end] - distances[start]
            pieces = int(math.ceil(length / max_length))

            for piece in range(1, pieces):
                target = distances[start] + length * piece / pieces
                index = int(np.searchsorted(distances, target))

                if spaced[-1] < index < end:
                    spaced.append(index)

            spaced.append(end)

        # Points too close to the previous one are dropped, except the last one
        result = [spaced[0]]

        for index in spaced[1:-1]:
            if distances[index] - distances[result[-1]] >= min_length and distances[spaced[-1]] - distances[index] >= min_length / 2:
                result.append(index)

        result.append(spaced[-1])
        return result

    @staticmethod
    def _spatial_index(positions, cell_size):
        buckets = {}

        for node, (x, y) in enumerate(positions[:, :2].tolist()):
            buckets.setdefault((int(x // cell_size), int(y // cell_size)), []).append(node)

        def nearby(x, y, radius):
            reach = int(math.ceil(radius / cell_size))
            bucket_x, bucket_y = int(x // cell_size), int(y // cell_size)

            for dx in range(-reach, reach + 1):
                for dy in range(-reach, reach + 1):
                    yield from buckets.get((bucket_x + dx, bucket_y + dy), ())

        return nearby

    @staticmethod
    def _neighbour_lists(count, links):
        neighbours = [[] for _ in range(count)]

        for a, b in links:
            neighbours[a].append(b)
            neighbours[b].append(a)

        return neighbours

    def _close_gaps(self, positions, links, raw_mask, grid, settings):
        """
        Links the dead ends that face another node across a short stretch of the same floor, as
        happens where a road passes under a bridge or the collision has a gap.
        """
        if not len(positions):
            return links

        gap_length = settings['gap_length']
        neighbours = self._neighbour_lists(len(positions), links)
        nearby = self._spatial_index(positions, gap_length)
        links = set(links)
        min_cos = math.cos(self.GAP_MAX_ANGLE)

        def within_hops(start, goal, hops):
            frontier = {start}
            seen = {start}

            for _ in range(hops):
                frontier = {other for node in frontier for other in neighbours[node]} - seen

                if goal in frontier:
                    return True

                seen |= frontier

            return False

        for end in range(len(positions)):
            if len(neighbours[end]) != 1:
                continue

            outward = positions[end, :2] - positions[neighbours[end][0], :2]
            outward_length = math.hypot(*outward)

            if outward_length < 1e-6:
                continue

            outward /= outward_length
            best, best_distance = None, gap_length

            for other in nearby(positions[end, 0], positions[end, 1], gap_length):
                if other == end or other in neighbours[end]:
                    continue

                offset = positions[other] - positions[end]
                distance = math.hypot(offset[0], offset[1])

                if (distance < 1e-6 or distance >= best_distance or
                        (offset[0] * outward[0] + offset[1] * outward[1]) / distance < min_cos or
                        abs(offset[2]) > 2.0 + 0.1 * distance):
                    continue

                if within_hops(end, other, self.GAP_MAX_HOPS):
                    continue

                if not self._is_gap_crossable(raw_mask, grid, positions[end], positions[other],
                                              settings['gap_off_floor_length']):
                    continue

                best, best_distance = other, distance

            if best is not None:
                links.add((min(end, best), max(end, best)))
                neighbours[end].append(best)
                neighbours[best].append(end)

        return links

    @classmethod
    def _is_gap_crossable(cls, floor, grid, start, end, max_off_floor):
        """
        Whether the way between two nodes is on the same floor, or on other ground at the same
        height for a short stretch, as where two pieces of road meet.
        """
        SAMPLES_PER_UNIT = 2

        length = math.hypot(end[0] - start[0], end[1] - start[1])
        t = np.linspace(0.0, 1.0, max(2, int(length * SAMPLES_PER_UNIT) + 1))
        points = np.asarray(start)[None, :] * (1 - t[:, None]) + np.asarray(end)[None, :] * t[:, None]
        cells, inside = cls._to_cells(grid, points)

        if not inside.all():
            return False

        on_floor = floor[cells[:, 1], cells[:, 0]]
        on_ground = np.abs(grid['ground_heights'][cells[:, 1], cells[:, 0]] - points[:, 2]) <= cls.MAX_STEP

        if not (on_floor | on_ground).all():
            return False

        # Longest stretch off the floor
        off_floor = np.concatenate(([0], (~on_floor).astype(np.int8), [0]))
        changes = np.flatnonzero(np.diff(off_floor))
        longest = (changes[1::2] - changes[::2]).max() if len(changes) else 0
        return longest / SAMPLES_PER_UNIT <= max_off_floor

    def _remove_small_networks(self, positions, half_widths, links, min_length):
        count = len(positions)
        parents = list(range(count))

        def find(node):
            while parents[node] != node:
                parents[node] = parents[parents[node]]
                node = parents[node]
            return node

        for a, b in links:
            parents[find(a)] = find(b)

        network_lengths = {}

        for a, b in links:
            root = find(a)
            network_lengths[root] = network_lengths.get(root, 0.0) + math.hypot(*(positions[a, :2] - positions[b, :2]))

        kept = [node for node in range(count) if network_lengths.get(find(node), 0.0) >= min_length]
        new_index = {node: i for i, node in enumerate(kept)}
        links = {(new_index[a], new_index[b]) for a, b in links if a in new_index and b in new_index}

        return positions[kept].reshape(-1, 3), half_widths[kept], links

    def _add_crossings(self, pedestrians, vehicles, grid):
        """
        Links the pavements on both sides of the roads near the junctions, so pedestrians can
        cross them.
        """
        positions = pedestrians['positions']
        crossings = set()

        if not len(positions) or not len(vehicles['positions']):
            return crossings

        vehicle_neighbours = self._neighbour_lists(len(vehicles['positions']), vehicles['links'])
        junctions = vehicles['positions'][[node for node, others in enumerate(vehicle_neighbours) if len(others) >= 3]]

        if not len(junctions):
            return crossings

        near_junction = self._spatial_index(junctions, self.CROSSING_JUNCTION_DISTANCE)
        vehicle_links = list(vehicles['links'])
        link_middles = np.array([(vehicles['positions'][a] + vehicles['positions'][b]) / 2 for a, b in vehicle_links]).reshape(-1, 3)
        near_link = self._spatial_index(link_middles, self.CROSSING_MAX_LENGTH)
        nearby = self._spatial_index(positions, self.CROSSING_MAX_LENGTH)
        walkable = grid['road'] | grid['pavement']

        # Pavements already joined do not need a crossing between them
        parents = list(range(len(positions)))

        def find(node):
            while parents[node] != node:
                parents[node] = parents[parents[node]]
                node = parents[node]
            return node

        for a, b in pedestrians['links']:
            parents[find(a)] = find(b)

        def closest_road_direction(point):
            best, best_distance = None, math.inf

            for link in near_link(point[0], point[1], self.CROSSING_MAX_LENGTH):
                start = vehicles['positions'][vehicle_links[link][0], :2]
                end = vehicles['positions'][vehicle_links[link][1], :2]
                direction = end - start
                length_squared = float(direction @ direction)

                if length_squared < 1e-9:
                    continue

                t = min(1.0, max(0.0, float((point - start) @ direction) / length_squared))
                distance = math.hypot(*(start + direction * t - point))

                if distance < best_distance:
                    best, best_distance = direction / math.sqrt(length_squared), distance

            return best

        candidates = []

        for start in range(len(positions)):
            for end in nearby(positions[start, 0], positions[start, 1], self.CROSSING_MAX_LENGTH):
                if end <= start or find(start) == find(end):
                    continue

                offset = positions[end] - positions[start]
                length = math.hypot(offset[0], offset[1])

                if not self.CROSSING_MIN_LENGTH <= length <= self.CROSSING_MAX_LENGTH or abs(offset[2]) > self.MAX_STEP:
                    continue

                middle = (positions[start, :2] + positions[end, :2]) / 2

                if not any(math.hypot(*(junctions[junction, :2] - middle)) <= self.CROSSING_JUNCTION_DISTANCE
                           for junction in near_junction(middle[0], middle[1], self.CROSSING_JUNCTION_DISTANCE)):
                    continue

                candidates.append((length, start, end, middle, offset[:2] / length))

        candidates.sort(key=lambda candidate: candidate[0])
        crossing_ends = []

        for length, start, end, middle, direction in candidates:
            if any(math.hypot(*(positions[node, :2] - positions[other, :2])) < self.CROSSING_SPACING
                   for node in (start, end) for other in crossing_ends):
                continue

            road_direction = closest_road_direction(middle)

            if road_direction is None or abs(float(road_direction @ direction)) > math.cos(self.CROSSING_MIN_ANGLE):
                continue

            if not self._is_line_on(walkable, grid, positions[start], positions[end]):
                continue

            # Most of the way has to be over the road
            t = np.linspace(0.0, 1.0, max(2, int(length * 2) + 1))[:, None]
            points = positions[start, :2] * (1 - t) + positions[end, :2] * t
            if self._sample(grid['road'], grid, points).mean() < self.CROSSING_MIN_ROAD_SHARE:
                continue

            crossings.add((start, end))
            crossing_ends += [start, end]

        pedestrians['links'] = pedestrians['links'] | crossings
        return crossings

    # Node files

    def _read_base_node_files(self, grid_width, footprint):
        """
        Returns, for each tile, the node file the game would load for it. A mod in modloader
        with most of its nodes around the map on its roads or pavements is an older version
        of it, so its files are skipped and the files they replace are used instead.
        """
        sources = []
        gta3_path = os.path.join(self.models_dir, 'gta3.img')

        if os.path.isfile(gta3_path):
            sources.append(('gta3.img', gta3_path, False))

        if os.path.isdir(self.modloader_dir):
            for mod_directory in sorted(os.listdir(self.modloader_dir)):
                mod_directory_path = os.path.join(self.modloader_dir, mod_directory)

                # Modloader ignores the folders whose name starts with a dot
                if not os.path.isdir(mod_directory_path) or mod_directory.startswith('.'):
                    continue

                for root, dirs, files in os.walk(mod_directory_path):
                    for file_name in sorted(files):
                        file_path = os.path.join(root, file_name)

                        if file_name.lower().endswith('.img') or self.NODE_FILE_PATTERN.match(file_name):
                            sources.append((mod_directory, file_path, True))

        candidates = {}
        nodes_around = {}
        nodes_on_footprint = {}

        for mod, file_path, from_modloader in sources:
            if file_path.lower().endswith('.img'):
                archive = ImgArchive(file_path)
                self._archives.append(archive)
                entries = [(name, lambda archive=archive, name=name: archive.read(name))
                           for name in archive.entries if self.NODE_FILE_PATTERN.match(name)]
            else:
                entries = [(os.path.basename(file_path).lower(), lambda file_path=file_path: self._read_file(file_path))]

            for name, read in entries:
                area = int(self.NODE_FILE_PATTERN.match(name).group(1))

                try:
                    base_file = self._parse_node_file(f'nodes{area}.dat', read(), grid_width)
                except PathPositioner.UnsupportedFormatError as e:
                    print(f'(paths) {e} Its nodes will be replaced ({file_path})')
                    base_file = None

                candidates.setdefault(area, []).append((mod, base_file, from_modloader))

                if base_file and from_modloader:
                    around, on_footprint = self._count_nodes_on_footprint(base_file, footprint)
                    nodes_around[mod] = nodes_around.get(mod, 0) + around
                    nodes_on_footprint[mod] = nodes_on_footprint.get(mod, 0) + on_footprint

        older_versions = {mod for mod, around in nodes_around.items()
                          if around >= self.OLDER_VERSION_MIN_NODES and
                          nodes_on_footprint[mod] >= self.OLDER_VERSION_SHARE * around}

        for mod in sorted(older_versions):
            print(f'(paths) Skipping the nodes of {mod}, which are on the roads of this map, as it looks like an older version of it')

        base_files = {}

        for area, area_candidates in candidates.items():
            # Later sources replace earlier ones, as modloader does with the files of the game.
            # Empty files add nothing, so the nodes of the files they would replace are kept
            for mod, base_file, from_modloader in reversed(area_candidates):
                if base_file is not None and not (from_modloader and mod in older_versions):
                    base_files[area] = base_file
                    break

        return base_files

    @staticmethod
    def _read_file(file_path):
        with open(file_path, 'rb') as f:
            return f.read()

    def _parse_node_file(self, file_name, data, grid_width):
        layout = self._positioner._detect_layout(file_name, data)
        counts = self._positioner._read_counts(data, layout)

        if not any(counts):
            return None

        # Original node files can only be used in the original 8x8 grid
        if layout is PathPositioner.LAYOUT_VANILLA and grid_width != self.VANILLA_GRID_WIDTH:
            return None

        base_file = {'name': file_name, 'data': data, 'layout': layout, 'counts': counts, 'is_empty': False,
                     'version': data[20:24] if layout is not PathPositioner.LAYOUT_VANILLA else None}
        sections = self._positioner._get_sections(base_file)
        base_file['sections'] = sections
        links_count = counts[4]
        base_file['data'] = data.ljust(sections[4] + 2 * links_count, b'\x00')
        return base_file

    def _node_records(self, base_file):
        layout = base_file['layout']
        nodes_count = base_file['counts'][0]
        start = base_file['sections'][0]
        return np.frombuffer(base_file['data'], dtype=np.uint8, count=nodes_count * layout['node_size'],
                             offset=start).reshape(nodes_count, layout['node_size'])

    def _node_positions(self, base_file):
        layout = base_file['layout']
        records = self._node_records(base_file)
        offset = layout['node_pos']
        size = struct.calcsize(layout['pos_format'])
        dtype = '<i2' if size == 2 else '<i4'
        x = records[:, offset:offset + size].copy().view(dtype).ravel()
        y = records[:, offset + size:offset + 2 * size].copy().view(dtype).ravel()
        return np.stack((x, y), axis=1) / self.COORD_SCALE

    def _count_nodes_on_footprint(self, base_file, footprint):
        # How many nodes are around the map, and how many of them on its roads or pavements
        positions = self._node_positions(base_file)
        cells, inside = self._to_cells(footprint, positions)
        return int(inside.sum()), int(footprint['mask'][cells[inside, 1], cells[inside, 0]].sum())

    def _flood_fills(self, count, links, first):
        parents = list(range(count))

        def find(node):
            while parents[node] != node:
                parents[node] = parents[parents[node]]
                node = parents[node]
            return node

        for a, b in links:
            parents[find(a)] = find(b)

        groups = {}
        flood_fills = []

        for node in range(count):
            root = find(node)

            if root not in groups:
                groups[root] = (first + len(groups) - 1) % self.MAX_FLOOD_FILL + 1

            flood_fills.append(groups[root])

        return flood_fills, first + len(groups)

    def _write_node_files(self, vehicles, pedestrians, grid, grid_width, output_dir):
        half_map = grid_width * self.TILE_SIZE / 2

        def area_of(x, y):
            column = int((x + half_map) // self.TILE_SIZE)
            row = int((y + half_map) // self.TILE_SIZE)

            if 0 <= column < grid_width and 0 <= row < grid_width:
                return row * grid_width + column

            return None

        footprint = {'origin': grid['origin'], 'road': grid['road'],
                     'mask': self._dilate(grid['road'] | grid['pavement'], 2)}
        base_files = self._read_base_node_files(grid_width, footprint)

        # Every node of the map, the vehicle nodes first
        vehicle_count = len(vehicles['positions'])
        positions = np.concatenate((vehicles['positions'], pedestrians['positions'])).reshape(-1, 3)
        half_widths = np.concatenate((vehicles['half_widths'], pedestrians['half_widths']))
        is_vehicle = np.arange(len(positions)) < vehicle_count
        dirt = np.concatenate((vehicles['dirt'], np.zeros(len(pedestrians['positions']), dtype=bool)))
        links = set(vehicles['links'])
        links |= {(a + vehicle_count, b + vehicle_count) for a, b in pedestrians['links']}
        crossings = {(a + vehicle_count, b + vehicle_count) for a, b in pedestrians['crossings']}

        areas = [area_of(x, y) for x, y in positions[:, :2].tolist()]
        outside = sum(area is None for area in areas)

        if outside:
            print(f'(paths) {outside} nodes are outside of the paths map, skipping them...')

        links = {(a, b) for a, b in links if areas[a] is not None and areas[b] is not None}
        neighbours = self._neighbour_lists(len(positions), links)

        for node, others in enumerate(neighbours):
            if len(others) > self.MAX_LINKS:
                # The farthest links are dropped, as a node cannot have more
                others.sort(key=lambda other: math.hypot(*(positions[other, :2] - positions[node, :2])))
                for other in others[self.MAX_LINKS:]:
                    neighbours[other].remove(node)
                    links.discard((min(node, other), max(node, other)))
                del others[self.MAX_LINKS:]

        # Nodes that can reach each other share a flood fill group, new ones after the game's own.
        # Vehicles and pedestrians never share a route, so each has its own groups
        first_flood_fill = 1 + max((int(self._node_records(base_file)[:, 23].max()) for base_file in base_files.values()
                                    if base_file['counts'][0]), default=0)
        vehicle_links = {(a, b) for a, b in links if a < vehicle_count}
        vehicle_flood_fills, next_vehicle_flood_fill = self._flood_fills(vehicle_count, vehicle_links, first_flood_fill)
        pedestrian_flood_fills, next_pedestrian_flood_fill = self._flood_fills(
            len(positions) - vehicle_count, {(a - vehicle_count, b - vehicle_count) for a, b in links if a >= vehicle_count},
            first_flood_fill)
        flood_fills = vehicle_flood_fills + pedestrian_flood_fills

        # Node IDs, the vehicle nodes of each tile before its pedestrian nodes
        def base_counts(area):
            base_file = base_files.get(area)
            return base_file['counts'] if base_file else (0, 0, 0, 0, 0)

        new_nodes = {}

        for node in range(len(positions)):
            if areas[node] is not None and neighbours[node]:
                new_nodes.setdefault(areas[node], ([], []))[0 if is_vehicle[node] else 1].append(node)

        node_ids = {}
        added_vehicles = {}

        for area, (area_vehicles, area_pedestrians) in new_nodes.items():
            nodes_count, vehicles_count, pedestrians_count = base_counts(area)[:3]
            added_vehicles[area] = len(area_vehicles)

            for i, node in enumerate(area_vehicles):
                node_ids[node] = (area, vehicles_count + i)
            for i, node in enumerate(area_pedestrians):
                node_ids[node] = (area, vehicles_count + len(area_vehicles) + pedestrians_count + i)

        # Each vehicle link has a navi node halfway, pointing to the first of its nodes
        navis = {}
        navi_ids = {}

        for a, b in sorted(vehicle_links):
            if a not in node_ids or b not in node_ids:
                continue

            middle = (positions[a] + positions[b]) / 2
            area = area_of(middle[0], middle[1])
            area = areas[a] if area is None or area not in new_nodes else area
            area_navis = navis.setdefault(area, [])
            navi_ids[(a, b)] = (area, base_counts(area)[3] + len(area_navis))

            direction = positions[a, :2] - middle[:2]
            direction = direction / max(math.hypot(*direction), 1e-6)
            road_width = 2 * min(half_widths[a], half_widths[b])
            lanes = int(min(self.MAX_LANES, max(1, round(road_width / (2 * self.LANE_WIDTH)))))
            area_navis.append({'position': middle, 'node': node_ids[a], 'direction': direction,
                               'flags': (lanes << self.LEFT_LANES_SHIFT) | (lanes << self.RIGHT_LANES_SHIFT)})

        # Pedestrian nodes of the tiles that get new vehicle nodes move up, along with the links
        # that point to them in every file
        shifts = {area: (base_counts(area)[1], base_counts(area)[0], len(area_vehicles), len(area_pedestrians))
                  for area, (area_vehicles, area_pedestrians) in new_nodes.items()}
        changed_areas = set(new_nodes)

        for area, base_file in base_files.items():
            if area not in changed_areas and shifts and self._remap_links(base_file, shifts) is not None:
                changed_areas.add(area)

        # Files are only written once all of them could be made, so no half of the paths is left
        contents = {}

        for area in sorted(changed_areas):
            base_file = base_files.get(area)

            if base_file:
                layout = base_file['layout']
            else:
                layout = PathPositioner.LAYOUT_VANILLA if grid_width == self.VANILLA_GRID_WIDTH else PathPositioner.LAYOUT_FM92_VER2

            area_vehicles, area_pedestrians = new_nodes.get(area, ([], []))
            area_navis = navis.get(area, [])
            counts = base_counts(area)
            links_count = counts[4]
            is_vanilla = layout is PathPositioner.LAYOUT_VANILLA

            if is_vanilla and counts[3] + len(area_navis) > self.VANILLA_MAX_NAVIS:
                raise self.GenerationError(f'nodes{area}.dat would have {counts[3] + len(area_navis)} navi nodes, '
                                           f'more than the {self.VANILLA_MAX_NAVIS} the original format can hold. '
                                           f'Move the map away from the roads of that tile.')

            node_records = []
            link_records, navi_link_records, length_records, flag_records = [], [], [], []

            for node in area_vehicles + area_pedestrians:
                node_links = sorted(neighbours[node])
                width = 0 if is_vehicle[node] else self.PEDESTRIAN_WIDTH
                flags = len(node_links) | self.SPAWN_PROBABILITY

                if is_vehicle[node]:
                    flags |= self.NOT_HIGHWAY
                    if dirt[node]:
                        flags |= self.DIRT_ROAD_TRAFFIC_LEVEL << self.TRAFFIC_LEVEL_SHIFT

                node_records.append(self._pack_node(layout, positions[node], links_count + len(link_records),
                                                    node_ids[node], width, flood_fills[node], flags))

                for other in node_links:
                    link = (min(node, other), max(node, other))
                    link_records.append(struct.pack('<2H', *node_ids[other]))
                    navi = navi_ids.get(link)
                    navi_link_records.append(self._pack_navi_link(layout, navi))
                    length_records.append(min(self.MAX_LINK_LENGTH, int(round(math.hypot(*(positions[other] - positions[node]))))))
                    flag_records.append(self.ROAD_CROSSING if link in crossings else 0)

            navi_records = [self._pack_navi(layout, navi) for navi in area_navis]

            contents[area] = self._build_node_file(area, base_file, layout, shifts,
                                                   node_records[:len(area_vehicles)], node_records[len(area_vehicles):],
                                                   navi_records, link_records, navi_link_records,
                                                   bytes(length_records), bytes(flag_records))

        os.makedirs(output_dir, exist_ok=True)

        for area, content in contents.items():
            with open(os.path.join(output_dir, f'nodes{area}.dat'), 'wb') as node_file:
                node_file.write(content)

        if max(next_vehicle_flood_fill, next_pedestrian_flood_fill) > self.MAX_FLOOD_FILL + 1:
            print('(paths) There are more path networks than flood fill groups, some of them share a group')

        return len(contents)

    def _pack_node(self, layout, position, link_id, node_id, width, flood_fill, flags):
        x, y, z = (int(round(value * self.COORD_SCALE)) for value in position)
        area, node = node_id

        if link_id > 0xFFFF:
            raise self.GenerationError(f'nodes{area}.dat would have more links than its format can hold.')

        if layout is PathPositioner.LAYOUT_VANILLA:
            limit = 1 << 15
            x, y, z = (max(-limit, min(limit - 1, value)) for value in (x, y, z))
            record = struct.pack('<4sI3hhHHHBBI', self.GENERATED_NODE_MARKER, 0, x, y, z, self.HEURISTIC_COST,
                                 link_id, area, node, width, flood_fill, flags)
        else:
            record = struct.pack('<4sI3hhHHHBBI3i', self.GENERATED_NODE_MARKER, 0, 0, 0, 0, self.HEURISTIC_COST,
                                 link_id, area, node, width, flood_fill, flags, x, y, z)

        return record.ljust(layout['node_size'], b'\x00')

    def _pack_navi(self, layout, navi):
        x, y = (int(round(value * self.COORD_SCALE)) for value in navi['position'][:2])
        area, node = navi['node']
        direction_x, direction_y = (max(-100, min(100, int(round(value * 100)))) for value in navi['direction'])

        if layout is PathPositioner.LAYOUT_VANILLA:
            return struct.pack('<2h2H2bI', x, y, area, node, direction_x, direction_y, navi['flags'])

        return struct.pack('<2h2H2bI2i', 0, 0, area, node, direction_x, direction_y, navi['flags'], x, y)

    def _pack_navi_link(self, layout, navi):
        # Pedestrian links have no navi node
        area, navi_id = navi if navi else (0, 0)

        if layout is PathPositioner.LAYOUT_VANILLA:
            return struct.pack('<H', (area << self.VANILLA_NAVI_AREA_SHIFT) | navi_id)

        return struct.pack('<2H', navi_id, area)

    def _remap_links(self, base_file, shifts):
        """
        Returns the links of a node file with the pedestrian nodes of the shifted tiles moved
        up, or None if none of them changes.
        """
        links_count = base_file['counts'][4]
        links_start = base_file['sections'][2]
        links = np.frombuffer(base_file['data'], dtype='<u2', count=links_count * 2, offset=links_start).reshape(-1, 2).copy()
        node_ids = links[:, 1].astype(np.int64)

        for area, (vehicles_count, nodes_count, added_vehicles, added_pedestrians) in shifts.items():
            in_area = links[:, 0] == area
            pedestrians = in_area & (links[:, 1] >= vehicles_count) & (links[:, 1] < nodes_count)
            # Links to nodes the file does not have keep pointing past its last node
            missing = in_area & (links[:, 1] >= nodes_count)
            node_ids[pedestrians] += added_vehicles
            node_ids[missing] += added_vehicles + added_pedestrians

        node_ids = np.minimum(node_ids, 0xFFFF)

        if np.array_equal(node_ids, links[:, 1]):
            return None

        links[:, 1] = node_ids
        return links.tobytes()

    def _build_node_file(self, area, base_file, layout, shifts, vehicle_records, pedestrian_records,
                         navi_records, link_records, navi_link_records, lengths, flags):
        counts = [0, 0, 0, 0, 0]
        base_vehicles = base_pedestrians = base_navis = base_links = base_navi_links = b''
        base_lengths = base_flags = b''
        filler = self.FILLER

        if base_file:
            data = base_file['data']
            node_size = layout['node_size']
            nodes_count, vehicles_count, pedestrians_count, navis_count, links_count = base_file['counts']
            nodes, navis, links, navi_links, end = base_file['sections']
            counts = list(base_file['counts'])

            base_vehicles = data[nodes:nodes + vehicles_count * node_size]
            records = self._node_records(base_file)[vehicles_count:].copy()

            # The pedestrian nodes of this tile come after its new vehicle nodes
            if area in shifts:
                node_ids = records[:, 20:22].copy().view('<u2').ravel() + shifts[area][2]
                records[:, 20:22] = node_ids.astype('<u2').view(np.uint8).reshape(-1, 2)

            base_pedestrians = records.tobytes()
            base_navis = data[navis:links]
            base_links = self._remap_links(base_file, shifts) or data[links:links + links_count * 4]
            filler = data[links + links_count * 4:navi_links]
            base_navi_links = data[navi_links:end]
            base_lengths = data[end:end + links_count]
            base_flags = data[end + links_count:end + 2 * links_count]

        counts[0] += len(vehicle_records) + len(pedestrian_records)
        counts[1] += len(vehicle_records)
        counts[2] += len(pedestrian_records)
        counts[3] += len(navi_records)
        counts[4] += len(link_records)

        if layout is PathPositioner.LAYOUT_VANILLA:
            content = bytearray()
        else:
            content = bytearray(PathPositioner.FM92_PREFIX + ((base_file or {}).get('version') or b'VER2'))

        content += struct.pack('<5I', *counts)
        content += base_vehicles + b''.join(vehicle_records)
        content += base_pedestrians + b''.join(pedestrian_records)
        content += base_navis + b''.join(navi_records)
        content += base_links + b''.join(link_records)
        content += filler
        content += base_navi_links + b''.join(navi_link_records)
        content += base_lengths + lengths
        content += base_flags + flags
        content += b'\x00' * PathPositioner.TRAILER_SIZE

        if layout is not PathPositioner.LAYOUT_VANILLA:
            content += PathPositioner.FM92_EOF

        return bytes(content)
