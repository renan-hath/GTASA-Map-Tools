"""
Checks that a GTA San Andreas installation can load every map mod installed in it, and sets it
up so it can.

It counts what the game will load (its own files and every modloader mod), compares that with
the limits of the game and of the limit adjusters installed (fastman92 Limit Adjuster, Open Limit
Adjuster and $$MapLimits.asi, in any combination), and lists what is too low or wrong, with the
change that fixes it. The changes are only made when asked, after copying every file they touch
to a backup folder inside the game folder, so they can be undone.

Run from the folder of the tool to only print the check:
    python -m application.tools.installation_check <game folder>
"""
import json
import math
import os
import re
import shutil
import struct
import sys
import time
from dataclasses import dataclass, field

from application.tools.limit_adjusters import UNLIMITED, LimitAdjusters
from application.tools.path_positioner import PathPositioner
from application.tools.radar_generator import ImgArchive

BACKUP_DIR_NAME = '.gtasa_map_tools_backup'
BASE_PATHS_MOD_NAME = 'paths_files'

SECTOR_SIZE = 50
LOD_SECTOR_SIZE = 200
BIG_BUILDING_DRAW_DISTANCE = 300
DAMAGEABLE_FLAG = 0x1000
FORCE_MATRIX_FLAG = 0x200
# Matrices the game needs at any time for vehicles, peds and objects, which is its original limit
DYNAMIC_MATRICES = 900
MAP_FILE_TYPES = ('.ide', '.ipl', '.zon')
IMG_FILE_TYPES = ('.dff', '.txd', '.col', '.ipl', '.ifp')
IDE_SECTIONS = ('objs', 'tobj', 'anim', 'hier', 'cars', 'peds', 'weap', '2dfx', 'txdp', 'path')
IPL_SECTIONS = ('inst', 'cull', 'grge', 'enex', 'pick', 'jump', 'tcyc', 'auzo', 'cars', 'occl', 'zone',
                'path', 'mult')
MAP_SIZES = (6000, 12000, 24000, 48000)
VANILLA_MAP_SIZE = 6000
RADAR_TILE_SIZE = 500
RADAR_TILE_PATTERN = re.compile(r'^radar(\d+)\.txd$', re.IGNORECASE)
WATER_VALUES_PER_CORNER = 7
# Objects further out than all but this share of them are not counted for the map size, as maps
# hide a few things far away, such as the places they keep in the sky
MAP_EXTENT_PERCENTILE = 99.9

# name, the game's own limit, fastman92's section and key, Open Limit Adjuster's key
LIMITS = [
    ('Matrices', 900, 'DYNAMIC LIMITS', 'Matrices', 'MatrixList'),
    ('ColModels', 10150, 'DYNAMIC LIMITS', 'ColModels', 'ColModel'),
    ('PtrNode Singles', 70000, 'DYNAMIC LIMITS', 'PtrNode Singles', 'PtrNodeSingle'),
    ('Buildings', 13000, 'IPL', 'Buildings', 'Buildings'),
    ('Dummies', 2500, 'IPL', 'Dummies', 'Dummys'),
    ('Inst entries per file', 4096, 'IPL', 'Inst entries per file', 'EntitiesPerIpl'),
    ('Entity index array', 40, 'IPL', 'Entity index array', 'EntityIpl'),
    ('CULL attribute zones', 1300, 'IPL', 'CULL attribute zones', None),
    ('Entry exits', 400, 'IPL', 'Entry exits', None),
    ('Occluders', 1000, 'IPL', 'Occluders', None),
    ('Stunt jumps', 256, 'IPL', 'Stunt jumps', None),
    ('Timecycle modifiers', 32, 'IPL', 'Timecycle modifiers', None),
    ('Auzo zone boxes', 158, 'IPL', 'Auzo zone boxes', None),
    ('Pickups', 620, 'IPL', 'Pickups', None),
    ('Map zones', 39, 'IPL', 'Map zones', None),
    ('Navigation zones', 380, 'IPL', 'Navigation zones', None),
    ('IDE Objects Type 1', 14000, 'IDE LIMITS', 'IDE Objects Type 1', 'AtomicModels'),
    ('IDE Objects Type 2', 70, 'IDE LIMITS', 'IDE Objects Type 2', 'DamageAtomicModels'),
    ('Timed Objects', 169, 'IDE LIMITS', 'Timed Objects', 'TimeModels'),
    ('Hier Objects', 92, 'IDE LIMITS', 'Hier Objects', 'ClumpModels'),
    ('Vehicle Models', 212, 'IDE LIMITS', 'Vehicle Models', 'VehicleModels'),
    ('Ped Models', 278, 'IDE LIMITS', 'Ped Models', 'PedModels'),
    ('Weapon Models', 51, 'IDE LIMITS', 'Weapon Models', 'WeaponModels'),
    ('2DFX Effects', 100, 'IDE LIMITS', '2DFX Effects', None),
    ('FILE_TYPE_DFF', 20000, 'ID LIMITS', 'FILE_TYPE_DFF', None),
    ('FILE_TYPE_TXD', 5000, 'ID LIMITS', 'FILE_TYPE_TXD', None),
    ('FILE_TYPE_COL', 255, 'ID LIMITS', 'FILE_TYPE_COL', None),
    ('FILE_TYPE_IPL', 256, 'ID LIMITS', 'FILE_TYPE_IPL', None),
    ('FILE_TYPE_IFP', 180, 'ID LIMITS', 'FILE_TYPE_IFP', None),
    ('Max number of IMG archives', 8, 'IMG LIMITS', 'Max number of IMG archives', None),
    ('Car generators', 500, 'CAR STREAMING', 'Car generators', None),
    ('Object info entries', 160, 'OTHER LIMITS', 'Object info entries', None),
]
# The ID limits only apply with the ID limit patch of fastman92 Limit Adjuster
ID_LIMITS = ('FILE_TYPE_DFF', 'FILE_TYPE_TXD', 'FILE_TYPE_COL', 'FILE_TYPE_IPL', 'FILE_TYPE_IFP')
# Limits that change the format of the savegames, which are only raised when they are too low
SAVEGAME_LIMITS = ('Map zones', 'Navigation zones', 'Pickups')
# Limits that crash the game when both adjusters change them: Open Limit Adjuster's EntityIpl
# patch, with fastman92's also installed, writes one byte off (at 0x405C3C), which corrupts
# CIplStore::LoadIplBoundingBox
CONFLICTING_LIMITS = ('Entity index array',)
# What $$MapLimits.asi takes care of by itself
MAP_LIMITS_ASI_LIMITS = ('Matrices',)

FLA_NAME = 'fastman92 Limit Adjuster'
OLA_NAME = 'Open Limit Adjuster'


@dataclass
class Change:
    """One change to the installation: a setting of an INI file, or files to write."""
    kind: str
    path: str
    description: str
    key: str = ''
    value: str = ''
    section: str = None
    extra: dict = field(default_factory=dict)


@dataclass
class Finding:
    name: str
    needed: str
    current: str
    status: str
    message: str
    changes: list = field(default_factory=list)

    OK = 'ok'
    FIX = 'fix'
    ERROR = 'error'
    INFO = 'info'


def round_up(value):
    # Leaves room for 50% more content and rounds to two significant digits
    value = max(int(value * 1.5), 1)
    magnitude = 10 ** max(len(str(value)) - 2, 0)
    return math.ceil(value / magnitude) * magnitude


def map_size_for(extent):
    for size in MAP_SIZES:
        if size / 2 >= extent:
            return size

    return MAP_SIZES[-1]


def read_text(path):
    with open(path, 'r', encoding='latin-1') as text_file:
        return text_file.read().splitlines()


def split_line(line):
    return [element for element in re.split(r'[,\s]+', line.strip()) if element]


def read_sections(lines, section_names):
    # The lines of each section of an IDE, IPL or ZON file
    sections = {}
    current = None

    for line in lines:
        line = line.split('#')[0].strip()
        lowered = line.lower()

        if not line:
            continue

        if lowered == 'end':
            current = None
        elif current is None and lowered in section_names:
            current = lowered
        elif current is not None:
            sections.setdefault(current, []).append(line)

    return sections


def read_water_lines(path):
    # Each line of a water.dat as its values, read as the game does (commas are spaces)
    lines = []

    if not os.path.isfile(path):
        return lines

    for line in read_text(path):
        values = line.replace(',', ' ').split()

        if values and values[0].lower() != 'processed':
            lines.append(tuple(values))

    return lines


def water_line_key(values):
    # Lines that only differ in how their numbers are written are the same water
    key = []

    for value in values:
        try:
            key.append(round(float(value), 2))
        except ValueError:
            key.append(value.lower())

    return tuple(key)


class GameFiles:
    """Every file the game loads, by name, with the ones of modloader replacing the game's own."""

    def __init__(self, game_dir, include_mods=True):
        self.game_dir = game_dir
        self.modloader_dir = os.path.join(game_dir, 'modloader')
        self.map_files = {}
        self.img_archives = {}
        self.img_entries = {}
        self.object_dat = ''
        self.mods = []

        self._add_directory(os.path.join(game_dir, 'data'))
        self._add_directory(os.path.join(game_dir, 'models'))

        if include_mods and os.path.isdir(self.modloader_dir):
            for mod in sorted(os.listdir(self.modloader_dir)):
                # Modloader ignores the folders whose name starts with a dot
                if not mod.startswith('.') and os.path.isdir(os.path.join(self.modloader_dir, mod)):
                    self.mods.append(mod)
                    self._add_directory(os.path.join(self.modloader_dir, mod), is_mod=True)

    def _add_directory(self, root, is_mod=False):
        for directory, directories, files in os.walk(root):
            directories[:] = [name for name in directories if not name.startswith('.')]

            for file in files:
                path = os.path.join(directory, file)
                name = file.lower()
                file_type = os.path.splitext(name)[1]

                if file_type == '.img':
                    self.img_archives[name] = path
                elif name == 'object.dat':
                    self.object_dat = path
                elif file_type in MAP_FILE_TYPES and not self._is_binary_ipl(path):
                    self.map_files[name] = path
                elif is_mod and file_type in IMG_FILE_TYPES:
                    # Loose files in modloader are loaded as if they were inside an IMG archive
                    self.img_entries[name] = (path, 0, os.path.getsize(path))

    @staticmethod
    def _is_binary_ipl(path):
        with open(path, 'rb') as ipl_file:
            return ipl_file.read(4) == b'bnry'

    def read_img_archives(self):
        for name, path in self.img_archives.items():
            archive = ImgArchive(path)

            for entry, (offset, size) in archive.entries.items():
                # Loose modloader files have priority over the ones inside IMG archives
                if not (entry in self.img_entries and self.img_entries[entry][1] == 0 and
                        not self.img_entries[entry][0].lower().endswith('.img')):
                    self.img_entries[entry] = (path, offset, size)

    def read_entry(self, name):
        path, offset, size = self.img_entries[name]

        with open(path, 'rb') as entry_file:
            entry_file.seek(offset)
            return entry_file.read(size)


def read_collision_bounds(content, bounds):
    # The radius around the origin of each object that contains its collision
    offset = 0

    while offset + 72 <= len(content):
        fourcc = content[offset:offset + 4]

        if fourcc not in (b'COLL', b'COL2', b'COL3', b'COL4'):
            break

        size = struct.unpack_from('<I', content, offset + 4)[0]
        model = content[offset + 8:offset + 30].split(b'\x00')[0].decode('latin-1').lower()

        if fourcc == b'COLL':
            radius, x, y, z = struct.unpack_from('<4f', content, offset + 32)
        else:
            x, y, z, radius = struct.unpack_from('<4f', content, offset + 56)

        is_valid = all(math.isfinite(value) for value in (radius, x, y, z))
        bounds[model] = radius + math.sqrt(x * x + y * y + z * z) if is_valid else 0.0
        offset += 8 + size


def count_sectors(x, y, radius, sector_size):
    columns = math.floor((x + radius) / sector_size) - math.floor((x - radius) / sector_size) + 1
    rows = math.floor((y + radius) / sector_size) - math.floor((y - radius) / sector_size) + 1
    return columns * rows


class InstallationCheck:
    def __init__(self, game_dir, map_limits_asi_source=''):
        """map_limits_asi_source: a built $$MapLimits.asi the fixes can install, if there is one."""
        self.game_dir = game_dir
        self.modloader_dir = os.path.join(game_dir, 'modloader')
        self.map_limits_asi_source = map_limits_asi_source
        self.adjusters = LimitAdjusters(game_dir)

    # Measuring

    def measure(self, progress=print, include_mods=True):
        """
        Counts what the game will load, or what it loads without its mods. Returns the needs by
        limit name and some details.
        """
        files = GameFiles(self.game_dir, include_mods)
        progress('Reading the IMG archives...')
        files.read_img_archives()
        need = dict.fromkeys((limit[0] for limit in LIMITS), 0)
        details = {'mods': files.mods}

        progress('Reading the IDE files...')
        models = {}
        draw_distances = {}
        txd_names = set()
        model_counts = dict.fromkeys(IDE_SECTIONS + ('objs2',), 0)

        for name, path in files.map_files.items():
            if not name.endswith('.ide'):
                continue

            for section, lines in read_sections(read_text(path), IDE_SECTIONS).items():
                for line in lines:
                    elements = split_line(line)

                    if section == '2dfx':
                        model_counts[section] += 1
                        continue

                    if section in ('txdp', 'path') or len(elements) < 3 or not elements[0].lstrip('-').isdigit():
                        continue

                    model_id = int(elements[0])

                    if model_id in models:
                        continue

                    models[model_id] = elements[1].lower()
                    txd_names.add(elements[2].lower())

                    if section == 'objs':
                        try:
                            flags = int(elements[-1])
                            distances = [float(element) for element in elements[3 if len(elements) == 5 else 4:-1]]
                        except ValueError:
                            flags, distances = 0, [0.0]

                        draw_distances[model_id] = max(distances or [0.0])
                        section = 'objs2' if flags & DAMAGEABLE_FLAG else 'objs'

                    model_counts[section] += 1

        need['IDE Objects Type 1'] = model_counts['objs']
        need['IDE Objects Type 2'] = model_counts['objs2']
        need['Timed Objects'] = model_counts['tobj']
        need['Hier Objects'] = model_counts['anim'] + model_counts['hier']
        need['Vehicle Models'] = model_counts['cars']
        need['Ped Models'] = model_counts['peds']
        need['Weapon Models'] = model_counts['weap']
        need['2DFX Effects'] = model_counts['2dfx']
        need['FILE_TYPE_DFF'] = max(models, default=0) + 1

        txd_names.update(name[:-4] for name in files.img_entries if name.endswith('.txd'))
        need['FILE_TYPE_TXD'] = len(txd_names)
        need['FILE_TYPE_COL'] = sum(1 for name in files.img_entries if name.endswith('.col')) + 1
        need['FILE_TYPE_IFP'] = sum(1 for name in files.img_entries if name.endswith('.ifp'))
        need['Max number of IMG archives'] = len(files.img_archives)

        progress('Reading the collisions...')
        bounds = {}

        for name in files.img_entries:
            if name.endswith('.col'):
                read_collision_bounds(files.read_entry(name), bounds)

        need['ColModels'] = len(bounds)
        dynamic_models = set()

        if files.object_dat:
            for line in read_text(files.object_dat):
                elements = split_line(line.split(';')[0])

                if len(elements) > 1 and elements[0][0] not in '#*':
                    dynamic_models.add(elements[0].lower())

            need['Object info entries'] = len(dynamic_models)

        positions = []

        def add_instance(model_id, flags, x, y, rotation_x, rotation_y, is_lod):
            model = models.get(model_id, '')
            is_tilted = (abs(rotation_x) > 0.05 or abs(rotation_y) > 0.05 or
                         (flags & FORCE_MATRIX_FLAG and rotation_x != 0.0 and rotation_y != 0.0))
            is_big = is_lod or draw_distances.get(model_id, 0.0) > BIG_BUILDING_DRAW_DISTANCE
            sectors = count_sectors(x, y, bounds.get(model, 0.0), LOD_SECTOR_SIZE if is_big else SECTOR_SIZE)

            if math.isfinite(x) and math.isfinite(y):
                positions.append(max(abs(x), abs(y)))

            return (0 if model in dynamic_models else 1, 1 if model in dynamic_models else 0,
                    1 if is_tilted else 0, sectors)

        progress('Reading the IPL files...')
        totals = [0, 0, 0, 0]
        stream_owners = set()
        binary_ipls = [name for name in files.img_entries if name.endswith('.ipl')]
        ipl_counts = dict.fromkeys(IPL_SECTIONS, 0)
        largest_file = 0

        for name, path in files.map_files.items():
            if name.endswith('.zon'):
                for line in read_sections(read_text(path), ('zone',)).get('zone', []):
                    elements = split_line(line)

                    if len(elements) > 1 and elements[1].isdigit():
                        need['Map zones' if elements[1] == '3' else 'Navigation zones'] += 1

                continue

            if not name.endswith('.ipl'):
                continue

            sections = read_sections(read_text(path), IPL_SECTIONS)
            instances = []

            for line in sections.get('inst', []):
                elements = split_line(line)

                try:
                    instances.append((int(elements[0]), int(elements[2]), float(elements[3]), float(elements[4]),
                                      float(elements[6]), float(elements[7]), int(elements[10])))
                except (ValueError, IndexError):
                    continue

            lods = {instance[6] for instance in instances if instance[6] >= 0}

            for index, instance in enumerate(instances):
                for i, value in enumerate(add_instance(*instance[:6], index in lods)):
                    totals[i] += value

            largest_file = max(largest_file, len(instances))

            for section in IPL_SECTIONS:
                ipl_counts[section] += len(sections.get(section, []))

            if any(binary.startswith(name[:-4] + '_stream') for binary in binary_ipls):
                stream_owners.add(name)

        for name in binary_ipls:
            content = files.read_entry(name)

            if content[:4] != b'bnry' or len(content) < 32:
                continue

            instances_count, cars_count = struct.unpack_from('<I', content, 4)[0], struct.unpack_from('<I', content, 20)[0]
            instances_offset = struct.unpack_from('<I', content, 28)[0]

            if instances_offset + instances_count * 40 > len(content):
                continue

            ipl_counts['cars'] += cars_count
            instances = [struct.unpack_from('<7f3i', content, instances_offset + i * 40) for i in range(instances_count)]
            lods = {instance[9] for instance in instances if instance[9] >= 0}

            for index, (x, y, z, rotation_x, rotation_y, rotation_z, rotation_w, model_id, flags, lod) in enumerate(instances):
                for i, value in enumerate(add_instance(model_id, flags, x, y, rotation_x, rotation_y, index in lods)):
                    totals[i] += value

        need['Buildings'], need['Dummies'] = totals[0], totals[1]
        need['Matrices'] = totals[2] + DYNAMIC_MATRICES
        need['PtrNode Singles'] = totals[3]
        need['Inst entries per file'] = largest_file
        need['Entity index array'] = len(stream_owners)
        need['FILE_TYPE_IPL'] = len(binary_ipls) + 1
        need['CULL attribute zones'] = ipl_counts['cull']
        need['Entry exits'] = ipl_counts['enex']
        need['Car generators'] = ipl_counts['cars']
        need['Occluders'] = ipl_counts['occl']
        need['Pickups'] = ipl_counts['pick']
        need['Stunt jumps'] = ipl_counts['jump']
        need['Timecycle modifiers'] = ipl_counts['tcyc']
        need['Auzo zone boxes'] = ipl_counts['auzo']

        if not include_mods:
            return need, details

        positions.sort()
        details['map_extent'] = positions[min(len(positions) - 1, int(len(positions) * MAP_EXTENT_PERCENTILE / 100))] \
            if positions else 0.0
        details['radar_tiles'] = max((int(match.group(1)) + 1 for match in
                                      (RADAR_TILE_PATTERN.match(name) for name in files.img_entries) if match), default=0)
        progress('Reading the paths and the water...')
        details['node_files'] = self._list_node_files()
        details['water'] = self._read_water()
        return need, details

    def _list_node_files(self):
        # The node files of each mod: their area numbers, and which ones are in fastman92's format
        node_files = {}

        if not os.path.isdir(self.modloader_dir):
            return node_files

        def add(mod, name, header):
            match = PathPositioner.NODE_FILE_PATTERN.match(name)

            if match:
                area = int(match.group(1))
                node_files.setdefault(mod, {})[area] = self._get_node_file_kind(area, header)

        for mod in os.listdir(self.modloader_dir):
            mod_path = os.path.join(self.modloader_dir, mod)

            if mod.startswith('.') or not os.path.isdir(mod_path):
                continue

            for root, dirs, files in os.walk(mod_path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for file_name in files:
                    path = os.path.join(root, file_name)

                    if file_name.lower().endswith('.img'):
                        archive = ImgArchive(path)

                        try:
                            for name in archive.entries:
                                if PathPositioner.NODE_FILE_PATTERN.match(name):
                                    add(mod, name, archive.read(name)[:32])
                        finally:
                            archive.close()
                    elif PathPositioner.NODE_FILE_PATTERN.match(file_name):
                        with open(path, 'rb') as node_file:
                            add(mod, file_name, node_file.read(32))

        return node_files

    @staticmethod
    def _is_in_original_map(line):
        try:
            return abs(float(line[0])) <= VANILLA_MAP_SIZE / 2 and abs(float(line[1])) <= VANILLA_MAP_SIZE / 2
        except (ValueError, IndexError):
            return False

    NODE_FM92 = 'fm92'
    NODE_EMPTY = 'empty'
    NODE_UNKNOWN = 'unknown'

    @classmethod
    def _get_node_file_kind(cls, area, header):
        """
        Returns NODE_FM92 for a file in fastman92's format, NODE_EMPTY for an empty one in the
        original format, and otherwise the grid width its first node lies in the tile of its
        number for (8 for the original 6000 paths map), or NODE_UNKNOWN.
        """
        if header[:4] == PathPositioner.EXTENDED_MAGIC:
            return cls.NODE_FM92

        if len(header) < 32:
            return cls.NODE_UNKNOWN

        if struct.unpack_from('<I', header, 0)[0] == 0:
            return cls.NODE_EMPTY

        # Each node starts with 8 bytes, then its position in eighths of a unit
        x, y = (value / 8 for value in struct.unpack_from('<2h', header, 28))

        for width in PathPositioner.GRID_WIDTHS:
            half = width * PathPositioner.TILE_SIZE / 2
            column = math.floor((x + half) / PathPositioner.TILE_SIZE)
            row = math.floor((y + half) / PathPositioner.TILE_SIZE)

            if 0 <= column < width and 0 <= row < width and row * width + column == area:
                return width

        return cls.NODE_UNKNOWN

    def _read_water(self):
        # The water of the game and of each mod's water.dat, and what modloader makes of them
        game_path = os.path.join(self.game_dir, 'data', 'water.dat')
        game_lines = read_water_lines(game_path)
        game_keys = {water_line_key(line) for line in game_lines}
        mods = []

        if os.path.isdir(self.modloader_dir):
            for root, dirs, files in os.walk(self.modloader_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for file_name in files:
                    if file_name.lower() == 'water.dat':
                        path = os.path.join(root, file_name)
                        mods.append((path, read_water_lines(path)))

        merged = set(game_keys)

        for path, lines in mods:
            merged.update(water_line_key(line) for line in lines)

        # Modloader drops the lines of the game that any mod leaves out. A mod with water of its own
        # where the original map is replaces the game's on purpose, as total conversions and fixes do
        missing = {path: game_keys - {water_line_key(line) for line in lines} for path, lines in mods}
        replacing = set()

        for path, lines in mods:
            own = [line for line in lines if water_line_key(line) not in game_keys and self._is_in_original_map(line)]

            if missing[path] and len(own) >= len(missing[path]) / 2:
                replacing.add(path)

        replaced = set().union(*(missing[path] for path in replacing)) if replacing else set()

        # Counted as the game will have it once the fixes add the lines other mods leave out
        merged -= replaced

        extent = 0.0
        triangles = sum(1 for key in merged if len(key) == 22)

        for key in merged:
            for start in range(0, len(key) - 1, WATER_VALUES_PER_CORNER):
                if isinstance(key[start], float) and isinstance(key[start + 1], float):
                    extent = max(extent, abs(key[start]), abs(key[start + 1]))

        return {'game_path': game_path, 'game_count': len(game_keys), 'mods': mods, 'missing': missing,
                'replacing': replacing, 'replaced': replaced,
                'quads': len(merged) - triangles, 'triangles': triangles, 'extent': extent}

    # Checking

    def run(self, progress=print):
        """Returns what was found, as a list of findings."""
        findings = []

        if not os.path.isfile(os.path.join(self.game_dir, 'gta_sa.exe')) and not os.path.isdir(os.path.join(self.game_dir, 'data')):
            return [Finding('Game folder', '', '', Finding.ERROR, f'{self.game_dir} is not a GTA San Andreas folder.')]

        findings.append(self._check_adjusters())
        findings.append(self._check_map_limits_asi())
        need, details = self.measure(progress)
        progress('Counting what the game has without its mods...')
        game_need, _ = self.measure(lambda message: None, include_mods=False)
        progress('Comparing with the limits...')

        for name, vanilla, section, key, ola_key in LIMITS:
            # The counts are estimates that are higher than what the game really uses (the objects of
            # binary IPL files are counted as if they were all loaded), so what the game's own files
            # are counted over its limits is taken away, as they fit
            needed = need[name] - max(0, game_need[name] - vanilla)
            findings.append(self._check_limit(name, vanilla, section, key, ola_key, needed))

        findings += self._check_map(details)
        findings += self._check_water(details['water'])
        findings += self._check_paths(details['node_files'])
        return [finding for finding in findings if finding is not None]

    def _check_adjusters(self):
        adjusters = self.adjusters
        found = []

        if adjusters.has_fla:
            found.append(FLA_NAME if adjusters.fla_asi else f'{FLA_NAME} (INI only, its ASI is missing)')
        if adjusters.has_ola:
            found.append(OLA_NAME if adjusters.ola_asi else f'{OLA_NAME} (INI only, its ASI is missing)')
        if adjusters.map_limits_asi:
            found.append('$$MapLimits.asi')

        if (adjusters.has_fla and not adjusters.fla_asi) or (adjusters.has_ola and not adjusters.ola_asi):
            return Finding('Limit adjusters', '', ', '.join(found), Finding.ERROR,
                           'A limit adjuster has its INI but not its ASI, so the game does not use its settings. '
                           'Install it again.')

        return Finding('Limit adjusters', '', ', '.join(found) or 'none', Finding.INFO,
                       'Found: ' + (', '.join(found) if found else 'no limit adjuster, so the game has its own limits.'))

    def _asi_change(self, reason):
        destination = os.path.join(self.game_dir, LimitAdjusters.MAP_LIMITS_ASI_NAME)
        return Change('copy_file', destination, f'Install {LimitAdjusters.MAP_LIMITS_ASI_NAME} in the game folder ({reason})',
                      extra={'source': self.map_limits_asi_source})

    def _check_map_limits_asi(self):
        # An installed $$MapLimits.asi that is not the one of this tool may be an older one, which
        # also changes fastman92's INI each time the game starts
        installed, source = self.adjusters.map_limits_asi, self.map_limits_asi_source

        if not installed or not source or not os.path.isfile(source):
            return None

        with open(installed, 'rb') as installed_file, open(source, 'rb') as source_file:
            if installed_file.read() == source_file.read():
                return Finding('$$MapLimits.asi', '', 'up to date', Finding.OK, '')

        return Finding('$$MapLimits.asi', '', 'another version', Finding.FIX,
                       "Versions older than this tool's also raise limits in fastman92's INI each time the game "
                       'starts, and leave the Entity index array to Open Limit Adjuster, which crashes the game '
                       'when both adjusters are installed.', [self._asi_change('update')])

    def _fla_change(self, key, value, section, reason):
        return Change('ini_set', self.adjusters.fla.path, f'{FLA_NAME}: {key} = {value} ({reason})', key, str(value), section)

    def _ola_change(self, key, value, reason):
        return Change('ini_set', self.adjusters.ola.path, f'{OLA_NAME}: {key} = {value} ({reason})', key, str(value),
                      LimitAdjusters.OLA_SECTION)

    def _check_limit(self, name, vanilla, section, key, ola_key, needed):
        adjusters = self.adjusters
        fla_value = adjusters.fla.get_number(key, section) if adjusters.has_fla else None
        ola_value = adjusters.ola.get_number(ola_key, LimitAdjusters.OLA_SECTION) if adjusters.has_ola and ola_key else None
        shown = lambda value: '-' if value is None else ('unlimited' if value >= UNLIMITED else str(value))
        current_text = f'{FLA_NAME[:9]} {shown(fla_value)} / {OLA_NAME[:4]} {shown(ola_value)}'

        if name in MAP_LIMITS_ASI_LIMITS and adjusters.map_limits_asi:
            return Finding(name, str(needed), '$$MapLimits.asi', Finding.OK, '$$MapLimits.asi removes this limit.')

        if (name in MAP_LIMITS_ASI_LIMITS and needed > max([v for v in (fla_value, ola_value) if v is not None] + [vanilla])
                and self.map_limits_asi_source and os.path.isfile(self.map_limits_asi_source)):
            return Finding(name, str(needed), current_text, Finding.FIX, f'$$MapLimits.asi removes this limit.',
                           [self._asi_change(f'{needed} needed')])

        if name in CONFLICTING_LIMITS and fla_value is not None and ola_value is not None:
            value = max(fla_value, round_up(needed), 5000)
            return Finding(name, str(needed), current_text, Finding.FIX,
                           f'Both limit adjusters change it, which crashes the game while loading the map '
                           f'(Open Limit Adjuster writes its patch one byte off when fastman92 Limit Adjuster is '
                           f'also installed). Only {FLA_NAME} should.',
                           [Change('ini_off', adjusters.ola.path, f'{OLA_NAME}: turn off {ola_key}', ola_key,
                                   section=LimitAdjusters.OLA_SECTION),
                            self._fla_change(key, value, section, f'{needed} needed')])

        if name in ID_LIMITS and fla_value is not None and not adjusters.fla.get_number('Apply ID limit patch', 'ID LIMITS'):
            fla_value = None

        values = [value for value in (fla_value, ola_value) if value is not None]
        current = max(values) if values else vanilla

        if needed <= current:
            return Finding(name, str(needed), current_text if values else f'{vanilla} (the game\'s own)', Finding.OK, '')

        target = round_up(needed)
        reason = f'{needed} needed'

        if name in CONFLICTING_LIMITS and adjusters.has_fla:
            # Even alone, this one is left to fastman92's patch when it is installed
            changes = [self._fla_change(key, max(target, 5000), section, reason)]
        elif ola_value is not None and fla_value is None and name not in CONFLICTING_LIMITS:
            # A limit Open Limit Adjuster already takes care of stays with it
            changes = [self._ola_change(ola_key, target, reason)]
        elif adjusters.has_fla:
            changes = [self._fla_change(key, target, section, reason)]

            if name in ID_LIMITS:
                changes.insert(0, self._fla_change('Apply ID limit patch', 1, 'ID LIMITS', 'for the ID limits'))
        elif adjusters.has_ola and ola_key:
            changes = [self._ola_change(ola_key, target, reason)]
        else:
            fix = FLA_NAME if not ola_key else f'{FLA_NAME} or {OLA_NAME}'
            return Finding(name, str(needed), f'{current} (the game\'s own)', Finding.ERROR,
                           f'The game can only hold {current}. Install {fix}, then check again.')

        message = f'Only {current} fit.'

        if name in SAVEGAME_LIMITS:
            message += ' Raising it changes the format of the savegames: older ones may not load.'

        return Finding(name, str(needed), current_text, Finding.FIX, message, changes)

    def _check_size(self, name, key, needed, reason, extra_changes=()):
        # A map size of fastman92 Limit Adjuster, which Open Limit Adjuster does not have
        adjusters = self.adjusters
        current = adjusters.fla.get_number(key) if adjusters.has_fla else None
        current = current or VANILLA_MAP_SIZE

        if needed <= current and not extra_changes:
            return Finding(name, str(needed), str(current), Finding.OK, reason)

        if not adjusters.has_fla:
            return Finding(name, str(needed), str(current), Finding.ERROR,
                           f'{reason} Only {FLA_NAME} can make it bigger: install it, then check again.')

        changes = list(extra_changes)

        if needed > current:
            changes.append(self._fla_change(key, needed, 'MAP LIMITS', reason.rstrip('.')))

        return Finding(name, str(needed), str(current), Finding.FIX, reason, changes)

    def _check_map(self, details):
        findings = []
        extent = details['map_extent']
        world_size = map_size_for(extent)
        reason = f'The mods place objects up to {extent:.0f} units from the center.'

        if world_size > VANILLA_MAP_SIZE:
            findings.append(self._check_size('World map size', 'World map size', world_size, reason))
            findings.append(self._check_size('Renderware world map size', 'Renderware world map size', world_size, reason))

        tiles = details['radar_tiles']

        if tiles > 144:
            tiles_per_row = math.isqrt(tiles - 1) + 1
            findings.append(self._check_size('Radar map size', 'Radar map size', tiles_per_row * RADAR_TILE_SIZE,
                                             f'The radar has {tiles} tiles ({tiles_per_row} per row).'))

        return findings

    def _check_water(self, water):
        findings = []
        adjusters = self.adjusters
        fla = adjusters.fla if adjusters.has_fla else None
        quads_count, triangles_count = water['quads'], water['triangles']
        quads = (fla.get_number('Water quads') if fla else None) or 301
        triangles = (fla.get_number('Water triangles') if fla else None) or 6
        lists = (fla.get_number('Water quads and triangles list') if fla else None) or 701
        vertices = (fla.get_number('Water vertices') if fla else None) or 1021
        total = quads_count + triangles_count
        # The game's own 307 lines take 701 places of the list and 1021 vertices
        needed = {'Water quads': (quads_count, quads, -(-quads_count * 2 // 500) * 500),
                  'Water triangles': (triangles_count, triangles, max(100, triangles_count * 2)),
                  'Water quads and triangles list': (math.ceil(total * 701 / 307), lists, -(-total * 8 // 500) * 500),
                  'Water vertices': (math.ceil(total * 1021 / 307), vertices, -(-total * 8 // 500) * 500)}
        too_low = {key: values for key, values in needed.items() if values[0] > values[1]}
        current = f'{quads} quads and {triangles} triangles'
        count_text = f'{quads_count} quads and {triangles_count} triangles'

        if not too_low:
            findings.append(Finding('Water', count_text, current, Finding.OK, ''))
        elif fla:
            findings.append(Finding('Water', count_text, current, Finding.FIX,
                                    'Modloader merges every water.dat, and the game crashes while loading more water '
                                    'than it holds.',
                                    [self._fla_change(key, target, 'WATER LIMITS', f'{count} needed')
                                     for key, (count, _, target) in too_low.items()]))
        else:
            findings.append(Finding('Water', count_text, current, Finding.ERROR,
                                    f'The game crashes while loading more water than it holds. Only {FLA_NAME} can '
                                    'raise these limits: install it, then check again.'))

        if water['extent'] > VANILLA_MAP_SIZE / 2:
            findings.append(self._check_size('Water map size', 'Water map size', map_size_for(water['extent']),
                                             f'There is water up to {water["extent"]:.0f} units from the center.'))

        if water['game_count']:
            for path in sorted(water['replacing']):
                mod_name = os.path.relpath(path, self.modloader_dir)
                findings.append(Finding(f'Water of {mod_name}', '', f'replaces {len(water["missing"][path])} of the '
                                        'game\'s lines', Finding.INFO,
                                        'It has its own water where the original map is, so it is left as it is.'))

            for path, missing in water['missing'].items():
                missing = missing - water['replaced']

                if not missing or path in water['replacing']:
                    continue

                mod_name = os.path.relpath(path, self.modloader_dir)
                findings.append(Finding(f'Water of {mod_name}', '', f'{len(missing)} of the game\'s lines left out',
                                        Finding.FIX,
                                        'Modloader removes the water of the game that any water.dat leaves out, '
                                        'so the original sea disappears.',
                                        [Change('water_lines', path, f'{mod_name}: add the {len(missing)} lines of the '
                                                f'game\'s water.dat it leaves out',
                                                extra={'source': water['game_path'], 'skipped': water['replaced']})]))

        return findings

    def _check_paths(self, node_files):
        findings = []
        adjusters = self.adjusters
        mods = {mod: areas for mod, areas in node_files.items() if mod.lower() != BASE_PATHS_MOD_NAME}
        extended = [area for areas in mods.values() for area, kind in areas.items() if kind != 8 and kind != self.NODE_EMPTY
                    and kind != self.NODE_UNKNOWN]
        size, is_set = adjusters.get_fla('Paths map size', VANILLA_MAP_SIZE) if adjusters.has_fla else (VANILLA_MAP_SIZE, False)
        patch = adjusters.get_fla('Apply paths limit patch', 0)[0] if adjusters.has_fla else 0
        current = size if patch else VANILLA_MAP_SIZE
        needed = current

        if extended:
            # The tile numbers tell the smallest grid the files were made for, or their nodes do
            highest = max(extended)
            widths = [width for width in PathPositioner.GRID_WIDTHS if width * width > highest]
            needed = max(current if current > VANILLA_MAP_SIZE else 0,
                         (widths[0] if widths else PathPositioner.GRID_WIDTHS[-1]) * PathPositioner.TILE_SIZE,
                         VANILLA_MAP_SIZE * 2)

        if needed == VANILLA_MAP_SIZE:
            return findings

        reason = f'The mods have node files made for a {needed} paths map.' if extended else \
            f'The game uses a {needed} paths map.'
        changes = []

        if needed != current or not patch:
            if not adjusters.has_fla:
                return [Finding('Paths map size', str(needed), str(current), Finding.ERROR,
                                f'{reason} Only {FLA_NAME} loads them: install it, then check again.')]

            changes = [self._fla_change('Apply paths limit patch', 1, 'MAP LIMITS', 'for the paths map'),
                       self._fla_change('Paths map size', needed, 'MAP LIMITS', 'for the node files of the mods')]

        findings.append(Finding('Paths map size', str(needed), str(current), Finding.FIX if changes else Finding.OK,
                                reason, changes))

        grid_width = needed // PathPositioner.TILE_SIZE

        for mod, areas in mods.items():
            # Files whose nodes are laid out for the original map, at its tile numbers
            wrong = [area for area, kind in areas.items() if kind == PathPositioner.VANILLA_GRID_WIDTH]

            if wrong:
                findings.append(Finding(f'Paths of {mod}', '', f'{len(wrong)} node files for the original 6000 map',
                                        Finding.ERROR,
                                        f'The game uses a {needed} paths map, where these tile numbers are other '
                                        f'places, so their roads end up in the wrong tiles. Regenerate this mod with '
                                        f'the tool for a {needed} map size, or remove its node files.'))

        # Every tile needs a file: the original map's converted, and empty ones where nothing is
        covered = {area for areas in mods.values() for area in areas}
        base = node_files.get(BASE_PATHS_MOD_NAME, {})
        missing = [area for area in range(grid_width * grid_width) if area not in covered and area not in base]
        doubled = sorted(covered & set(base))
        outside = [area for area in base if area >= grid_width * grid_width]

        if missing or doubled or outside:
            problems = []

            if missing:
                problems.append(f'{len(missing)} of the {grid_width * grid_width} tiles have no node file')
            if doubled:
                problems.append(f'{len(doubled)} tiles have a file both in {BASE_PATHS_MOD_NAME} and in a mod')
            if outside:
                problems.append(f'{BASE_PATHS_MOD_NAME} was made for another paths map size')

            findings.append(Finding('Base paths', str(grid_width * grid_width), f'{len(covered | set(base))} tiles',
                                    Finding.FIX,
                                    '; '.join(problems).capitalize() + '. The game needs one file for every tile, '
                                    'with the original roads converted to the new grid.',
                                    [Change('base_paths', os.path.join(self.modloader_dir, BASE_PATHS_MOD_NAME),
                                            f'Write modloader\\{BASE_PATHS_MOD_NAME}: the original roads for a {needed} '
                                            f'paths map, and empty files for the tiles no mod has',
                                            value=str(needed))]))
        else:
            findings.append(Finding('Base paths', str(grid_width * grid_width), 'complete', Finding.OK, ''))

        return findings

    # Fixing

    def apply(self, findings, progress=print):
        """
        Makes the changes of the findings to fix. Every file they touch is copied first to a new
        backup folder, whose path is returned.
        """
        changes = [change for finding in findings if finding.status == Finding.FIX for change in finding.changes]

        if not changes:
            return ''

        backup_dir = os.path.join(self.game_dir, BACKUP_DIR_NAME, time.strftime('%Y%m%d-%H%M%S'))
        os.makedirs(backup_dir, exist_ok=True)
        manifest = {'files': [], 'created': [], 'folders': [], 'changes': [change.description for change in changes]}

        def back_up(path, is_folder=False):
            relative = os.path.relpath(path, self.game_dir)

            if relative in manifest['files'] or relative in manifest['folders'] or relative in manifest['created']:
                return

            if not os.path.exists(path):
                manifest['created'].append(relative)
                return

            destination = os.path.join(backup_dir, 'files', relative)
            os.makedirs(os.path.dirname(destination), exist_ok=True)

            if is_folder:
                shutil.copytree(path, destination)
                manifest['folders'].append(relative)
            else:
                shutil.copy2(path, destination)
                manifest['files'].append(relative)

        for change in changes:
            back_up(change.path, is_folder=change.kind == 'base_paths')

        with open(os.path.join(backup_dir, 'manifest.json'), 'w', encoding='utf-8') as manifest_file:
            json.dump(manifest, manifest_file, indent=2)

        ini_files = {}

        for change in changes:
            progress(change.description)

            if change.kind in ('ini_set', 'ini_off'):
                ini = self._get_ini(change.path, ini_files)

                if change.kind == 'ini_set':
                    ini.set(change.key, change.value, change.section)
                else:
                    ini.turn_off(change.key, change.section)
            elif change.kind == 'water_lines':
                self._add_water_lines(change.path, change.extra['source'], change.extra.get('skipped', ()))
            elif change.kind == 'base_paths':
                PathPositioner().build_base_set(self.game_dir, int(change.value), os.path.join(change.path, 'gta3.img'),
                                                skipped_mods=[BASE_PATHS_MOD_NAME])
            elif change.kind == 'copy_file':
                shutil.copy2(change.extra['source'], change.path)

        for ini in ini_files.values():
            ini.save()

        return backup_dir

    def _get_ini(self, path, ini_files):
        if path not in ini_files:
            adjusters = self.adjusters
            ini_files[path] = next(ini for ini in (adjusters.fla, adjusters.ola) if ini is not None and ini.path == path)

        return ini_files[path]

    @staticmethod
    def _add_water_lines(path, game_path, skipped=()):
        # The game's lines go first, as in the files this tool writes, followed by the mod's own
        with open(path, 'r', encoding='latin-1') as water_file:
            lines = water_file.read().splitlines()

        keys = {water_line_key(line.replace(',', ' ').split()) for line in lines}
        game_lines = [line for line in read_text(game_path) if line.strip() and line.strip().lower() != 'processed']
        added = [line for line in game_lines if water_line_key(line.replace(',', ' ').split()) not in keys | set(skipped)]
        header = [line for line in lines[:1] if line.strip().lower() == 'processed']
        body = lines[len(header):]

        with open(path, 'w', encoding='latin-1', newline='\r\n') as water_file:
            water_file.write('\n'.join(header + added + body) + '\n')

    def list_backups(self):
        backups_dir = os.path.join(self.game_dir, BACKUP_DIR_NAME)

        if not os.path.isdir(backups_dir):
            return []

        return sorted(os.path.join(backups_dir, name) for name in os.listdir(backups_dir)
                      if os.path.isfile(os.path.join(backups_dir, name, 'manifest.json')))

    def restore(self, backup_dir, progress=print):
        """Puts back what a backup folder has, and removes what the changes after it created."""
        with open(os.path.join(backup_dir, 'manifest.json'), 'r', encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)

        for relative in manifest['created']:
            path = os.path.join(self.game_dir, relative)

            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)

        for relative in manifest['folders']:
            path = os.path.join(self.game_dir, relative)

            if os.path.isdir(path):
                shutil.rmtree(path)

            shutil.copytree(os.path.join(backup_dir, 'files', relative), path)

        for relative in manifest['files']:
            shutil.copy2(os.path.join(backup_dir, 'files', relative), os.path.join(self.game_dir, relative))

        progress(f'Restored {len(manifest["files"]) + len(manifest["folders"])} files and folders, and removed '
                 f'{len(manifest["created"])} created ones, from {backup_dir}.')
        shutil.rmtree(backup_dir)


def format_findings(findings):
    labels = {Finding.OK: 'OK', Finding.FIX: 'FIX', Finding.ERROR: 'PROBLEM', Finding.INFO: 'INFO'}
    lines = []

    for finding in findings:
        text = f'[{labels[finding.status]}] {finding.name}'

        if finding.needed:
            text += f': needs {finding.needed}, has {finding.current}'
        elif finding.current:
            text += f': {finding.current}'

        if finding.message:
            text += f'. {finding.message}'

        lines.append(text)

        for change in finding.changes:
            lines.append(f'      -> {change.description}')

    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    check = InstallationCheck(sys.argv[1])
    findings = check.run()
    print()
    print(format_findings(findings))
    return 0


if __name__ == '__main__':
    sys.exit(main())
