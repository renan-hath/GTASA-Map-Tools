import io
import math
import os
import re
import struct
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import shared_memory

import numpy as np
from PIL import Image

from application.tools.procobj_converter import ProcObjConverter

# The generator and the scene of the process that is drawing blocks for another one
_block_worker = None


def _start_block_worker(state, scene_specs):
    global _block_worker

    # The shared memory is kept too, as the arrays of the scene are only views of it
    memories = []
    scene = {}

    for name, (memory_name, shape, dtype) in scene_specs.items():
        memory = shared_memory.SharedMemory(name=memory_name)
        memories.append(memory)
        scene[name] = np.ndarray(shape, dtype=dtype, buffer=memory.buf)

    radar_generator = RadarGenerator.__new__(RadarGenerator)
    radar_generator.__dict__.update(state)
    _block_worker = (radar_generator, scene, memories)


def _draw_block(block, style):
    radar_generator, scene, memories = _block_worker
    return radar_generator._render_block(block, scene, style)


class ImgArchive:
    """
    Reads the entries of a version 2 IMG archive, which is the one GTA San Andreas uses.
    """

    SECTOR_SIZE = 2048
    ENTRY_LENGTH = 32

    def __init__(self, file_path):
        self.file_path = file_path
        self.entries = {}
        self._file = None

        with open(file_path, 'rb') as img_file:
            header = img_file.read(8)

            if len(header) < 8 or header[:4] != b'VER2':
                print(f'Unsupported IMG format, skipping: {file_path}')
                return

            entries_count = struct.unpack_from('<I', header, 4)[0]
            directory = img_file.read(entries_count * self.ENTRY_LENGTH)

        for i in range(len(directory) // self.ENTRY_LENGTH):
            offset, streaming_size, archive_size, name = struct.unpack_from('<IHH24s', directory, i * self.ENTRY_LENGTH)
            name = name.split(b'\x00')[0].decode('ascii', errors='replace').lower()
            self.entries[name] = (offset * self.SECTOR_SIZE, (streaming_size or archive_size) * self.SECTOR_SIZE)

    def read(self, name):
        offset, size = self.entries[name]

        if self._file is None:
            self._file = open(self.file_path, 'rb')

        self._file.seek(offset)
        return self._file.read(size)

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None


class RadarGenerator:
    """
    Generates the radar tiles of the game, drawing every object the installed mods place on top of
    the radar of the original map.

    The radar is a grid of radarXX.txd files, numbered row by row from the north-west corner, each
    one covering 500x500 units of the map. The original map is 6000 units wide, so 12x12 tiles, and
    a bigger radar map size (fastman92 Limit Adjuster) adds tiles around it.

    The objects are drawn as the game would show them seen from above: their models are read from
    the DFF files, painted with the textures of their TXD files and shaded with their prelighting.
    Where several objects overlap, the highest one is the one that shows, and anything under the
    water level is shown as water.

    That is the realistic style. The vanilla style draws them as the radar of the original game
    does instead, with one flat color for each kind of ground: the kind comes from the surfaces
    of the collision of the objects, and from the color of their textures where the collision
    does not tell it. The objects without collision are not drawn in this style, except for the
    LODs that no object points to, which fill what the other objects leave empty.
    """

    STYLE_REALISTIC = 'realistic'
    STYLE_VANILLA = 'vanilla'

    TILE_WORLD_SIZE = 500
    VANILLA_MAP_SIZE = 6000
    VANILLA_TILES_PER_ROW = 12
    VANILLA_TILE_RESOLUTION = 256
    TILE_RESOLUTIONS = (128, 256, 512, 1024)
    SUPERSAMPLING = 2
    # The tiles are drawn in blocks of as many as fit in this many samples a side, up to this many
    MAX_BLOCK_TILES = 4
    MAX_BLOCK_RESOLUTION = 2048
    # Blocks are drawn by several processes at once. Each one needs its own memory to draw on
    MAX_WORKERS = 8
    # Textures are reduced to this size, enough for a pixel that covers about one unit of the map,
    # and to more than that when the tiles have more pixels than the ones of the original radar
    TEXTURE_SAMPLE_SIZE = 32
    MAX_TEXTURE_SAMPLE_SIZE = 64
    ALPHA_TEST = 128
    # The side, in samples, of the cells that tell which triangles reach the pixels that are needed
    NEEDED_CELL_SIZE = 16
    # The game lights the objects with the sun and the ambient light on top of their prelighting,
    # so the prelighting alone would leave them much darker than they look
    AMBIENT_LIGHT = 0.35
    PRELIGHT_SCALE = 1.0
    RASTER_CHUNK_SAMPLES = 1 << 18
    # Triangles are drawn in groups whose bounding boxes are rounded up to one of these sizes
    BUCKET_SIZES = tuple(range(1, 8)) + tuple(size << shift for shift in range(10) for size in (8, 10, 12))
    TXD_NAME_LENGTH = 32
    PREVIEW_MAX_RESOLUTION = 4096

    RW_VERSION = 0x1803FFFF
    RW_STRUCT = 0x01
    RW_STRING = 0x02
    RW_EXTENSION = 0x03
    RW_TEXTURE = 0x06
    RW_MATERIAL = 0x07
    RW_MATERIAL_LIST = 0x08
    RW_FRAME_LIST = 0x0E
    RW_GEOMETRY = 0x0F
    RW_CLUMP = 0x10
    RW_ATOMIC = 0x14
    RW_TEXTURE_NATIVE = 0x15
    RW_TEXTURE_DICTIONARY = 0x16
    RW_GEOMETRY_LIST = 0x1A
    RW_BIN_MESH = 0x50E
    RW_FRAME_NAME = 0x253F2FE

    GEOMETRY_TEXTURED = 0x04
    GEOMETRY_PRELIT = 0x08
    GEOMETRY_TEXTURED2 = 0x80
    GEOMETRY_NATIVE = 0x01000000

    # Interior 13 is shown everywhere, including outside
    EXTERIOR_INTERIORS = (0, 13)

    # Kinds of ground of the vanilla style
    KIND_NONE = 0
    KIND_UNKNOWN = 1
    KIND_STRUCTURE = 2
    KIND_ROAD = 3
    KIND_CONCRETE = 4
    KIND_BUILDING = 5
    KIND_DARK_GRASS = 6
    KIND_LIGHT_GRASS = 7
    KIND_SAND = 8
    KIND_DESERT = 9
    KIND_DIRT = 10
    KIND_ROCK = 11
    KIND_WATER = 12
    KIND_RAILWAY = 13

    # The colors the radar of the original game uses the most. Water is not here, as it is read
    # from the radar itself
    VANILLA_PALETTE = {
        KIND_NONE: (0, 0, 0),
        KIND_UNKNOWN: (161, 160, 161),
        KIND_STRUCTURE: (161, 160, 161),
        KIND_ROAD: (0, 0, 0),
        KIND_CONCRETE: (161, 160, 161),
        KIND_BUILDING: (255, 255, 255),
        KIND_DARK_GRASS: (57, 106, 41),
        KIND_LIGHT_GRASS: (123, 139, 57),
        KIND_SAND: (231, 195, 99),
        KIND_DESERT: (156, 136, 115),
        KIND_DIRT: (115, 102, 82),
        KIND_ROCK: (161, 160, 161),
        KIND_RAILWAY: (74, 12, 0),
    }

    # The surfaces of each kind. The surface that says nothing (DEFAULT) is unknown, and every
    # other one that is not here is part of a structure
    SURFACE_KINDS = {
        KIND_ROAD: ('TARMAC', 'TARMAC_FUCKED', 'TARMAC_REALLYFUCKED', 'PAVEMENT', 'PAVEMENT_FUCKED'),
        KIND_CONCRETE: ('GRAVEL', 'FUCKED_CONCRETE', 'PAINTED_GROUND',
                        'CONCRETE_BEACH', 'P_CONCRETE', 'P_POOLSIDE', 'P_DOCKLANDS', 'P_INDUSTRIAL', 'P_INDUSTJETTY',
                        'P_CONCRETELITTER', 'P_ALLEYRUBISH', 'P_AIRPORTGRND', 'STAIRSSTONE', 'FLOORCONCRETE',
                        'P_ROADSIDE'),
        KIND_DARK_GRASS: ('GRASS_SHORT_LUSH', 'GRASS_MEDIUM_LUSH', 'GRASS_LONG_LUSH', 'GOLFGRASS_ROUGH',
                          'GOLFGRASS_SMOOTH', 'FLOWERBED', 'VEGETATION', 'HEDGE', 'PARKGRASS', 'P_GRASS_SHORT',
                          'P_WOODLAND', 'P_WOODDENSE', 'P_FLOWERBED', 'P_MARSH', 'P_BUSHY', 'P_BUSHYMIX',
                          'P_BUSHYMID', 'P_GRASSWEEFLOWERS', 'P_GRASSLUSHTALL', 'P_GRASSGRNMIX', 'P_GRASSLOW',
                          'P_GRASSSMALLTREES', 'P_FORRESTLEAVES', 'P_SPARSEFLOWERS', 'P_GRASSMID1', 'P_GRASSMID2',
                          'P_GRASSDARK', 'P_GRASSDARK2'),
        KIND_LIGHT_GRASS: ('GRASS_MEDIUM_DRY', 'GRASS_LONG_DRY', 'MEADOW', 'CORNFIELD', 'P_GRASS_MEADOW',
                           'P_GRASS_DRY', 'P_BUSHYDRY', 'P_GRASSDRYTALL', 'P_GRASSROCKY', 'P_FORRESTDRY',
                           'P_CORNFIELD', 'P_GRASSLIGHT', 'P_GRASSLIGHTER2', 'P_GRASSDIRTMIX', 'P_RIVEREDGE',
                           'STEEP_SLIDYGRASS', 'WOODLANDGROUND', 'P_FORESTSTUMPS', 'P_GRASSWEEDS', 'P_SAND_COMPACT'),
        KIND_SAND: ('SAND_BEACH', 'P_SANDBEACH'),
        KIND_DESERT: ('SAND_DEEP', 'SAND_MEDIUM', 'SAND_COMPACT', 'SAND_ARID', 'SAND_MORE', 'P_SAND', 'P_SAND_DENSE',
                      'P_SAND_ARID', 'P_SAND_ROCKY', 'P_ROADSIDEDES', 'P_DESERTROCKS', 'P_CACTUSDENSE',
                      'P_WASTEGROUND', 'GRASS_SHORT_DRY', 'P_GRASSBRNMIX', 'P_GRASSLIGHTER', 'DIRT', 'P_DIRTROCKY',
                      'ROCK_CLIFF'),
        KIND_DIRT: ('MUD_WET', 'MUD_DRY', 'DIRTTRACK', 'P_DIRTWEEDS', 'P_RUBBLE', 'P_BUILDINGSITE', 'P_JUNKYARDPILES',
                    'P_JUNKYARDGRND', 'P_DUMP', 'P_RIVERBEDSTONE', 'P_RIVERBEDSHALLOW', 'P_RIVERBEDWEEDS',
                    'P_SEAWEED', 'P_FORESTSTICKS', 'WASTEGROUND'),
        KIND_ROCK: ('STEEP_CLIFF', 'ROCK_DRY', 'ROCK_WET', 'P_MOUNTAIN'),
        KIND_RAILWAY: ('RAILTRACK',),
    }
    # What a roof can be made of
    ROOF_KINDS = (KIND_UNKNOWN, KIND_STRUCTURE, KIND_CONCRETE)
    # Added to the kind of the triangles that could be a roof
    ROOF_FLAG = 0x80
    # The surfaces that tell an object is part of the ground, however small it is
    GROUND_KINDS = (KIND_ROAD, KIND_DARK_GRASS, KIND_LIGHT_GRASS, KIND_SAND, KIND_DESERT, KIND_DIRT, KIND_WATER,
                    KIND_RAILWAY)
    # What the color of the textures tells instead of the collision, as long as a model shows there
    TEXTURED_KINDS = (KIND_UNKNOWN, KIND_STRUCTURE)
    # A roof is this much above the lowest point of an object that has walls, and above the
    # ground around it, which is measured in cells of this many units
    BUILDING_MIN_HEIGHT = 2.5
    GROUND_CELL_SIZE = TILE_WORLD_SIZE / 16
    GROUND_SEARCH_CELLS = 8
    WALL_MAX_NORMAL_Z = 0.3
    BUILDING_MIN_WALL_SHARE = 0.3
    # Buildings are wider than this, and so are the objects that are not props, such as lamp posts
    BUILDING_MIN_HALF_WIDTH = 3
    PROP_MAX_HALF_WIDTH = 3
    # Collisions this wide, of so few triangles and this flat, are planes of water or sky
    BACKDROP_MIN_HALF_WIDTH = 1000
    BACKDROP_MAX_TRIANGLES = 16
    BACKDROP_MAX_HEIGHT = 1.0
    # A piece of land is wider than this and has less than this share of what faces up being
    # flat, as the roofs and the floors of the buildings are
    LAND_MIN_HALF_WIDTH = 60
    LAND_MAX_FLAT_SHARE = 0.3
    # And anything wider than this is land, as no building is that big, however flat it is
    LAND_ANY_SHAPE_MIN_HALF_WIDTH = 220
    # What the colors of a LOD tell is the kind most of it has within this many units
    LOW_DETAIL_VOTE_RADIUS = 24
    FLAT_MIN_NORMAL_Z = 0.995
    # No roof has the color of these kinds of ground
    GROUND_COLOR_KINDS = (KIND_DARK_GRASS, KIND_LIGHT_GRASS, KIND_SAND)
    # A model shows a collision if it is not further below it than this
    MODEL_MAX_DEPTH = 5
    # Tarmac wider than a road, such as a car park or a runway, is shown as concrete. What is only
    # known to be a road by its color has to be narrower, and most of what is around each of its
    # points has to have that color too, as the dark stones of a cliff do not
    ROAD_MAX_HALF_WIDTH = 30
    COLOR_ROAD_MAX_HALF_WIDTH = 24
    ROAD_SHARE_RADIUS = 4
    ROAD_MIN_SHARE = 0.45
    # A bridge is something as narrow as a road, standing above the ground as a roof does, with
    # at least this share of what is around each of its points having the color of a road
    BRIDGE_ROAD_SHARE = 0.75
    BRIDGE_SHARE_RADIUS = 12
    # Or something that narrow and at least this long with this share of nothing but sea around it
    BRIDGE_SEA_SHARE = 0.6
    BRIDGE_SEA_RADIUS = 48
    BRIDGE_MAX_HALF_WIDTH = 36
    BRIDGE_MIN_LENGTH = 160
    BRIDGE_MIN_WIDTH = 6
    # The widths are measured in pixels of about this many units, which is enough and much faster
    COARSE_PIXEL_SIZE = TILE_WORLD_SIZE / VANILLA_TILE_RESOLUTION
    # Where the collision does not tell the kind of ground, the color of the textures does
    GREY_MAX_SATURATION = 0.2
    ROAD_MAX_BRIGHTNESS = 0.5
    DIRT_MAX_BRIGHTNESS = 0.4
    SAND_MIN_SATURATION = 0.4
    SAND_MIN_BRIGHTNESS = 0.6

    # The vanilla style draws the roads as strokes along the vehicle paths, where a map has them:
    # the paved places on them are roads and the others near them are concrete
    ROAD_STROKE_WIDTH = 6 * 500 / 256
    PAVED_KINDS = (KIND_ROAD, KIND_CONCRETE, KIND_STRUCTURE, KIND_UNKNOWN)
    ROAD_COVERAGE_RADIUS = 100
    NODE_LINK_COUNT_MASK = 0xF
    NODE_BOAT_FLAG = 0x80

    def __init__(self, game_dir, vanilla_file_names, is_vanilla_placement, surfaces_path):
        surface_ids, object_surfaces, water_surfaces = ProcObjConverter.read_surfaces(surfaces_path)
        self._surface_kinds = np.full(256, self.KIND_STRUCTURE, dtype=np.uint8)
        self._default_surface = surface_ids.get('DEFAULT', 0)
        self._surface_kinds[self._default_surface] = self.KIND_UNKNOWN

        for kind, names in self.SURFACE_KINDS.items():
            for name in names:
                if name in surface_ids:
                    self._surface_kinds[surface_ids[name]] = kind

        for surface_id in water_surfaces:
            self._surface_kinds[surface_id] = self.KIND_WATER

        self.game_dir = game_dir
        self.data_dir = os.path.join(game_dir, 'data')
        self.models_dir = os.path.join(game_dir, 'models')
        self.modloader_dir = os.path.join(game_dir, 'modloader')
        self.vanilla_file_names = {file_name.lower() for file_name in vanilla_file_names}
        self.is_vanilla_placement = is_vanilla_placement

        self._archives = []
        self._assets = {}
        self._ide_objects = {}
        self._txd_parents = {}
        self._txd_cache = {}
        self._model_cache = {}
        self._textures = []
        self._texture_indices = {}
        self.water_color = np.array((32, 52, 82), dtype=np.uint8)
        self._water_tile = None

    # Main

    def run(self, map_size, output_dir, progress=print, style=STYLE_REALISTIC, tile_resolution=VANILLA_TILE_RESOLUTION,
            light_intensity=1.0, excluded_mods=(), include_vanilla_map=False):
        """
        Generates the radar with tiles of the given resolution. The light intensity makes the
        objects of the realistic style brighter or darker, and the excluded mods are the folders
        of modloader whose objects are left out of the radar. The original map is drawn from its
        objects too, instead of keeping its radar, if the vanilla map is included.
        """
        self.include_vanilla_map = include_vanilla_map
        self.tile_resolution = tile_resolution if tile_resolution in self.TILE_RESOLUTIONS else self.VANILLA_TILE_RESOLUTION
        # The vanilla style gives flat colors, which need no more than one sample per pixel
        self.samples = 1 if style == self.STYLE_VANILLA else self.SUPERSAMPLING
        self.block_tiles = max(1, min(self.MAX_BLOCK_TILES, self.MAX_BLOCK_RESOLUTION // (self.tile_resolution * self.samples)))
        self.texture_sample_size = min(self.TEXTURE_SAMPLE_SIZE * max(1, self.tile_resolution // self.VANILLA_TILE_RESOLUTION),
                                       self.MAX_TEXTURE_SAMPLE_SIZE)
        self.light_intensity = float(light_intensity)
        self.excluded_mods = {mod.lower() for mod in excluded_mods}

        try:
            return self._generate(map_size, output_dir, progress, style)
        finally:
            for archive in self._archives:
                archive.close()

    def _generate(self, map_size, output_dir, progress, style):
        radar_map_size = self.get_radar_map_size() or map_size
        tiles_per_row = max(radar_map_size // self.TILE_WORLD_SIZE, self.VANILLA_TILES_PER_ROW)
        progress(f'Radar map size: {radar_map_size} ({tiles_per_row * tiles_per_row} tiles)')

        progress('Reading the installed mods...')
        mod_files = self._list_mod_files()
        self._index_assets(mod_files)
        self._read_ide_files(mod_files)
        instances = self._read_instances(mod_files)
        water_quads = self._read_water_quads(mod_files)
        progress(f'{len(instances)} objects found in the installed mods')

        vanilla_tiles = self._read_vanilla_tiles()
        collisions = None

        if self.include_vanilla_map:
            # Only the color of the sea is taken from the original radar
            vanilla_tiles = {}

        if style == self.STYLE_VANILLA:
            progress('Reading the collisions...')
            collisions = self._read_collisions({entry['ide_object'][0].lower() for entry in instances}, mod_files)

        # Texture 0 is used by the materials whose texture cannot be found
        self._textures = [np.full((self.texture_sample_size, self.texture_sample_size, 4), (128, 128, 128, 255), dtype=np.uint8)]
        self._texture_indices = {}

        blocks, scene = self._assign_instances_to_blocks(instances, collisions, radar_map_size, tiles_per_row, progress)
        scene['atlas'] = np.stack(self._textures)
        scene['water_quads'] = water_quads
        scene['road_segments'] = self._read_road_segments(mod_files) if style == self.STYLE_VANILLA else np.zeros((0, 4), np.float32)
        self._textures = []
        self._txd_cache = {}

        if os.path.isdir(output_dir):
            for file_name in os.listdir(output_dir):
                os.remove(os.path.join(output_dir, file_name))
        os.makedirs(output_dir, exist_ok=True)

        tile_resolution = self.tile_resolution
        preview_tile_resolution = min(tile_resolution, self.PREVIEW_MAX_RESOLUTION // tiles_per_row)
        preview = Image.new('RGB', (preview_tile_resolution * tiles_per_row, preview_tile_resolution * tiles_per_row))
        written_tiles = set()
        water_data = None

        def write_tile(tile_row, tile_col, tile_image):
            nonlocal water_data

            tile_name = f'radar{tile_row * tiles_per_row + tile_col:02d}'
            image = Image.fromarray(tile_image, 'RGB')
            preview.paste(image.resize((preview_tile_resolution, preview_tile_resolution), Image.BOX),
                          (tile_col * preview_tile_resolution, tile_row * preview_tile_resolution))

            # Every tile of open sea is the same, so it is only compressed once
            if tile_image is self._water_tile:
                if water_data is None:
                    water_data = self._compress_dxt1(image)
                data = water_data
            else:
                data = self._compress_dxt1(image)

            with open(os.path.join(output_dir, f'{tile_name}.txd'), 'wb') as txd_file:
                txd_file.write(self._write_txd(tile_name, tile_resolution, data))

            written_tiles.add((tile_row, tile_col))

        # The tiles are written as soon as their block is drawn, so they are not all kept in memory
        for i, (block_row, block_col, color_sums, sample_counts) in enumerate(self._render_blocks(blocks, scene, style)):
            progress(f'Drawing the objects... ({i + 1}/{len(blocks)})')
            block_image = self._get_block_image(block_row, block_col, color_sums, sample_counts, vanilla_tiles, tiles_per_row)

            for row in range(self.block_tiles):
                for col in range(self.block_tiles):
                    tile_row = block_row * self.block_tiles + row
                    tile_col = block_col * self.block_tiles + col

                    if tile_row < tiles_per_row and tile_col < tiles_per_row:
                        write_tile(tile_row, tile_col, block_image[row * tile_resolution:(row + 1) * tile_resolution,
                                                                   col * tile_resolution:(col + 1) * tile_resolution])

        for tile_row in range(tiles_per_row):
            progress(f'Writing the radar tiles... ({tile_row * tiles_per_row}/{tiles_per_row * tiles_per_row})')

            for tile_col in range(tiles_per_row):
                if (tile_row, tile_col) not in written_tiles:
                    write_tile(tile_row, tile_col, self._get_background_tile(tile_row, tile_col, vanilla_tiles, tiles_per_row))

        preview.save(os.path.join(output_dir, 'radar_preview.png'))
        progress(f'Radar saved at: {output_dir}')
        return output_dir

    def _render_blocks(self, blocks, scene, style):
        """
        Draws every block, giving each one as soon as it is done. They are drawn by several
        processes at once, which read the scene from memory they all share, or one after the
        other if that cannot be done.
        """
        # The ones that take the longest go first, so the processes end at about the same time
        pending = sorted(blocks, key=lambda block: -len(block[2]))
        workers_count = min((os.cpu_count() or 1) - 1, len(pending), self.MAX_WORKERS)
        memories = []

        if workers_count > 1:
            try:
                scene_specs = {}

                for name, array in scene.items():
                    memory = shared_memory.SharedMemory(create=True, size=max(array.nbytes, 1))
                    memories.append(memory)
                    np.ndarray(array.shape, dtype=array.dtype, buffer=memory.buf)[...] = array
                    scene_specs[name] = (memory.name, array.shape, array.dtype.str)

                with ProcessPoolExecutor(workers_count, initializer=_start_block_worker,
                                         initargs=(self._get_worker_state(), scene_specs)) as executor:
                    tasks = {executor.submit(_draw_block, block, style): block for block in pending}

                    for task in as_completed(tasks):
                        result = task.result()
                        pending.remove(tasks[task])
                        yield result
            except (OSError, RuntimeError, MemoryError) as error:
                print(f'Could not draw with several processes ({error}), drawing with one...')
            finally:
                for memory in memories:
                    memory.close()
                    memory.unlink()

        for block in list(pending):
            yield self._render_block(block, scene, style)

    def _get_worker_state(self):
        # What a process needs to draw blocks, which leaves out the files that are open
        return {name: getattr(self, name) for name in ('tile_resolution', 'block_tiles', 'light_intensity',
                                                       'water_color', 'samples')}

    def get_radar_map_size(self):
        # The radar map size of fastman92 Limit Adjuster sets how many tiles the game loads
        ini_path = os.path.join(self.game_dir, 'fastman92limitAdjuster_GTASA.ini')

        if os.path.isfile(ini_path):
            with open(ini_path, 'r', encoding='latin-1') as ini_file:
                for line in ini_file:
                    match = re.match(r'^\s*Radar map size\s*=\s*(\d+)', line, re.IGNORECASE)
                    if match:
                        return int(match.group(1))

        return 0

    # Game and mod files

    def _list_mod_files(self):
        mod_files = []

        if not os.path.isdir(self.modloader_dir):
            return mod_files

        for mod_directory in sorted(os.listdir(self.modloader_dir)):
            mod_directory_path = os.path.join(self.modloader_dir, mod_directory)

            # Modloader ignores the folders whose name starts with a dot
            if not os.path.isdir(mod_directory_path) or mod_directory.startswith('.'):
                continue

            for root, dirs, files in os.walk(mod_directory_path):
                for file_name in files:
                    mod_files.append(os.path.join(root, file_name))

        return mod_files

    def _index_assets(self, mod_files):
        # Later sources replace earlier ones, as modloader does with the files of the game
        img_paths = [os.path.join(self.models_dir, file_name) for file_name in ('gta3.img', 'gta_int.img')]
        img_paths = [img_path for img_path in img_paths if os.path.isfile(img_path)]
        img_paths += [file_path for file_path in mod_files if file_path.lower().endswith('.img')]

        for img_path in img_paths:
            archive = ImgArchive(img_path)
            self._archives.append(archive)

            for name in archive.entries:
                self._assets[name] = (archive, name)

        for file_path in mod_files:
            if os.path.splitext(file_path)[1].lower() in ('.dff', '.txd', '.ipl'):
                self._assets[os.path.basename(file_path).lower()] = (None, file_path)

    def _read_asset(self, name):
        asset = self._assets.get(name)

        if asset is None:
            return None

        archive, path = asset

        try:
            if archive is None:
                with open(path, 'rb') as asset_file:
                    return asset_file.read()
            return archive.read(path)
        except OSError:
            print(f'Could not read {name}')
            return None

    def _read_ide_files(self, mod_files):
        ide_paths = []

        for root, dirs, files in os.walk(self.data_dir):
            ide_paths += [os.path.join(root, file_name) for file_name in files if file_name.lower().endswith('.ide')]

        ide_paths += [file_path for file_path in mod_files if file_path.lower().endswith('.ide')]

        for ide_path in ide_paths:
            section = None

            with open(ide_path, 'r', encoding='latin-1') as ide_file:
                for line in ide_file:
                    line = line.split('#')[0].strip()

                    if not line:
                        continue

                    if line.lower() in ('objs', 'tobj', 'anim', 'txdp', 'cars', 'peds', 'weap', 'hier', 'path', '2dfx'):
                        section = line.lower()
                        continue
                    if line.lower() == 'end':
                        section = None
                        continue

                    elements = [element.strip() for element in line.split(',')]

                    try:
                        if section in ('objs', 'tobj', 'anim') and len(elements) >= 4:
                            # Animated objects are clumps, which keep the position of their parts
                            self._ide_objects[int(elements[0])] = (elements[1].lower(), elements[2].lower(), section == 'anim')
                        elif section == 'txdp' and len(elements) >= 2:
                            self._txd_parents[elements[0].lower()] = elements[1].lower()
                    except ValueError:
                        continue

    def _read_instances(self, mod_files):
        """
        Returns the position, rotation and IDE object of every object the installed mods place
        outside, leaving out the LODs, as the objects they stand for are drawn instead.
        """
        instances = []
        text_ipls = {}
        stream_contents = {}
        modloader_dir_length = len(self.modloader_dir) + 1
        ipl_paths = []

        if self.include_vanilla_map:
            for root, dirs, files in os.walk(self.data_dir):
                ipl_paths += [os.path.join(root, file_name) for file_name in files]

        for file_path in mod_files:
            # The excluded mods still give their models to the others, but place nothing
            if file_path[modloader_dir_length:].split(os.sep)[0].lower() not in self.excluded_mods:
                ipl_paths.append(file_path)

        for file_path in ipl_paths:
            file_name = os.path.basename(file_path).lower()

            if not file_name.endswith('.ipl') or 'seabed' in file_name:
                continue

            with open(file_path, 'rb') as ipl_file:
                content = ipl_file.read()

            if content[:4] == b'bnry':
                stream_contents[file_name] = content
            else:
                text_ipls[file_name] = self._read_text_ipl(content)

        # The binary IPL files of a text IPL file are named after it, and are usually in an IMG file
        for file_name in text_ipls:
            if file_name in self.vanilla_file_names and not self.include_vanilla_map:
                continue

            base_name = os.path.splitext(file_name)[0]
            stream_index = 0

            while f'{base_name}_stream{stream_index}.ipl' in self._assets:
                stream_name = f'{base_name}_stream{stream_index}.ipl'

                if stream_name not in stream_contents:
                    content = self._read_asset(stream_name)
                    if content and content[:4] == b'bnry':
                        stream_contents[stream_name] = content

                stream_index += 1

        lod_indices = {file_name: set() for file_name in text_ipls}

        for file_name, entries in text_ipls.items():
            for entry in entries:
                if entry['lod'] >= 0:
                    lod_indices[file_name].add(entry['lod'])

        for stream_name, content in stream_contents.items():
            base_name = re.sub(r'_stream\d+$', '', os.path.splitext(stream_name)[0])
            text_ipl_name = f'{base_name}.ipl'

            for entry in self._read_binary_ipl(content):
                if entry['lod'] >= 0 and text_ipl_name in lod_indices:
                    lod_indices[text_ipl_name].add(entry['lod'])

                instances.append(entry)

        for file_name, entries in text_ipls.items():
            # The binary IPL files of the original map are only read if it is drawn, so only then
            # are all the objects that point to the LODs of its files known
            links_known = self.include_vanilla_map or file_name not in self.vanilla_file_names

            for index, entry in enumerate(entries):
                if index in lod_indices[file_name]:
                    continue
                if not self.include_vanilla_map and self.is_vanilla_placement(entry['elements']):
                    continue

                entry['links_known'] = links_known
                instances.append(entry)

        valid_instances = []

        for entry in instances:
            ide_object = self._ide_objects.get(entry['id'])

            if not ide_object or entry['interior'] not in self.EXTERIOR_INTERIORS:
                continue

            model = ide_object[0]

            if 'seabed' in model:
                continue

            # A LOD that no object points to is the only model of what it shows, such as the land
            # far away that cannot be reached, so the game shows it at any distance. It is drawn
            # only where nothing else is, in case an object that points to it was not found
            entry['stand_in'] = model.startswith('lod')

            if entry['stand_in'] and not entry.get('links_known'):
                continue

            entry['ide_object'] = ide_object
            valid_instances.append(entry)

        return valid_instances

    @staticmethod
    def _read_text_ipl(content):
        entries = []
        in_inst = False

        for line in content.decode('latin-1').splitlines():
            line = line.split('#')[0].strip()

            if not line:
                continue
            if line.lower() == 'inst':
                in_inst = True
                continue
            if line.lower() == 'end':
                in_inst = False
                continue
            if not in_inst:
                continue

            elements = [element.strip() for element in line.split(',')]

            if len(elements) < 11:
                continue

            try:
                entries.append({
                    'id': int(elements[0]),
                    'interior': int(float(elements[2])) & 0xFF,
                    'position': (float(elements[3]), float(elements[4]), float(elements[5])),
                    'rotation': (float(elements[6]), float(elements[7]), float(elements[8]), float(elements[9])),
                    'lod': int(float(elements[10])),
                    'elements': elements,
                })
            except ValueError:
                # Kept so that the LOD indices still point to the right objects
                entries.append({'id': -1, 'interior': 0, 'position': (0.0, 0.0, 0.0),
                                'rotation': (0.0, 0.0, 0.0, 1.0), 'lod': -1, 'elements': elements})

        return entries

    @staticmethod
    def _read_binary_ipl(content):
        INST_LENGTH = 40
        entries = []

        try:
            inst_count = struct.unpack_from('<i', content, 4)[0]
            inst_offset = struct.unpack_from('<i', content, 28)[0]

            for i in range(inst_count):
                elements = struct.unpack_from('<7f3i', content, inst_offset + i * INST_LENGTH)
                entries.append({
                    'id': elements[7],
                    'interior': elements[8] & 0xFF,
                    'position': elements[0:3],
                    'rotation': elements[3:7],
                    'lod': elements[9],
                })
        except struct.error:
            print('Could not read a binary IPL file, skipping the rest of it...')

        return entries

    def _read_water_quads(self, mod_files):
        # The water of the game and of every mod, as triangles, so what is under it is shown as water
        water_paths = [os.path.join(self.data_dir, 'water.dat')]
        water_paths += [file_path for file_path in mod_files if os.path.basename(file_path).lower() == 'water.dat']
        triangles = []

        for water_path in water_paths:
            if not os.path.isfile(water_path):
                continue

            with open(water_path, 'r', encoding='latin-1') as water_file:
                for line in water_file:
                    elements = line.split()

                    # Each point has its position, flow and size, and the line ends with its flags
                    if len(elements) not in (22, 29):
                        continue

                    try:
                        points = [(float(elements[i]), float(elements[i + 1]), float(elements[i + 2]))
                                  for i in range(0, len(elements) - 1, 7)]
                    except ValueError:
                        continue

                    triangles.append(points[0:3])

                    if len(points) == 4:
                        triangles.append((points[1], points[3], points[2]))

        return np.array(triangles, dtype=np.float32).reshape(-1, 3, 3)

    # Vanilla radar

    def _read_vanilla_tiles(self):
        vanilla_tiles = {}
        gta3_path = os.path.join(self.models_dir, 'gta3.img')

        if not os.path.isfile(gta3_path):
            print(f'{gta3_path} was not found, the original map will not be on the radar')
            self._water_tile = np.full((self.tile_resolution, self.tile_resolution, 3), self.water_color, dtype=np.uint8)
            return vanilla_tiles

        archive = ImgArchive(gta3_path)
        self._water_tile = np.empty((self.tile_resolution, self.tile_resolution, 3), dtype=np.uint8)

        for tile_index in range(self.VANILLA_TILES_PER_ROW * self.VANILLA_TILES_PER_ROW):
            name = f'radar{tile_index:02d}.txd'

            if name not in archive.entries:
                continue

            textures = self._read_txd(archive.read(name))

            if textures:
                # They are resized when they are used, as it is only once and they take a lot of memory
                vanilla_tiles[divmod(tile_index, self.VANILLA_TILES_PER_ROW)] = next(iter(textures.values())).convert('RGB')

        archive.close()

        # The open sea of the original radar is in its corners
        if (self.VANILLA_TILES_PER_ROW - 1, self.VANILLA_TILES_PER_ROW - 1) in vanilla_tiles:
            corner = vanilla_tiles[(self.VANILLA_TILES_PER_ROW - 1, self.VANILLA_TILES_PER_ROW - 1)]
            corner = np.asarray(corner.resize((self.VANILLA_TILE_RESOLUTION, self.VANILLA_TILE_RESOLUTION), Image.BICUBIC))
            self.water_color = np.median(corner[-16:, -16:].reshape(-1, 3), axis=0).astype(np.uint8)

        self._water_tile[:] = self.water_color

        return vanilla_tiles

    def _get_background_tile(self, tile_row, tile_col, vanilla_tiles, tiles_per_row):
        # The original map is in the middle of the radar
        margin = (tiles_per_row - self.VANILLA_TILES_PER_ROW) // 2
        image = vanilla_tiles.get((tile_row - margin, tile_col - margin))

        if image is None:
            return self._water_tile

        return np.asarray(image.resize((self.tile_resolution, self.tile_resolution), Image.BICUBIC))

    def _get_block_image(self, block_row, block_col, color_sums, sample_counts, vanilla_tiles, tiles_per_row):
        """
        Returns the image of a block from the samples that were drawn of each of its pixels.
        Averaging them smooths the edges of the objects, and the ones that no object covers
        keep the radar of the original map.
        """
        tile_resolution = self.tile_resolution
        background = np.empty((self.block_tiles * tile_resolution, self.block_tiles * tile_resolution, 3), dtype=np.uint8)

        for row in range(self.block_tiles):
            for col in range(self.block_tiles):
                tile = self._get_background_tile(block_row * self.block_tiles + row, block_col * self.block_tiles + col,
                                                 vanilla_tiles, tiles_per_row)
                background[row * tile_resolution:(row + 1) * tile_resolution,
                           col * tile_resolution:(col + 1) * tile_resolution] = tile

        samples_count = self.samples * self.samples
        empty_counts = (samples_count - sample_counts.astype(np.float64))[:, :, None]
        return np.round((color_sums + empty_counts * background) / samples_count).astype(np.uint8)

    # Models

    def _read_collisions(self, models, mod_files):
        # Imported here because the path generator uses the IMG reader of this file
        from application.tools.path_generator import PathGenerator

        collisions = {}

        def read_collision_file(content):
            for model, body, fourcc in PathGenerator.iter_collision_models(content):
                if model in models and model not in collisions:
                    try:
                        collisions[model] = self._build_collision(PathGenerator.read_collision_model(body, fourcc))
                    except (struct.error, ValueError, IndexError):
                        print(f'Could not read the collision of {model}, skipping...')
                        collisions[model] = None

        # The first collision found of each model is kept, so the sources that replace the others
        # are read first
        for file_path in reversed(mod_files):
            if file_path.lower().endswith('.col'):
                try:
                    with open(file_path, 'rb') as col_file:
                        read_collision_file(col_file.read())
                except OSError:
                    print(f'Could not read {file_path}')

        for archive in reversed(self._archives):
            if len(collisions) == len(models):
                break

            for name in archive.entries:
                if name.endswith('.col'):
                    read_collision_file(archive.read(name))

        return collisions

    def _build_collision(self, collision_model):
        """
        Returns the triangles of a collision model and the kind of ground of each one, with the
        top of its boxes as triangles too.
        """
        if collision_model is None:
            return None

        triangles = collision_model['vertices'][collision_model['faces']].reshape(-1, 3, 3)
        surfaces = np.asarray(collision_model['surfaces'], dtype=np.uint8)
        kinds = self._surface_kinds[collision_model['surfaces']]
        box_mins, box_maxs = collision_model['box_mins'], collision_model['box_maxs']
        has_walls = bool(len(box_mins))
        is_land = False

        if len(triangles):
            normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
            areas = np.linalg.norm(normals, axis=1)
            walls = np.abs(normals[:, 2]) < areas * self.WALL_MAX_NORMAL_Z
            has_walls = has_walls or areas[walls].sum() > areas.sum() * self.BUILDING_MIN_WALL_SHARE
            # The hills and the cliffs of a piece of land are not the walls and the roof of a building
            flat = np.abs(normals[:, 2]) > areas * self.FLAT_MIN_NORMAL_Z
            triangles_half_width = float(np.abs(triangles[:, :, :2]).max())
            is_land = ((triangles_half_width > self.LAND_MIN_HALF_WIDTH and
                        areas[flat].sum() < areas[~walls].sum() * self.LAND_MAX_FLAT_SHARE) or
                       triangles_half_width > self.LAND_ANY_SHAPE_MIN_HALF_WIDTH)

        if len(box_mins):
            x0, y0 = box_mins[:, 0], box_mins[:, 1]
            x1, y1, z = box_maxs[:, 0], box_maxs[:, 1], box_maxs[:, 2]
            tops = np.stack((np.stack((x0, y0, z), axis=1), np.stack((x1, y0, z), axis=1),
                             np.stack((x1, y1, z), axis=1), np.stack((x0, y1, z), axis=1)), axis=1)
            triangles = np.concatenate((triangles, tops[:, (0, 1, 2)], tops[:, (0, 2, 3)])).astype(np.float32)
            box_kinds = self._surface_kinds[collision_model['box_surfaces']]
            kinds = np.concatenate((kinds, box_kinds, box_kinds))
            box_surfaces = np.asarray(collision_model['box_surfaces'], dtype=np.uint8)
            surfaces = np.concatenate((surfaces, box_surfaces, box_surfaces))

        if not len(triangles):
            return None

        # Small objects that are not a piece of ground are props, which the radar does not show
        half_width = float(np.abs(triangles[:, :, :2]).max())
        is_prop = half_width < self.PROP_MAX_HALF_WIDTH and not np.isin(kinds, self.GROUND_KINDS).any()

        # A few flat triangles kilometres wide are a plane of water or sky around a map, not land
        if half_width > self.BACKDROP_MIN_HALF_WIDTH and len(triangles) <= self.BACKDROP_MAX_TRIANGLES:
            heights = triangles[:, :, 2]
            is_prop = is_prop or float(heights.max() - heights.min()) <= self.BACKDROP_MAX_HEIGHT

        if has_walls and not is_land:
            # What could be a roof is only marked, as it also takes being above the ground around it
            lowest = min(triangles[:, :, 2].min(), box_mins[:, 2].min() if len(box_mins) else np.inf)
            roofs = np.isin(kinds, self.ROOF_KINDS) & (triangles[:, :, 2].max(axis=1) >= lowest + self.BUILDING_MIN_HEIGHT)
            kinds = np.where(roofs, kinds | self.ROOF_FLAG, kinds).astype(np.uint8)

        return {'triangles': triangles, 'kinds': kinds, 'surfaces': surfaces, 'is_prop': is_prop,
                'radius': float(np.linalg.norm(triangles.reshape(-1, 3), axis=1).max())}

    def _build_stand_in_collision(self, model):
        # The model itself, with the surface that says nothing, so the color of its textures
        # tells what it is
        faces = np.asarray(model['triangles'], dtype=np.int64).reshape(-1, 3)
        empty_boxes = np.zeros((0, 3), dtype=np.float32)
        return self._build_collision({
            'vertices': np.asarray(model['vertices'], dtype=np.float32), 'faces': faces,
            'surfaces': np.full(len(faces), self._default_surface, dtype=np.uint8),
            'box_mins': empty_boxes, 'box_maxs': empty_boxes, 'box_surfaces': np.zeros(0, dtype=np.uint8)})

    def _assign_instances_to_blocks(self, instances, collisions, radar_map_size, tiles_per_row, progress):
        """
        Returns the blocks that have objects, each one with its row, its column and the objects
        that reach it, and the scene, which is the models and the collisions of every object put
        together, so that they can be shared by the processes that draw the blocks.
        """
        half = radar_map_size / 2
        block_world_size = self.block_tiles * self.TILE_WORLD_SIZE
        blocks_per_row = math.ceil(tiles_per_row / self.block_tiles)
        blocks = {}
        models = sorted({entry['ide_object'] for entry in instances})
        model_indices = {}
        collision_indices = {}
        scene_models = []
        scene_collisions = []

        for i, ide_object in enumerate(models):
            if i % 100 == 0:
                progress(f'Reading the models... ({i}/{len(models)})')
            self._get_model(ide_object)

        stand_in_collisions = {}

        for entry in instances:
            ide_object = entry['ide_object']
            model = self._model_cache.get(ide_object)
            collision = None
            stand_in = entry.get('stand_in', False)

            if collisions is not None:
                # What has no collision is decoration, which the vanilla style does not show,
                # except for the LODs that stand in for land, which have no collision either
                collision = collisions.get(ide_object[0].lower())

                if collision is None and stand_in and model is not None:
                    if ide_object not in stand_in_collisions:
                        stand_in_collisions[ide_object] = self._build_stand_in_collision(model)
                    collision = stand_in_collisions[ide_object]

                if collision is None or collision['is_prop']:
                    continue

                radius = max(collision['radius'], model['radius'] if model is not None else 0.0)
            elif model is None:
                continue
            else:
                radius = model['radius']

            if model is not None and ide_object not in model_indices:
                model_indices[ide_object] = len(scene_models)
                scene_models.append(model)

            if collision is not None and ide_object[0] not in collision_indices:
                collision_indices[ide_object[0]] = len(scene_collisions)
                scene_collisions.append(collision)

            block_instance = (model_indices.get(ide_object, -1) if model is not None else -1,
                              collision_indices.get(ide_object[0], -1) if collision is not None else -1,
                              entry['rotation'], entry['position'], stand_in)

            x, y = entry['position'][0], entry['position'][1]
            first_col = int((x - radius + half) // block_world_size)
            last_col = int((x + radius + half) // block_world_size)
            first_row = int((half - (y + radius)) // block_world_size)
            last_row = int((half - (y - radius)) // block_world_size)

            for block_row in range(max(first_row, 0), min(last_row, blocks_per_row - 1) + 1):
                for block_col in range(max(first_col, 0), min(last_col, blocks_per_row - 1) + 1):
                    blocks.setdefault((block_row, block_col), []).append(block_instance)

        self._model_cache = {}
        blocks = [(block_row, block_col, block_instances, radar_map_size)
                  for (block_row, block_col), block_instances in sorted(blocks.items())]
        return blocks, self._build_scene(scene_models, scene_collisions)

    @staticmethod
    def _build_scene(models, collisions):
        def join(arrays, shape, dtype):
            return np.concatenate(arrays).astype(dtype, copy=False) if arrays else np.zeros(shape, dtype=dtype)

        def get_ranges(counts):
            ends = np.cumsum(np.array(counts, dtype=np.int64))
            return np.stack((ends - counts, ends), axis=1).reshape(-1, 2)

        return {
            'vertices': join([model['vertices'] for model in models], (0, 3), np.float32),
            'vertex_ranges': get_ranges([len(model['vertices']) for model in models]),
            'triangles': join([model['triangles'] for model in models], (0, 3), np.int32),
            'triangle_ranges': get_ranges([len(model['triangles']) for model in models]),
            'triangle_uvs': join([model['triangle_uvs'] for model in models], (0, 3, 2), np.float32),
            'triangle_vertex_colors': join([model['triangle_vertex_colors'] for model in models], (0, 3, 3), np.uint8),
            'triangle_textures': join([model['triangle_textures'] for model in models], (0,), np.int32),
            'triangle_colors': join([model['triangle_colors'] for model in models], (0, 4), np.uint8),
            'collision_triangles': join([collision['triangles'] for collision in collisions], (0, 3, 3), np.float32),
            'collision_kinds': join([collision['kinds'] for collision in collisions], (0,), np.uint8),
            'collision_surfaces': join([collision['surfaces'] for collision in collisions], (0,), np.uint8),
            'collision_ranges': get_ranges([len(collision['triangles']) for collision in collisions]),
        }

    def _get_model(self, ide_object):
        if ide_object in self._model_cache:
            return self._model_cache[ide_object]

        model_name, txd_name, is_clump = ide_object
        model = None
        content = self._read_asset(f'{model_name}.dff')

        if content:
            try:
                model = self._read_dff(content, is_clump)
            except (struct.error, ValueError, IndexError):
                print(f'Could not read {model_name}.dff, skipping...')
                model = None

        if model is not None:
            # Every material gets the texture it uses from the TXD file of the object or its parents
            texture_indices = [self._get_texture_index(txd_name, texture_name) for texture_name, color in model['materials']]
            model['triangle_textures'] = np.array(texture_indices, dtype=np.int32)[model['triangle_materials']]
            model['triangle_colors'] = np.array([color for texture_name, color in model['materials']],
                                                dtype=np.uint8).reshape(-1, 4)[model['triangle_materials']]
            # What each triangle has at its corners is the same wherever the object is placed
            model['triangle_uvs'] = model['uvs'][model['triangles']]
            model['triangle_vertex_colors'] = model['colors'][model['triangles']]

        self._model_cache[ide_object] = model
        return model

    def _get_texture_index(self, txd_name, texture_name):
        if not texture_name:
            return 0

        visited = set()

        # The game looks for the texture in the TXD file of the object and then in its parents
        while txd_name and txd_name not in visited:
            visited.add(txd_name)
            key = (txd_name, texture_name)

            if key in self._texture_indices:
                return self._texture_indices[key]

            textures = self._get_txd_textures(txd_name)

            if texture_name in textures:
                self._texture_indices[key] = len(self._textures)
                self._textures.append(textures[texture_name])
                return self._texture_indices[key]

            txd_name = self._txd_parents.get(txd_name)

        return 0

    def _get_txd_textures(self, txd_name):
        if txd_name not in self._txd_cache:
            textures = {}
            content = self._read_asset(f'{txd_name}.txd')

            if content:
                size = self.texture_sample_size

                for name, image in self._read_txd(content).items():
                    textures[name] = np.asarray(image.convert('RGBA').resize((size, size), Image.BOX))

            self._txd_cache[txd_name] = textures

        return self._txd_cache[txd_name]

    # RenderWare files

    @classmethod
    def _iter_chunks(cls, content, start, end):
        offset = start

        while offset + 12 <= end:
            chunk_type, chunk_size, version = struct.unpack_from('<3I', content, offset)
            chunk_end = min(offset + 12 + chunk_size, end)
            yield chunk_type, offset + 12, chunk_end, version
            offset = chunk_end

    @staticmethod
    def _get_library_version(version):
        if version & 0xFFFF0000:
            return ((version >> 14) & 0x3FF00) + 0x30000 | ((version >> 16) & 0x3F)
        return version << 8

    @classmethod
    def _read_dff(cls, content, is_clump):
        for chunk_type, start, end, version in cls._iter_chunks(content, 0, len(content)):
            if chunk_type == cls.RW_CLUMP:
                return cls._read_clump(content, start, end, is_clump)

        return None

    @classmethod
    def _read_clump(cls, content, start, end, is_clump):
        frames = []
        frame_names = []
        geometries = []
        atomics = []

        for chunk_type, chunk_start, chunk_end, version in cls._iter_chunks(content, start, end):
            if chunk_type == cls.RW_FRAME_LIST:
                frames, frame_names = cls._read_frame_list(content, chunk_start, chunk_end)
            elif chunk_type == cls.RW_GEOMETRY_LIST:
                for geometry_type, geometry_start, geometry_end, geometry_version in cls._iter_chunks(content, chunk_start, chunk_end):
                    if geometry_type == cls.RW_GEOMETRY:
                        geometries.append(cls._read_geometry(content, geometry_start, geometry_end, geometry_version))
            elif chunk_type == cls.RW_ATOMIC:
                for atomic_type, atomic_start, atomic_end, atomic_version in cls._iter_chunks(content, chunk_start, chunk_end):
                    if atomic_type == cls.RW_STRUCT:
                        atomics.append(struct.unpack_from('<2I', content, atomic_start))
                        break

        vertices, uvs, colors, triangles, triangle_materials, materials = [], [], [], [], [], []
        vertex_count = 0

        for frame_index, geometry_index in atomics:
            frame_name = frame_names[frame_index] if frame_index < len(frame_names) else ''

            # The damaged version of breakable objects is not shown until they break
            if frame_name.endswith('_dam') or frame_name.endswith('_vlo') or geometry_index >= len(geometries):
                continue

            geometry = geometries[geometry_index]

            if geometry is None:
                continue

            geometry_vertices = geometry['vertices']

            # The game discards the frames of objects that are not clumps, placing their single
            # model straight at the position of the object
            if is_clump and frame_index < len(frames):
                rotation, position = cls._get_frame_matrix(frames, frame_index)
                geometry_vertices = geometry_vertices @ rotation + position

            vertices.append(geometry_vertices)
            uvs.append(geometry['uvs'])
            colors.append(geometry['colors'])
            triangles.append(geometry['triangles'] + vertex_count)
            triangle_materials.append(geometry['triangle_materials'] + len(materials))
            materials.extend(geometry['materials'])
            vertex_count += len(geometry_vertices)

        if not triangles or not materials:
            return None

        vertices = np.concatenate(vertices).astype(np.float32)

        return {
            'vertices': vertices,
            'uvs': np.concatenate(uvs).astype(np.float32),
            'colors': np.concatenate(colors),
            'triangles': np.concatenate(triangles),
            'triangle_materials': np.concatenate(triangle_materials),
            'materials': materials,
            'radius': float(np.sqrt((vertices * vertices).sum(axis=1).max())) if len(vertices) else 0.0,
        }

    @classmethod
    def _read_frame_list(cls, content, start, end):
        FRAME_LENGTH = 56
        frames = []
        frame_names = []
        extensions = []

        for chunk_type, chunk_start, chunk_end, version in cls._iter_chunks(content, start, end):
            if chunk_type == cls.RW_STRUCT:
                frames_count = struct.unpack_from('<I', content, chunk_start)[0]

                for i in range(frames_count):
                    elements = struct.unpack_from('<12fiI', content, chunk_start + 4 + i * FRAME_LENGTH)
                    frames.append((np.array(elements[0:9], dtype=np.float32).reshape(3, 3),
                                   np.array(elements[9:12], dtype=np.float32), elements[12]))
            elif chunk_type == cls.RW_EXTENSION:
                extensions.append((chunk_start, chunk_end))

        for i in range(len(frames)):
            frame_name = ''

            if i < len(extensions):
                for chunk_type, chunk_start, chunk_end, version in cls._iter_chunks(content, *extensions[i]):
                    if chunk_type == cls.RW_FRAME_NAME:
                        frame_name = bytes(content[chunk_start:chunk_end]).split(b'\x00')[0].decode('latin-1').lower()

            frame_names.append(frame_name)

        return frames, frame_names

    @staticmethod
    def _get_frame_matrix(frames, frame_index):
        rotation, position, parent = frames[frame_index]
        visited = {frame_index}

        while 0 <= parent < len(frames) and parent not in visited:
            visited.add(parent)
            parent_rotation, parent_position, next_parent = frames[parent]
            position = position @ parent_rotation + parent_position
            rotation = rotation @ parent_rotation
            parent = next_parent

        return rotation, position

    @classmethod
    def _read_geometry(cls, content, start, end, version):
        geometry = None
        materials = []

        for chunk_type, chunk_start, chunk_end, chunk_version in cls._iter_chunks(content, start, end):
            if chunk_type == cls.RW_STRUCT:
                geometry = cls._read_geometry_struct(content, chunk_start, version)

                if geometry is None:
                    return None
            elif chunk_type == cls.RW_MATERIAL_LIST:
                materials = cls._read_material_list(content, chunk_start, chunk_end)
            elif chunk_type == cls.RW_EXTENSION and geometry is not None and not len(geometry['triangles']):
                # Some models only keep their triangles in their meshes
                for extension_type, extension_start, extension_end, extension_version in cls._iter_chunks(content, chunk_start, chunk_end):
                    if extension_type == cls.RW_BIN_MESH:
                        geometry['triangles'], geometry['triangle_materials'] = cls._read_bin_mesh(content, extension_start)

        if geometry is None or not materials or not len(geometry['triangles']):
            return None

        geometry['materials'] = materials
        geometry['triangle_materials'] = np.minimum(geometry['triangle_materials'], len(materials) - 1)
        return geometry

    @classmethod
    def _read_geometry_struct(cls, content, offset, version):
        geometry_format, triangles_count, vertices_count, morph_targets_count = struct.unpack_from('<4I', content, offset)
        offset += 16

        if cls._get_library_version(version) < 0x34000:
            # Ambient, specular and diffuse
            offset += 12

        if geometry_format & cls.GEOMETRY_NATIVE:
            return None

        if geometry_format & cls.GEOMETRY_PRELIT:
            colors = np.frombuffer(content, dtype=np.uint8, count=vertices_count * 4, offset=offset).reshape(-1, 4)[:, :3]
            offset += vertices_count * 4
        else:
            colors = np.full((vertices_count, 3), 255, dtype=np.uint8)

        texture_sets = (geometry_format >> 16) & 0xFF

        if not texture_sets:
            if geometry_format & cls.GEOMETRY_TEXTURED2:
                texture_sets = 2
            elif geometry_format & cls.GEOMETRY_TEXTURED:
                texture_sets = 1

        if texture_sets:
            uvs = np.frombuffer(content, dtype='<f4', count=vertices_count * 2, offset=offset).reshape(-1, 2)
        else:
            uvs = np.zeros((vertices_count, 2), dtype=np.float32)

        offset += texture_sets * vertices_count * 8

        # Each triangle is stored as its second vertex, first vertex, material and third vertex
        triangles = np.frombuffer(content, dtype='<u2', count=triangles_count * 4, offset=offset).reshape(-1, 4)
        offset += triangles_count * 8

        # Bounding sphere, then whether it has vertices and normals
        has_vertices = struct.unpack_from('<I', content, offset + 16)[0]
        offset += 24

        if not has_vertices or not morph_targets_count:
            return None

        vertices = np.frombuffer(content, dtype='<f4', count=vertices_count * 3, offset=offset).reshape(-1, 3)

        return {
            'vertices': vertices,
            'uvs': uvs,
            'colors': colors,
            'triangles': triangles[:, [1, 0, 3]].astype(np.int32),
            'triangle_materials': triangles[:, 2].astype(np.int32),
        }

    @classmethod
    def _read_material_list(cls, content, start, end):
        material_indices = []
        materials = []

        for chunk_type, chunk_start, chunk_end, version in cls._iter_chunks(content, start, end):
            if chunk_type == cls.RW_STRUCT:
                materials_count = struct.unpack_from('<I', content, chunk_start)[0]
                material_indices = struct.unpack_from(f'<{materials_count}i', content, chunk_start + 4)
            elif chunk_type == cls.RW_MATERIAL:
                materials.append(cls._read_material(content, chunk_start, chunk_end))

        # Materials can be instances of earlier ones
        material_list = []
        new_materials = iter(materials)

        for material_index in material_indices:
            if material_index < 0:
                material_list.append(next(new_materials, ('', (255, 255, 255, 255))))
            else:
                material_list.append(material_list[material_index] if material_index < len(material_list) else ('', (255, 255, 255, 255)))

        return material_list

    @classmethod
    def _read_material(cls, content, start, end):
        color = (255, 255, 255, 255)
        texture_name = ''

        for chunk_type, chunk_start, chunk_end, version in cls._iter_chunks(content, start, end):
            if chunk_type == cls.RW_STRUCT:
                color = struct.unpack_from('<4B', content, chunk_start + 4)
            elif chunk_type == cls.RW_TEXTURE:
                for texture_type, texture_start, texture_end, texture_version in cls._iter_chunks(content, chunk_start, chunk_end):
                    if texture_type == cls.RW_STRING:
                        texture_name = bytes(content[texture_start:texture_end]).split(b'\x00')[0].decode('latin-1').lower()
                        break

        return texture_name, color

    @staticmethod
    def _read_bin_mesh(content, offset):
        is_strip, meshes_count, indices_count = struct.unpack_from('<3I', content, offset)
        offset += 12
        triangles = []
        triangle_materials = []

        for i in range(meshes_count):
            mesh_indices_count, material_index = struct.unpack_from('<2I', content, offset)
            indices = struct.unpack_from(f'<{mesh_indices_count}I', content, offset + 8)
            offset += 8 + mesh_indices_count * 4

            if is_strip:
                for j in range(len(indices) - 2):
                    a, b, c = indices[j:j + 3]

                    if a != b and b != c and a != c:
                        triangles.append((a, b, c) if j % 2 == 0 else (b, a, c))
                        triangle_materials.append(material_index)
            else:
                for j in range(0, len(indices) - 2, 3):
                    triangles.append(indices[j:j + 3])
                    triangle_materials.append(material_index)

        return np.array(triangles, dtype=np.int32).reshape(-1, 3), np.array(triangle_materials, dtype=np.int32)

    @classmethod
    def _read_txd(cls, content):
        """
        Returns the first level of every texture of a TXD file for PC, as images.
        """
        textures = {}

        for chunk_type, start, end, version in cls._iter_chunks(content, 0, len(content)):
            if chunk_type != cls.RW_TEXTURE_DICTIONARY:
                continue

            for texture_type, texture_start, texture_end, texture_version in cls._iter_chunks(content, start, end):
                if texture_type != cls.RW_TEXTURE_NATIVE:
                    continue

                for struct_type, struct_start, struct_end, struct_version in cls._iter_chunks(content, texture_start, texture_end):
                    if struct_type == cls.RW_STRUCT:
                        try:
                            name, image = cls._read_texture_native(content, struct_start)
                            if image is not None:
                                textures[name] = image
                        except (struct.error, ValueError):
                            pass
                        break

        return textures

    @classmethod
    def _read_texture_native(cls, content, offset):
        FORMAT_MASK = 0xF00
        FORMAT_1555 = 0x100
        FORMAT_565 = 0x200
        FORMAT_4444 = 0x300
        FORMAT_LUM8 = 0x400
        FORMAT_8888 = 0x500
        FORMAT_888 = 0x600
        FORMAT_555 = 0xA00
        FORMAT_PAL8 = 0x2000
        FORMAT_PAL4 = 0x4000

        platform = struct.unpack_from('<I', content, offset)[0]
        name = bytes(content[offset + 8:offset + 40]).split(b'\x00')[0].decode('latin-1').lower()
        raster_format, d3d_format = struct.unpack_from('<I4s', content, offset + 72)
        width, height, depth, levels, raster_type, flags = struct.unpack_from('<2H4B', content, offset + 80)
        offset += 88

        if platform not in (8, 9) or not width or not height:
            return name, None

        palette = None

        if raster_format & (FORMAT_PAL8 | FORMAT_PAL4):
            palette_size = 256 if raster_format & FORMAT_PAL8 else 16
            palette = np.frombuffer(content, dtype=np.uint8, count=palette_size * 4, offset=offset).reshape(-1, 4)
            offset += palette_size * 4

        data_size = struct.unpack_from('<I', content, offset)[0]
        data = bytes(content[offset + 4:offset + 4 + data_size])

        # Direct3D 9 textures say whether they are compressed in their flags, Direct3D 8 ones
        # say which DXT format they use instead
        if platform == 9 and flags & 0x08:
            compression = {b'DXT1': 1, b'DXT3': 3, b'DXT5': 5}.get(d3d_format, 0)
        elif platform == 8:
            compression = flags
        else:
            compression = 0

        if compression:
            block_size = 8 if compression == 1 else 16
            blocks_width, blocks_height = max(1, (width + 3) // 4), max(1, (height + 3) // 4)
            data = data.ljust(blocks_width * blocks_height * block_size, b'\x00')
            image = Image.frombytes('RGBA', (blocks_width * 4, blocks_height * 4), data, 'bcn',
                                    {1: 1, 3: 2, 5: 3}.get(compression, 1))
            return name, image.crop((0, 0, width, height))

        pixel_count = width * height

        if palette is not None:
            if raster_format & FORMAT_PAL4:
                packed = np.frombuffer(data, dtype=np.uint8, count=(pixel_count + 1) // 2)
                indices = np.stack((packed & 0x0F, packed >> 4), axis=1).ravel()[:pixel_count]
            else:
                indices = np.frombuffer(data, dtype=np.uint8, count=pixel_count)
            return name, Image.fromarray(palette[indices].reshape(height, width, 4), 'RGBA')

        pixel_format = raster_format & FORMAT_MASK

        if pixel_format in (FORMAT_8888, FORMAT_888):
            pixels = np.frombuffer(data, dtype=np.uint8, count=pixel_count * 4).reshape(height, width, 4)
            rgba = pixels[:, :, [2, 1, 0, 3]].copy()
            if pixel_format == FORMAT_888:
                rgba[:, :, 3] = 255
            return name, Image.fromarray(rgba, 'RGBA')

        if pixel_format == FORMAT_LUM8:
            pixels = np.frombuffer(data, dtype=np.uint8, count=pixel_count).reshape(height, width)
            return name, Image.fromarray(pixels, 'L').convert('RGBA')

        if pixel_format in (FORMAT_565, FORMAT_1555, FORMAT_555, FORMAT_4444):
            pixels = np.frombuffer(data, dtype='<u2', count=pixel_count).reshape(height, width).astype(np.uint32)

            if pixel_format == FORMAT_565:
                channels = ((pixels >> 11) & 0x1F) * 255 // 31, ((pixels >> 5) & 0x3F) * 255 // 63, (pixels & 0x1F) * 255 // 31, np.full_like(pixels, 255)
            elif pixel_format == FORMAT_4444:
                channels = ((pixels >> 8) & 0xF) * 17, ((pixels >> 4) & 0xF) * 17, (pixels & 0xF) * 17, ((pixels >> 12) & 0xF) * 17
            else:
                alpha = ((pixels >> 15) & 1) * 255 if pixel_format == FORMAT_1555 else np.full_like(pixels, 255)
                channels = ((pixels >> 10) & 0x1F) * 255 // 31, ((pixels >> 5) & 0x1F) * 255 // 31, (pixels & 0x1F) * 255 // 31, alpha

            return name, Image.fromarray(np.stack(channels, axis=2).astype(np.uint8), 'RGBA')

        return name, None

    @staticmethod
    def _compress_dxt1(image):
        DDS_HEADER_LENGTH = 128

        dds = io.BytesIO()
        image.convert('RGBA').save(dds, 'DDS', pixel_format='DXT1')
        return dds.getvalue()[DDS_HEADER_LENGTH:]

    def _write_txd(self, name, size, data):
        # Same layout as the radar tiles of the game: one DXT1 texture without mipmaps
        RASTER_FORMAT_565 = 0x200
        FILTER_LINEAR = 0x02
        ADDRESSING_WRAP = 0x11
        DEVICE_D3D9 = 2
        PLATFORM_D3D9 = 9
        RASTER_TYPE_TEXTURE = 4
        FLAG_COMPRESSED = 0x08

        texture = struct.pack('<IBBH32s32sI4s2H4BI', PLATFORM_D3D9, FILTER_LINEAR, ADDRESSING_WRAP, 0,
                              name.encode('ascii'), b'', RASTER_FORMAT_565, b'DXT1',
                              size, size, 16, 1, RASTER_TYPE_TEXTURE, FLAG_COMPRESSED, len(data)) + data

        texture_native = self._chunk(self.RW_TEXTURE_NATIVE, self._chunk(self.RW_STRUCT, texture) +
                                     self._chunk(self.RW_EXTENSION, b''))

        return self._chunk(self.RW_TEXTURE_DICTIONARY, self._chunk(self.RW_STRUCT, struct.pack('<2H', 1, DEVICE_D3D9)) +
                           texture_native + self._chunk(self.RW_EXTENSION, b''))

    @classmethod
    def _chunk(cls, chunk_type, payload):
        return struct.pack('<3I', chunk_type, len(payload), cls.RW_VERSION) + payload

    # Drawing

    def _get_placements(self, block_instances):
        # The objects, and apart from them the LODs that only show where nothing else does
        placements = []
        stand_ins = []

        for model_index, collision_index, rotation, position, stand_in in block_instances:
            right, forward, up = ProcObjConverter.get_instance_matrix(rotation)
            (stand_ins if stand_in else placements).append(
                (model_index, collision_index, np.array((right, forward, up), dtype=np.float32),
                 np.array(position, dtype=np.float32)))

        return placements, stand_ins

    def _get_block_view(self, block):
        # The left and the top of a block in the world, the size of its pixels and how many they are on each side
        block_row, block_col, block_instances, radar_map_size = block
        half = radar_map_size / 2
        samples = self.samples
        resolution = self.block_tiles * self.tile_resolution * samples
        units_per_pixel = self.TILE_WORLD_SIZE / (self.tile_resolution * samples)
        left = -half + block_col * self.block_tiles * self.TILE_WORLD_SIZE
        top = half - block_row * self.block_tiles * self.TILE_WORLD_SIZE
        return left, top, units_per_pixel, resolution

    def _get_water_levels(self, view, scene):
        # The sea outside the original map is everywhere, while inside it only the water of
        # water.dat files is
        left, top, units_per_pixel, resolution = view
        water_levels = np.full(resolution * resolution, -np.inf, dtype=np.float32)
        pixel_x = left + (np.arange(resolution) + 0.5) * units_per_pixel
        pixel_y = top - (np.arange(resolution) + 0.5) * units_per_pixel
        vanilla_half = self.VANILLA_MAP_SIZE / 2
        outside = ((np.abs(pixel_y)[:, None] > vanilla_half) | (np.abs(pixel_x)[None, :] > vanilla_half)).ravel()
        water_levels[outside] = 0.0
        water_quads = scene['water_quads']

        if len(water_quads):
            self._rasterize((water_quads[:, :, 0] - left) / units_per_pixel, (top - water_quads[:, :, 1]) / units_per_pixel,
                            water_quads[:, :, 2], resolution, water_levels)

        return water_levels

    def _render_block(self, block, scene, style):
        """
        Draws the objects of a block. Returns its row and column, and for each of its pixels
        the sum of the colors of its samples that an object covers and how many they are.
        """
        block_row, block_col = block[0], block[1]
        view = self._get_block_view(block)
        units_per_pixel, resolution = view[2], view[3]
        samples = self.samples

        if style == self.STYLE_VANILLA:
            color, covered, depth, water_levels = self._render_vanilla_style(block, scene, view)
        else:
            placements, stand_ins = self._get_placements(block[2])
            depth = np.full(resolution * resolution, -np.inf, dtype=np.float32)
            color = np.zeros((resolution * resolution, 3), dtype=np.uint8)

            self._draw_models(placements, scene, view, depth, color, self.light_intensity)

            if stand_ins:
                stand_in_depth = np.full(resolution * resolution, -np.inf, dtype=np.float32)
                stand_in_color = np.zeros((resolution * resolution, 3), dtype=np.uint8)
                self._draw_models(stand_ins, scene, view, stand_in_depth, stand_in_color, self.light_intensity)
                filled = (depth == -np.inf) & (stand_in_depth > -np.inf)
                depth[filled] = stand_in_depth[filled]
                color[filled] = stand_in_color[filled]

            covered = depth > -np.inf

            water_levels = self._get_water_levels(view, scene)

        color[covered & (depth < water_levels)] = self.water_color
        color[~covered] = 0

        size = resolution // samples
        color_sums = color.reshape(size, samples, size, samples, 3).sum(axis=(1, 3), dtype=np.uint16)
        sample_counts = covered.reshape(size, samples, size, samples).sum(axis=(1, 3), dtype=np.uint8)
        return block_row, block_col, color_sums, sample_counts

    def _render_vanilla_style(self, block, scene, view):
        """
        The vanilla style: the hand-made rules tell what each pixel shows, and near the vehicle
        paths, if the map has them, the paved places on their strokes are roads and the others
        concrete. Returns the color of each pixel, which ones it draws, the height of the
        collision there and the water level.
        """
        resolution = view[3]
        depth = np.full(resolution * resolution, -np.inf, dtype=np.float32)
        color = np.zeros((resolution * resolution, 3), dtype=np.uint8)
        placements, stand_ins = self._get_placements(block[2])
        color, covered, depth, kinds = self._render_vanilla_rules(placements, scene, view, depth, color, stand_ins)
        road_segments = scene['road_segments']

        if len(road_segments):
            strokes, near = self._draw_road_strokes(road_segments, view)
            paved = covered & np.isin(kinds, self.PAVED_KINDS) & near
            color[paved & strokes] = self.VANILLA_PALETTE[self.KIND_ROAD]
            color[paved & ~strokes] = self.VANILLA_PALETTE[self.KIND_CONCRETE]

        return color, covered, depth, self._get_water_levels(view, scene)

    def _draw_road_strokes(self, road_segments, view):
        """
        Returns which pixels of a view the strokes of the roads cover, and which ones are near
        the vehicle paths at all, where the strokes tell the roads from the rest.
        """
        left, top, units_per_pixel, resolution = view
        right, bottom = left + resolution * units_per_pixel, top - resolution * units_per_pixel
        reach = self.ROAD_COVERAGE_RADIUS
        x0, y0, x1, y1 = road_segments[:, 0], road_segments[:, 1], road_segments[:, 2], road_segments[:, 3]
        shown = ((np.maximum(x0, x1) >= left - reach) & (np.minimum(x0, x1) <= right + reach) &
                 (np.maximum(y0, y1) >= bottom - reach) & (np.minimum(y0, y1) <= top + reach))
        strokes = Image.new('L', (resolution, resolution), 0)
        near = Image.new('L', (resolution, resolution), 0)

        if shown.any():
            from PIL import ImageDraw

            stroke_width = max(1, round(self.ROAD_STROKE_WIDTH / units_per_pixel))
            near_width = max(1, round(2 * reach / units_per_pixel))
            draw_strokes, draw_near = ImageDraw.Draw(strokes), ImageDraw.Draw(near)

            for segment in road_segments[shown]:
                points = [((segment[0] - left) / units_per_pixel, (top - segment[1]) / units_per_pixel),
                          ((segment[2] - left) / units_per_pixel, (top - segment[3]) / units_per_pixel)]

                for draw, width in ((draw_strokes, stroke_width), (draw_near, near_width)):
                    draw.line(points, fill=255, width=width)

                    # Round ends, so the strokes of a road join at its bends
                    for x, y in points:
                        draw.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=255)

        return np.asarray(strokes).ravel() > 0, np.asarray(near).ravel() > 0

    def _read_road_segments(self, mod_files):
        """
        Returns the links between the vehicle nodes of the paths of the game, as the two ends of
        each one, from the node files the game would load: the ones of the mods, which replace
        the ones of the original map with the same name, and those only if the original map is drawn.
        """
        from application.tools.path_positioner import PathPositioner

        positioner = PathPositioner()
        node_files = {}
        modloader_dir_length = len(self.modloader_dir) + 1

        def is_excluded(path):
            return path[modloader_dir_length:].split(os.sep)[0].lower() in self.excluded_mods

        for archive in self._archives:
            is_vanilla = not archive.file_path.startswith(self.modloader_dir)

            if (is_vanilla and not self.include_vanilla_map) or (not is_vanilla and is_excluded(archive.file_path)):
                continue

            for name in archive.entries:
                match = PathPositioner.NODE_FILE_PATTERN.match(name)

                if match:
                    node_files[int(match.group(1))] = (name, archive, name)

        for file_path in mod_files:
            match = PathPositioner.NODE_FILE_PATTERN.match(os.path.basename(file_path))

            if match and not is_excluded(file_path):
                node_files[int(match.group(1))] = (os.path.basename(file_path), None, file_path)

        areas = {}

        for area, (name, archive, path) in node_files.items():
            try:
                if archive is None:
                    with open(path, 'rb') as node_file:
                        data = node_file.read()
                else:
                    data = archive.read(path)

                layout = positioner._detect_layout(name, data)
                counts = positioner._read_counts(data, layout)

                if not counts[0]:
                    continue

                node_file = {'name': name, 'data': data, 'layout': layout, 'counts': counts}
                nodes_start, _, links_start = positioner._get_sections(node_file)[:3]
            except (OSError, PathPositioner.UnsupportedFormatError, struct.error) as error:
                print(f'Could not read the paths of {name} ({error})')
                continue

            records = np.frombuffer(data, dtype=np.uint8, count=counts[0] * layout['node_size'],
                                    offset=nodes_start).reshape(counts[0], layout['node_size'])
            position_type = np.int16 if layout['pos_format'] == '<h' else np.int32
            position_size = np.dtype(position_type).itemsize
            positions = records[:, layout['node_pos']:layout['node_pos'] + 2 * position_size].copy().view(position_type)
            positions = positions.reshape(-1, 2).astype(np.float32) / PathPositioner.COORD_SCALE
            link_starts = records[:, 16:18].copy().view(np.uint16).ravel()
            flags = records[:, 24:28].copy().view(np.uint32).ravel()
            links = np.frombuffer(data, dtype=np.uint16, count=counts[4] * 2, offset=links_start).reshape(-1, 2)
            areas[area] = (positions, link_starts, flags, links, counts[1])

        segments = set()

        for area, (positions, link_starts, flags, links, vehicle_count) in areas.items():
            for node in range(vehicle_count):
                if flags[node] & self.NODE_BOAT_FLAG:
                    continue

                for link in links[link_starts[node]:link_starts[node] + (flags[node] & self.NODE_LINK_COUNT_MASK)]:
                    other_area, other_node = int(link[0]), int(link[1])
                    other = areas.get(other_area)

                    if other is None or other_node >= other[4] or other[2][other_node] & self.NODE_BOAT_FLAG:
                        continue

                    ends = sorted(((area, node), (other_area, other_node)))
                    segments.add((ends[0], ends[1]))

        return np.array([(*areas[a][0][i], *areas[b][0][j]) for (a, i), (b, j) in segments],
                        dtype=np.float32).reshape(-1, 4)

    def _render_vanilla_rules(self, placements, scene, view, depth, color, stand_ins=()):
        """
        The hand-made rules of the vanilla style. Returns the color of each pixel, which ones it
        draws, the height of the collision there and the kind of thing it shows. The stand-ins
        are only drawn where the collision of the other objects does not reach.
        """
        resolution = view[3]
        collision_depth, kinds = self._rasterize_collisions(placements, scene, view)
        filled = np.zeros(resolution * resolution, dtype=bool)

        if stand_ins:
            stand_in_depth, stand_in_kinds = self._rasterize_collisions(stand_ins, scene, view)
            filled = (kinds == self.KIND_NONE) & (stand_in_depth > -np.inf)
            collision_depth[filled] = stand_in_depth[filled]
            kinds[filled] = stand_in_kinds[filled]

        # The models are only needed where the collision does not tell what the radar shows
        kinds = kinds.reshape(resolution, resolution)
        filled = filled.reshape(resolution, resolution)
        textured_kinds = ((kinds & self.ROOF_FLAG) != 0) | np.isin(kinds, self.TEXTURED_KINDS)

        if (textured_kinds & ~filled).any():
            # Their own colors are used, as how they are lit says nothing about what they are
            self._draw_models(placements, scene, view, depth, color, None, textured_kinds & ~filled)

        # Some maps give the collision of their land to an object with an empty model, and its
        # looks to a LOD on its own, so the stand-ins also show where the models do not
        shown = (depth >= collision_depth - self.MODEL_MAX_DEPTH).reshape(resolution, resolution)
        needed = textured_kinds & (filled | ~shown)
        used = np.zeros(resolution * resolution, dtype=bool)

        if stand_ins and needed.any():
            stand_in_depth = np.full(resolution * resolution, -np.inf, dtype=np.float32)
            stand_in_color = np.zeros((resolution * resolution, 3), dtype=np.uint8)
            self._draw_models(stand_ins, scene, view, stand_in_depth, stand_in_color, None, needed)
            used = needed.ravel() & (filled.ravel() | (stand_in_depth >= collision_depth - self.MODEL_MAX_DEPTH))
            depth[used] = stand_in_depth[used]
            color[used] = stand_in_color[used]

        color, covered, kinds = self._paint_vanilla_style(kinds, collision_depth.reshape(resolution, resolution),
                                                   color, depth >= collision_depth - self.MODEL_MAX_DEPTH, used)
        return color, covered, collision_depth, kinds

    def _rasterize_collisions(self, placements, scene, view):
        # The height of the highest collision on each pixel and its kind of ground
        left, top, units_per_pixel, resolution = view
        collision_depth = np.full(resolution * resolution, -np.inf, dtype=np.float32)
        kinds = np.full(resolution * resolution, self.KIND_NONE, dtype=np.uint8)
        collision_triangles = []
        collision_kinds = []

        for model_index, collision_index, matrix, position in placements:
            start, end = scene['collision_ranges'][collision_index]
            collision_triangles.append(scene['collision_triangles'][start:end] @ matrix + position)
            collision_kinds.append(scene['collision_kinds'][start:end])

        if collision_triangles:
            collision_triangles = np.concatenate(collision_triangles)
            self._rasterize((collision_triangles[:, :, 0] - left) / units_per_pixel,
                            (top - collision_triangles[:, :, 1]) / units_per_pixel,
                            collision_triangles[:, :, 2], resolution, collision_depth,
                            labels=np.concatenate(collision_kinds), label_buffer=kinds)

        return collision_depth, kinds

    def _draw_models(self, placements, scene, view, depth, color, light_intensity, needed=None):
        """
        Draws the models of the objects of a block, lit as the game would light them, or with
        their own colors if there is no light intensity. If only some pixels are needed, the
        triangles that are away from all of them are left out.
        """
        left, top, units_per_pixel, resolution = view
        right, bottom = left + resolution * units_per_pixel, top - resolution * units_per_pixel
        needed_cells = None

        if needed is not None:
            # How many needed pixels there are before each cell of a grid, to count them in any part of it
            cell_size = self.NEEDED_CELL_SIZE
            cells = needed.reshape(resolution // cell_size, cell_size, resolution // cell_size, cell_size).any(axis=(1, 3))
            needed_cells = np.pad(cells.cumsum(axis=0, dtype=np.int32).cumsum(axis=1, dtype=np.int32), ((1, 0), (1, 0)))
            cells_per_unit = 1 / (units_per_pixel * cell_size)
            last_cell = resolution // cell_size - 1

        parts = ([], [], [], [], [])

        for model_index, collision_index, matrix, position in placements:
            if model_index < 0:
                continue

            first_vertex, last_vertex = scene['vertex_ranges'][model_index]
            first_triangle, last_triangle = scene['triangle_ranges'][model_index]
            vertices = scene['vertices'][first_vertex:last_vertex] @ matrix + position
            triangles = vertices[scene['triangles'][first_triangle:last_triangle]]
            triangle_slice = slice(first_triangle, last_triangle)

            min_x, max_x = triangles[:, :, 0].min(axis=1), triangles[:, :, 0].max(axis=1)
            min_y, max_y = triangles[:, :, 1].min(axis=1), triangles[:, :, 1].max(axis=1)
            shown = (max_x >= left) & (min_x <= right) & (max_y >= bottom) & (min_y <= top)

            if needed_cells is not None:
                first_col = np.clip(((min_x - left) * cells_per_unit).astype(np.int32), 0, last_cell)
                last_col = np.clip(((max_x - left) * cells_per_unit).astype(np.int32), 0, last_cell) + 1
                first_row = np.clip(((top - max_y) * cells_per_unit).astype(np.int32), 0, last_cell)
                last_row = np.clip(((top - min_y) * cells_per_unit).astype(np.int32), 0, last_cell) + 1
                shown &= (needed_cells[last_row, last_col] - needed_cells[first_row, last_col] -
                          needed_cells[last_row, first_col] + needed_cells[first_row, first_col]) > 0

            if not shown.any():
                continue

            arrays = (triangles, scene['triangle_uvs'][triangle_slice], scene['triangle_vertex_colors'][triangle_slice],
                      scene['triangle_textures'][triangle_slice], scene['triangle_colors'][triangle_slice])

            for part, array in zip(parts, arrays):
                part.append(array if shown.all() else array[shown])

        if not parts[0]:
            return

        triangles, uvs, vertex_colors, textures, material_colors = (np.concatenate(part) for part in parts)
        self._rasterize((triangles[:, :, 0] - left) / units_per_pixel, (top - triangles[:, :, 1]) / units_per_pixel,
                        triangles[:, :, 2], resolution, depth, color, uvs, vertex_colors, textures, material_colors,
                        scene['atlas'], light_intensity=light_intensity)

    def _paint_vanilla_style(self, kinds, heights, textured_color, textured, low_detail=None):
        """
        Returns the color the vanilla style gives to each pixel and which pixels it draws, from
        the kind of ground the collision gave them and, where it does not tell it, from the
        color of the models there.
        """
        resolution = kinds.shape[0]
        units_per_pixel = self.TILE_WORLD_SIZE / (self.tile_resolution * self.samples)
        textured = textured.reshape(resolution, resolution)
        roofs = (kinds & self.ROOF_FLAG) != 0
        kinds = kinds & ~np.uint8(self.ROOF_FLAG)
        textured_kinds = roofs | np.isin(kinds, self.TEXTURED_KINDS)

        # A collision whose model does not show there is something the game does not show either
        hidden = textured_kinds & ~textured
        kinds[hidden] = self.KIND_NONE
        roofs &= ~hidden

        color_kinds = np.full(resolution * resolution, self.KIND_NONE, dtype=np.uint8)
        textured_pixels = np.nonzero((textured_kinds & textured).ravel())[0]
        color_kinds[textured_pixels] = self._get_color_kinds(textured_color[textured_pixels])
        color_kinds = color_kinds.reshape(resolution, resolution)

        if low_detail is not None and low_detail.any():
            color_kinds = self._get_low_detail_kinds(color_kinds, low_detail.reshape(resolution, resolution), units_per_pixel)

        # The widths of the roads and the bridges are measured in bigger pixels
        coarse = max(1, round(self.COARSE_PIXEL_SIZE / units_per_pixel))
        coarse_resolution = resolution // coarse
        coarse_pixel_size = units_per_pixel * coarse

        def get_coarse(mask):
            return mask.reshape(coarse_resolution, coarse, coarse_resolution, coarse).sum(axis=(1, 3))

        def get_fine(mask):
            return mask.repeat(coarse, axis=0).repeat(coarse, axis=1)

        def get_wide(mask, max_half_width=self.ROAD_MAX_HALF_WIDTH):
            half_width = int(max_half_width / coarse_pixel_size)
            return self._grow(self._grow(mask, half_width, False), half_width + 1, True)

        # What has the color of grass or sand is ground, whatever its height is
        ground_colored = roofs & np.isin(color_kinds, self.GROUND_COLOR_KINDS)
        kinds[ground_colored] = color_kinds[ground_colored]
        roofs &= ~ground_colored

        if roofs.any():
            ground = self._get_ground_heights(heights, (kinds != self.KIND_NONE) & ~roofs)
            roofs &= heights >= ground + self.BUILDING_MIN_HEIGHT

        if roofs.any():
            coarse_roofs = get_coarse(roofs)
            narrow = (coarse_roofs > 0) & ~get_wide(coarse_roofs > 0)

            # Bridges over the land, which have the color of the roads
            coarse_roads = get_coarse(roofs & (color_kinds == self.KIND_ROAD))
            share_radius = max(1, round(self.BRIDGE_SHARE_RADIUS / coarse_pixel_size))
            bridges = narrow & (self._sum_around(coarse_roads, share_radius) >=
                                self._sum_around(coarse_roofs, share_radius) * self.BRIDGE_ROAD_SHARE)

            # Bridges over the sea, whatever their color is
            sea_radius = max(1, round(self.BRIDGE_SEA_RADIUS / coarse_pixel_size))
            sea_around = self._sum_around(get_coarse(kinds == self.KIND_NONE), sea_radius)
            land_around = (2 * sea_radius + 1) ** 2 * coarse * coarse - self._sum_around(coarse_roofs, sea_radius)
            over_sea = ((coarse_roofs > 0) & ~get_wide(coarse_roofs > 0, self.BRIDGE_MAX_HALF_WIDTH) &
                        (sea_around >= land_around * self.BRIDGE_SEA_SHARE))
            length_radius = max(1, round(self.BRIDGE_MIN_LENGTH / 2 / coarse_pixel_size))
            bridges |= over_sea & (self._sum_around(over_sea, length_radius) >=
                                   (2 * length_radius + 1) * self.BRIDGE_MIN_WIDTH / coarse_pixel_size)

            bridges = roofs & get_fine(bridges)
            kinds[bridges] = self.KIND_ROAD
            roofs &= ~bridges
            # What is too thin to be a building is left as what its color tells
            min_half_width = max(1, round(self.BUILDING_MIN_HALF_WIDTH / units_per_pixel))
            roofs &= self._grow(self._grow(roofs, min_half_width, False), min_half_width, True)
            kinds[roofs] = self.KIND_BUILDING

        textured_kinds = np.isin(kinds, self.TEXTURED_KINDS)
        kinds[textured_kinds] = color_kinds[textured_kinds]

        roads = kinds == self.KIND_ROAD

        if roads.any():
            share_radius = max(1, round(self.ROAD_SHARE_RADIUS / coarse_pixel_size))
            min_count = (2 * share_radius + 1) ** 2 * coarse * coarse * self.ROAD_MIN_SHARE
            color_roads = roads & textured_kinds
            solid_color_roads = self._sum_around(get_coarse(color_roads), share_radius) >= min_count
            wide = (get_wide(self._sum_around(get_coarse(roads), share_radius) >= min_count) |
                    get_wide(solid_color_roads, self.COLOR_ROAD_MAX_HALF_WIDTH))
            kinds[(roads & get_fine(wide)) | (color_roads & ~get_fine(solid_color_roads))] = self.KIND_CONCRETE

        kinds = self._smooth_kinds(kinds)

        palette = np.zeros((max(self.VANILLA_PALETTE) + 2, 3), dtype=np.uint8)
        for kind, kind_color in self.VANILLA_PALETTE.items():
            palette[kind] = kind_color
        palette[self.KIND_WATER] = self.water_color

        kinds = kinds.ravel()
        return palette[kinds], kinds != self.KIND_NONE, kinds

    def _get_low_detail_kinds(self, color_kinds, low_detail, units_per_pixel):
        # A LOD gives each of its big faces its own texture, so what its colors tell is the kind
        # most of it has around each point
        radius = max(1, round(self.LOW_DETAIL_VOTE_RADIUS / units_per_pixel))
        most_votes = np.zeros(color_kinds.shape, dtype=np.int64)
        voted = color_kinds.copy()

        for kind in np.unique(color_kinds[low_detail]):
            votes = self._sum_around(low_detail & (color_kinds == kind), radius)
            more = low_detail & (votes > most_votes)
            voted[more] = kind
            most_votes[more] = votes[more]

        return voted

    @staticmethod
    def _sum_around(values, radius):
        # The sum of the values of the square of cells around each one
        size = values.shape[0]
        sums = np.pad(values.astype(np.int64), ((radius + 1, radius), (radius + 1, radius)))
        sums = sums.cumsum(axis=0).cumsum(axis=1)
        length = 2 * radius + 1
        return sums[length:, length:] - sums[:size, length:] - sums[length:, :size] + sums[:size, :size]

    def _get_ground_heights(self, heights, ground):
        """
        Returns the height of the ground around each pixel, which is the average one of the
        pixels of its cell that are ground, or of the cells around it when it has none. Where
        there is no ground around, it is as low as it can be.
        """
        resolution = heights.shape[0]
        cell_size = round(self.GROUND_CELL_SIZE * self.tile_resolution * self.samples / self.TILE_WORLD_SIZE)
        cells = resolution // cell_size
        # The sea covers what is under it
        ground_heights = np.where(ground, np.maximum(heights, 0.0), 0.0)
        totals = ground_heights.reshape(cells, cell_size, cells, cell_size).sum(axis=(1, 3))
        counts = ground.reshape(cells, cell_size, cells, cell_size).sum(axis=(1, 3)).astype(np.float32)

        for _ in range(self.GROUND_SEARCH_CELLS):
            empty = counts == 0

            if not empty.any():
                break

            padded_totals = np.pad(totals, 1)
            padded_counts = np.pad(counts, 1)
            around_totals = sum(padded_totals[1 + dy:cells + 1 + dy, 1 + dx:cells + 1 + dx]
                                for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            around_counts = sum(padded_counts[1 + dy:cells + 1 + dy, 1 + dx:cells + 1 + dx]
                                for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            totals = np.where(empty, around_totals, totals)
            counts = np.where(empty, around_counts, counts)

        cell_heights = np.where(counts > 0, totals / np.maximum(counts, 1), -np.inf).astype(np.float32)
        return cell_heights.repeat(cell_size, axis=0).repeat(cell_size, axis=1)

    def _get_color_kinds(self, colors):
        colors = colors.astype(np.float32) / 255.0
        red, green, blue = colors[:, 0], colors[:, 1], colors[:, 2]
        brightness = colors.max(axis=1)
        chroma = brightness - colors.min(axis=1)
        saturation = chroma / np.maximum(brightness, 1e-6)
        safe_chroma = np.maximum(chroma, 1e-6)
        hue = np.where(brightness == red, ((green - blue) / safe_chroma) % 6,
                       np.where(brightness == green, (blue - red) / safe_chroma + 2,
                                (red - green) / safe_chroma + 4)) * 60

        grey = saturation < self.GREY_MAX_SATURATION
        brown = (hue < 35) | (hue >= 330)
        yellow = (hue >= 35) & (hue < 60)
        sand = yellow & (saturation >= self.SAND_MIN_SATURATION) & (brightness >= self.SAND_MIN_BRIGHTNESS)

        # From the least to the most specific, each one replacing the ones before it
        kinds = np.full(len(colors), self.KIND_CONCRETE, dtype=np.uint8)
        kinds[brown] = self.KIND_DESERT
        kinds[brown & (brightness < self.DIRT_MAX_BRIGHTNESS)] = self.KIND_DIRT
        kinds[yellow] = self.KIND_DESERT
        kinds[yellow & (hue >= 50)] = self.KIND_LIGHT_GRASS
        kinds[sand] = self.KIND_SAND
        kinds[(hue >= 60) & (hue < 90)] = self.KIND_LIGHT_GRASS
        kinds[(hue >= 90) & (hue < 170)] = self.KIND_DARK_GRASS
        kinds[grey] = self.KIND_CONCRETE
        kinds[grey & (brightness < self.ROAD_MAX_BRIGHTNESS)] = self.KIND_ROAD
        return kinds

    @staticmethod
    def _grow(mask, radius, value):
        # Spreads the cells with the given value to their neighbours, alternating straight and
        # diagonal steps so it grows about the same in every direction
        mask = mask if value else ~mask

        for i in range(radius):
            padded = np.pad(mask, 1, mode='edge')
            grown = padded[1:-1, 1:-1] | padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:]

            if i % 2:
                grown |= padded[:-2, :-2] | padded[:-2, 2:] | padded[2:, :-2] | padded[2:, 2:]

            mask = grown

        return mask if value else ~mask

    @staticmethod
    def _smooth_kinds(kinds):
        # Each pixel gets the kind most of its neighbours have, which removes the specks
        smoothed = kinds.copy()
        most_votes = np.zeros(kinds.shape, dtype=np.uint8)

        for kind in np.unique(kinds):
            same = (kinds == kind).astype(np.uint8)
            padded = np.pad(same, 1, mode='edge')
            rows = padded[:-2] + padded[1:-1] + padded[2:]
            # The pixel itself counts once more, so a tie leaves it as it is
            votes = (rows[:, :-2] + rows[:, 1:-1] + rows[:, 2:]) * 2 + same
            more = votes > most_votes
            smoothed[more] = kind
            most_votes[more] = votes[more]

        return smoothed

    def _rasterize(self, screen_x, screen_y, z, resolution, depth, color=None, uvs=None, vertex_colors=None,
                   textures=None, material_colors=None, atlas=None, labels=None, label_buffer=None, light_intensity=None):
        """
        Draws triangles seen from above, keeping in the depth buffer the highest point of each
        pixel. Without a color buffer, only the depth buffer is updated, and the label buffer
        if there is one, with the label of the triangle each pixel shows. Without a light
        intensity, the triangles are drawn with the colors of their textures alone.
        """
        min_x = np.ceil(screen_x.min(axis=1) - 0.5)
        max_x = np.floor(screen_x.max(axis=1) - 0.5)
        min_y = np.ceil(screen_y.min(axis=1) - 0.5)
        max_y = np.floor(screen_y.max(axis=1) - 0.5)
        min_x = np.maximum(min_x, 0)
        min_y = np.maximum(min_y, 0)
        max_x = np.minimum(max_x, resolution - 1)
        max_y = np.minimum(max_y, resolution - 1)

        area = ((screen_x[:, 1] - screen_x[:, 0]) * (screen_y[:, 2] - screen_y[:, 0]) -
                (screen_x[:, 2] - screen_x[:, 0]) * (screen_y[:, 1] - screen_y[:, 0]))
        width = max_x - min_x + 1
        height = max_y - min_y + 1

        # Walls have no area seen from above
        visible = np.nonzero((width > 0) & (height > 0) & (np.abs(area) > 1e-6))[0]

        if not len(visible):
            return

        # Triangles are drawn in groups of similar size, testing every pixel of their bounding box.
        # In each group the highest ones go first, so most of what they hide is discarded early
        bucket_sizes = np.array(self.BUCKET_SIZES, dtype=np.int64)
        width_bucket = np.searchsorted(bucket_sizes, width[visible].astype(np.int64))
        height_bucket = np.searchsorted(bucket_sizes, height[visible].astype(np.int64))
        buckets = width_bucket * len(bucket_sizes) + height_bucket
        order = np.lexsort((-z[visible].max(axis=1), buckets))
        visible, buckets = visible[order], buckets[order]
        bucket_starts = np.nonzero(np.diff(buckets, prepend=-1))[0]
        bucket_ends = np.append(bucket_starts[1:], len(visible))

        for bucket_start, bucket_end in zip(bucket_starts, bucket_ends):
            bucket_width, bucket_height = (int(bucket_sizes[i]) for i in divmod(int(buckets[bucket_start]), len(bucket_sizes)))
            samples_count = bucket_width * bucket_height
            indices = visible[bucket_start:bucket_end]
            offset_y, offset_x = np.divmod(np.arange(samples_count, dtype=np.float32), bucket_width)
            chunk_size = max(1, self.RASTER_CHUNK_SAMPLES // samples_count)

            for chunk_start in range(0, len(indices), chunk_size):
                chunk = indices[chunk_start:chunk_start + chunk_size]
                pixel_x = min_x[chunk, None] + offset_x[None, :]
                pixel_y = min_y[chunk, None] + offset_y[None, :]
                inside = (pixel_x <= max_x[chunk, None]) & (pixel_y <= max_y[chunk, None])

                center_x = pixel_x + 0.5
                center_y = pixel_y + 0.5
                x0, x1, x2 = (screen_x[chunk, i, None] for i in range(3))
                y0, y1, y2 = (screen_y[chunk, i, None] for i in range(3))
                chunk_area = area[chunk, None]
                weight0 = ((x1 - center_x) * (y2 - center_y) - (x2 - center_x) * (y1 - center_y)) / chunk_area
                weight1 = ((x2 - center_x) * (y0 - center_y) - (x0 - center_x) * (y2 - center_y)) / chunk_area
                weight2 = 1.0 - weight0 - weight1
                inside &= (weight0 >= 0) & (weight1 >= 0) & (weight2 >= 0)

                sample_indices = np.flatnonzero(inside)

                if not len(sample_indices):
                    continue

                triangles = chunk[sample_indices // samples_count]
                weight0, weight1, weight2 = (weight.ravel()[sample_indices] for weight in (weight0, weight1, weight2))
                pixels = (pixel_y.ravel()[sample_indices].astype(np.int64) * resolution +
                          pixel_x.ravel()[sample_indices].astype(np.int64))
                triangle_z = z[triangles]
                pixel_z = weight0 * triangle_z[:, 0] + weight1 * triangle_z[:, 1] + weight2 * triangle_z[:, 2]

                higher = np.flatnonzero(pixel_z > depth[pixels])

                if not len(higher):
                    continue

                pixels, triangles, pixel_z = pixels[higher], triangles[higher], pixel_z[higher]

                if color is None:
                    if label_buffer is None:
                        np.maximum.at(depth, pixels, pixel_z)
                    else:
                        order = np.argsort(pixel_z, kind='stable')
                        depth[pixels[order]] = pixel_z[order]
                        label_buffer[pixels[order]] = labels[triangles[order]]
                    continue

                weight0, weight1, weight2 = weight0[higher, None], weight1[higher, None], weight2[higher, None]
                triangle_uvs = uvs[triangles]
                pixel_uv = np.nan_to_num(weight0 * triangle_uvs[:, 0] + weight1 * triangle_uvs[:, 1] +
                                         weight2 * triangle_uvs[:, 2])
                texture_size = atlas.shape[1]
                texel_x = np.floor(np.clip(pixel_uv[:, 0], -1e6, 1e6) * texture_size).astype(np.int64) % texture_size
                texel_y = np.floor(np.clip(pixel_uv[:, 1], -1e6, 1e6) * texture_size).astype(np.int64) % texture_size
                texel = atlas[textures[triangles], texel_y, texel_x]
                material_color = material_colors[triangles]

                # Transparent parts of the textures, such as the leaves of the trees, let what is
                # under them show
                opaque = np.flatnonzero(texel[:, 3].astype(np.float32) * material_color[:, 3] / 255.0 >= self.ALPHA_TEST)

                if not len(opaque):
                    continue

                pixels, triangles, pixel_z = pixels[opaque], triangles[opaque], pixel_z[opaque]
                pixel_color = texel[opaque, :3].astype(np.float32) * (material_color[opaque, :3].astype(np.float32) / 255.0)

                if light_intensity is not None:
                    triangle_colors = vertex_colors[triangles].astype(np.float32)
                    prelight = (weight0[opaque] * triangle_colors[:, 0] + weight1[opaque] * triangle_colors[:, 1] +
                                weight2[opaque] * triangle_colors[:, 2])
                    light = np.minimum(self.AMBIENT_LIGHT + prelight / 255.0 * self.PRELIGHT_SCALE, 1.0)
                    pixel_color = pixel_color * light

                    if light_intensity != 1.0:
                        pixel_color *= light_intensity

                # Drawn from the lowest to the highest, so the highest one stays where they overlap
                order = np.argsort(pixel_z, kind='stable')
                depth[pixels[order]] = pixel_z[order]
                color[pixels[order]] = np.clip(pixel_color[order], 0, 255).astype(np.uint8)
