import os
import re

from application.tools.limit_adjusters import UNLIMITED, LimitAdjusters
from application.tools.radar_generator import ImgArchive


class GameLimits:
    """
    Reads the limits that fastman92 Limit Adjuster sets in a game folder, and warns when a map
    needs more than that. Each check prints what to change in the INI, since the game either
    crashes or ignores the files when they are over these limits.
    """

    INI_NAME = LimitAdjusters.FLA_INI_NAME
    UNLIMITED = UNLIMITED

    # The game's own values, used when the INI leaves a line commented out
    DEFAULTS = {
        'Paths map size': 6000,
        'Radar map size': 6000,
        'Water map size': 6000,
        'Water quads': 301,
        'Water vertices': 1021,
        'Entity index array': 40,
    }

    STREAM_IPL_PATTERN = re.compile(r'^(.+)_stream\d+\.ipl$', re.IGNORECASE)
    # The position of each corner of a water.dat line is followed by 5 other values
    WATER_VALUES_PER_CORNER = 7

    def __init__(self, game_dir):
        self.game_dir = game_dir or ''
        self.adjusters = LimitAdjusters(self.game_dir)
        self.has_ini = self.adjusters.has_fla

    def get(self, name):
        """Returns the value the game uses and whether the INI sets it."""
        return self.adjusters.get_fla(name, self.DEFAULTS.get(name, 0))

    @staticmethod
    def warn(message):
        print(f'(limits) WARNING: {message}')

    # Water

    @classmethod
    def read_water_lines(cls, file_path):
        lines = []

        if not os.path.isfile(file_path):
            return lines

        with open(file_path, 'r', encoding='latin-1') as water_file:
            for line in water_file:
                values = line.replace(',', ' ').split()

                if values and values[0].lower() != 'processed':
                    lines.append(tuple(values))

        return lines

    def check_water(self, water_lines):
        """water_lines: every line the game will read, after modloader merges all water.dat files."""
        if not self.has_ini or not water_lines:
            return

        quads, quads_set = self.get('Water quads')

        if len(water_lines) > quads:
            self.warn(f'the game will read {len(water_lines)} water quads and triangles, but it can only hold {quads}. '
                      f'Set "Water quads = {self._round_up(len(water_lines) * 2)}", '
                      f'"Water vertices = {self._round_up(len(water_lines) * 8)}" and '
                      f'"Water quads and triangles list = {self._round_up(len(water_lines) * 8)}" in {self.INI_NAME}, '
                      'or the game crashes while loading water.dat.')

        water_map_size, _ = self.get('Water map size')
        extent = 0

        for values in water_lines:
            for start in range(0, len(values) - 1, self.WATER_VALUES_PER_CORNER):
                try:
                    extent = max(extent, abs(float(values[start])), abs(float(values[start + 1])))
                except ValueError:
                    break

        if extent > water_map_size / 2:
            self.warn(f'there is water up to {extent:.0f} units from the center of the map, but the water map is only '
                      f'{water_map_size}x{water_map_size}. Set "Water map size" in {self.INI_NAME} to at least '
                      f'{self._map_size_for(extent)}, or the game crashes while loading water.dat.')

    # Stream IPLs

    def count_stream_ipl_groups(self, extra_sources=()):
        """
        Counts the text IPLs that have stream (binary) IPLs in the game, its modloader mods and
        the given IMG files or folders. The game keeps one entity index array for each.
        """
        sources = [os.path.join(self.game_dir, 'models', 'gta3.img')]
        modloader_dir = os.path.join(self.game_dir, 'modloader')

        if os.path.isdir(modloader_dir):
            for root, dirs, files in os.walk(modloader_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for name in dirs + files:
                    if name.lower().endswith('.img'):
                        sources.append(os.path.join(root, name))

        groups = set()

        for source in list(sources) + list(extra_sources):
            if os.path.isdir(source):
                names = [name.lower() for name in os.listdir(source)]
            elif os.path.isfile(source):
                archive = ImgArchive(source)
                names = list(archive.entries)
            else:
                continue

            for name in names:
                match = self.STREAM_IPL_PATTERN.match(name)

                if match:
                    groups.add(match.group(1))

        return len(groups)

    def check_stream_ipls(self, extra_sources=()):
        if not self.has_ini:
            return

        needed = self.count_stream_ipl_groups(extra_sources)
        limit, _ = self.get('Entity index array')

        if needed > limit:
            self.warn(f'{needed} text IPL files have stream IPLs, but the game only has {limit} entity index arrays. '
                      f'Set "Entity index array = 5000" in {self.INI_NAME}, or the game crashes while loading the map.')

        self.check_open_limit_adjuster()

    def check_open_limit_adjuster(self):
        # With fastman92 Limit Adjuster also installed, Open Limit Adjuster's EntityIpl patch writes
        # the new array one byte too early (at 0x405C3C), which corrupts CIplStore::LoadIplBoundingBox
        ola = self.adjusters.ola

        if ola is not None and ola.get('EntityIpl') is not None:
            self.warn(f'Open Limit Adjuster sets EntityIpl in {ola.path}. Together with fastman92 Limit Adjuster '
                      'it corrupts the game code and the game crashes while loading the map. The "Check '
                      'installation" button fixes it.')

    # Paths

    def check_paths(self, written_map_size):
        """Warns when node files are written for a grid other than the one the game loads."""
        if not self.game_dir:
            return

        paths_map_size, _ = self.get('Paths map size')
        patch, _ = self.get('Apply paths limit patch')

        if int(written_map_size) == paths_map_size and (paths_map_size == 6000 or patch):
            return

        if int(written_map_size) == 6000:
            self.warn(f'the node files were made for the original 6000 paths map, but the game uses {paths_map_size}. '
                      f'Choose {paths_map_size} as the map size, or the game will not load these paths.')
        else:
            self.warn(f'the node files were made for a {written_map_size} paths map, but the game uses '
                      f'{paths_map_size}{" without the paths limit patch" if not patch else ""}. Set '
                      f'"Apply paths limit patch = 1" and "Paths map size = {written_map_size}" in {self.INI_NAME}, '
                      'and install a full set of node files for that size (the "Check installation" button). '
                      'Otherwise the game will not load these paths, and node files numbered over 63 can '
                      'overwrite the animation files the game streams, which crashes it.')

    @staticmethod
    def _round_up(value, step=500):
        return -(-int(value) // step) * step

    @staticmethod
    def _map_size_for(extent):
        for size in (6000, 12000, 24000, 48000):
            if size / 2 >= extent:
                return size

        return 48000
