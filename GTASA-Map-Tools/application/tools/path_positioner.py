import os
import re
import struct


class PathPositioner:
    """
    Repositions path node files (nodes*.dat).

    Paths are split in square tiles of 750 units, one file per tile, numbered row by row from the
    south-west corner of the map. Moving paths therefore means shifting the coordinates stored in
    each file, renumbering the files and updating every reference to a tile number inside of them.
    For that reason paths can only be moved in steps of 750 units on the X and Y axes.

    Supported formats:

    ==========  ==========  ==========  ==========================================
    format      node size   navi size   notes
    ==========  ==========  ==========  ==========================================
    vanilla     28 bytes    14 bytes    8x8 tiles only (6000x6000 map)
    FM92 VER2   40 bytes    22 bytes    fastman92 limit adjuster, any map size
    FM92 VER3   42 bytes    22 bytes    fastman92 limit adjuster, any map size
    ==========  ==========  ==========  ==========================================

    Vanilla files are kept in the vanilla format when the target map is 6000x6000 and converted to
    FM92 VER2 otherwise. FM92 files keep their own version.
    """

    TILE_SIZE = 750
    COORD_SCALE = 8
    VANILLA_GRID_WIDTH = 8
    GRID_WIDTHS = (8, 16, 32, 64)
    NODE_FILE_PATTERN = re.compile(r'^nodes(\d+)\.dat$', re.IGNORECASE)

    EXTENDED_MAGIC = b"\xff\xff\xff\xff"
    FM92_TAG = b"FM92"
    FM92_PREFIX = EXTENDED_MAGIC + FM92_TAG + b"\x0b\x00fastman92\x00"
    FM92_EOF = b"EOF\x00"
    COUNTS_SIZE = 20
    FILLER_SIZE = 768
    TRAILER_SIZE = 384

    # Offsets are relative to the start of each record
    LAYOUT_VANILLA = {
        'name': 'vanilla', 'counts_offset': 0,
        'node_size': 28, 'node_area': 18, 'node_pos': 8, 'pos_format': '<h',
        'navi_size': 14, 'navi_area': 4, 'navi_pos': 0,
        'link_size': 4, 'link_area': 0,
        'navi_link_size': 2, 'navi_link_area': None,
    }
    LAYOUT_FM92_VER2 = {
        'name': 'FM92 VER2', 'counts_offset': 24,
        'node_size': 40, 'node_area': 18, 'node_pos': 28, 'pos_format': '<i',
        'navi_size': 22, 'navi_area': 4, 'navi_pos': 14,
        'link_size': 4, 'link_area': 0,
        'navi_link_size': 4, 'navi_link_area': 2,
    }
    LAYOUT_FM92_VER3 = dict(LAYOUT_FM92_VER2, name='FM92 VER3', node_size=42)
    FM92_LAYOUTS = {b"VER2": LAYOUT_FM92_VER2, b"VER3": LAYOUT_FM92_VER3}

    class UnsupportedFormatError(Exception):
        pass

    class OutOfBoundsError(Exception):
        pass

    def __init__(self):
        pass

    def run(self, input_dir, output_dir, map_command_x, map_command_y, map_command_z, map_size=6000):
        try:
            node_files = self._read_node_files(input_dir)

            if not node_files:
                print("(paths) No node files to move.")
                return False

            moved_files = self._move_node_files(node_files, map_command_x, map_command_y, map_command_z, map_size)
        except (self.UnsupportedFormatError, self.OutOfBoundsError, OSError) as e:
            print(f"Error while moving paths: {e}")
            return False

        os.makedirs(output_dir, exist_ok=True)

        for file_name, content in moved_files.items():
            with open(os.path.join(output_dir, file_name), 'wb') as f:
                f.write(content)

        print(f"(paths) {len(moved_files)} node files moved.")
        return bool(moved_files)

    # Reading

    def _read_node_files(self, input_dir):
        node_files = []

        if not os.path.isdir(input_dir):
            return node_files

        for file_name in os.listdir(input_dir):
            match = self.NODE_FILE_PATTERN.match(file_name)

            if not match:
                continue

            with open(os.path.join(input_dir, file_name), 'rb') as f:
                data = f.read()

            layout = self._detect_layout(file_name, data)
            counts = self._read_counts(data, layout)
            node_files.append({'name': file_name, 'area': int(match.group(1)), 'data': data,
                               'layout': layout, 'counts': counts, 'is_empty': not any(counts)})

        node_files.sort(key=lambda node_file: node_file['area'])
        return node_files

    def _detect_layout(self, file_name, data):
        if data[:4] != self.EXTENDED_MAGIC:
            return self.LAYOUT_VANILLA

        tag = data[4:8]
        version = data[20:24]

        if tag != self.FM92_TAG or version not in self.FM92_LAYOUTS:
            description = tag.decode('ascii', errors='replace')

            if tag == self.FM92_TAG:
                description += ' ' + version.decode('ascii', errors='replace')

            raise self.UnsupportedFormatError(f"{file_name} uses the unsupported node format '{description}'.")

        return self.FM92_LAYOUTS[version]

    def _read_counts(self, data, layout):
        counts_offset = layout['counts_offset']

        if len(data) < counts_offset + self.COUNTS_SIZE:
            return (0, 0, 0, 0, 0)

        return struct.unpack_from('<5I', data, counts_offset)

    def _get_sections(self, node_file):
        # Returns the offset of each section: nodes, navi nodes, links, navi links and the end of them
        layout = node_file['layout']
        nodes_count, _, _, navis_count, links_count = node_file['counts']

        nodes = layout['counts_offset'] + self.COUNTS_SIZE
        navis = nodes + nodes_count * layout['node_size']
        links = navis + navis_count * layout['navi_size']
        navi_links = links + links_count * layout['link_size'] + self.FILLER_SIZE
        end = navi_links + links_count * layout['navi_link_size']

        if links + links_count * layout['link_size'] > len(node_file['data']):
            raise self.UnsupportedFormatError(f"{node_file['name']} is truncated or is not a valid node file.")

        return nodes, navis, links, navi_links, end

    # Grid

    def _detect_grid_width(self, node_files):
        # Vanilla files can only address 64 tiles, while the amount of tiles of FM92 files depends
        # on the map size they were made for, which is found by checking which grid puts the nodes
        # in the tile they claim to be in
        extended_files = [node_file for node_file in node_files
                          if node_file['layout'] is not self.LAYOUT_VANILLA and not node_file['is_empty']]

        if not extended_files:
            return self.VANILLA_GRID_WIDTH

        votes = dict.fromkeys(self.GRID_WIDTHS, 0)

        for node_file in extended_files:
            layout = node_file['layout']
            data = node_file['data']
            nodes = self._get_sections(node_file)[0]

            for index in range(min(node_file['counts'][0], 16)):
                offset = nodes + index * layout['node_size']
                x, y = struct.unpack_from('<2i', data, offset + layout['node_pos'])
                area = struct.unpack_from('<H', data, offset + layout['node_area'])[0]

                for width in self.GRID_WIDTHS:
                    half_map = width * self.TILE_SIZE / 2
                    column = int((x / self.COORD_SCALE + half_map) // self.TILE_SIZE)
                    row = int((y / self.COORD_SCALE + half_map) // self.TILE_SIZE)

                    if 0 <= column < width and 0 <= row < width and row * width + column == area:
                        votes[width] += 1

        best_width = max(self.GRID_WIDTHS, key=lambda width: votes[width])

        if votes[best_width] == 0:
            highest_area = max(node_file['area'] for node_file in node_files)
            best_width = next((width for width in self.GRID_WIDTHS if width * width > highest_area),
                              self.GRID_WIDTHS[-1])

        return best_width

    # Moving

    def _move_node_files(self, node_files, offset_x, offset_y, offset_z, map_size):
        source_width = self._detect_grid_width(node_files)
        target_width = int(map_size) // self.TILE_SIZE

        if target_width not in self.GRID_WIDTHS:
            raise self.UnsupportedFormatError(f"{map_size} is not a supported map size for paths.")

        tiles_x = round(offset_x / self.TILE_SIZE)
        tiles_y = round(offset_y / self.TILE_SIZE)

        if tiles_x * self.TILE_SIZE != offset_x or tiles_y * self.TILE_SIZE != offset_y:
            print(f"(paths) Paths can only be moved in steps of {self.TILE_SIZE} units, "
                  f"so they will be moved X: {tiles_x * self.TILE_SIZE}, Y: {tiles_y * self.TILE_SIZE}")

        # Both grids are centered on the map
        centering = (target_width - source_width) // 2
        column_shift = centering + tiles_x
        row_shift = centering + tiles_y
        delta = (tiles_x * self.TILE_SIZE * self.COORD_SCALE,
                 tiles_y * self.TILE_SIZE * self.COORD_SCALE,
                 round(offset_z * self.COORD_SCALE))
        keep_vanilla = target_width == self.VANILLA_GRID_WIDTH and source_width == self.VANILLA_GRID_WIDTH

        def map_area(area):
            # Values outside of the grid are not tile numbers, e.g. the 0xFFFF used by unused links
            if area >= source_width * source_width:
                return area

            row = area // source_width + row_shift
            column = area % source_width + column_shift

            if not (0 <= row < target_width and 0 <= column < target_width):
                raise self.OutOfBoundsError(f"the chosen offset would put the paths of tile {area} "
                                            f"outside of the {map_size}x{map_size} map.")

            return row * target_width + column

        moved_files = {}

        for node_file in node_files:
            if node_file['is_empty']:
                try:
                    new_area = map_area(node_file['area'])
                except self.OutOfBoundsError:
                    continue
            else:
                new_area = map_area(node_file['area'])

            if node_file['layout'] is self.LAYOUT_VANILLA and not keep_vanilla:
                content = self._convert_vanilla_to_fm92(node_file, map_area, delta)
            else:
                content = self._move_in_place(node_file, map_area, delta)

            moved_files[f"nodes{new_area}.dat"] = content

        return moved_files

    def _move_in_place(self, node_file, map_area, delta):
        layout = node_file['layout']
        data = bytearray(node_file['data'])

        if node_file['is_empty']:
            return data

        nodes_count, _, _, navis_count, links_count = node_file['counts']
        nodes, navis, links, navi_links, _ = self._get_sections(node_file)
        pos_format = layout['pos_format']
        pos_size = struct.calcsize(pos_format)
        pos_limit = 1 << (pos_size * 8 - 1)

        def move_area(offset):
            area = struct.unpack_from('<H', data, offset)[0]
            struct.pack_into('<H', data, offset, map_area(area))

        def move_position(offset, axes):
            for axis in range(axes):
                value = struct.unpack_from(pos_format, data, offset + axis * pos_size)[0] + delta[axis]
                value = max(-pos_limit, min(pos_limit - 1, value))
                struct.pack_into(pos_format, data, offset + axis * pos_size, value)

        for index in range(nodes_count):
            offset = nodes + index * layout['node_size']
            move_area(offset + layout['node_area'])
            move_position(offset + layout['node_pos'], 3)

        for index in range(navis_count):
            offset = navis + index * layout['navi_size']
            move_area(offset + layout['navi_area'])
            move_position(offset + layout['navi_pos'], 2)

        for index in range(links_count):
            move_area(links + index * layout['link_size'] + layout['link_area'])

        for index in range(links_count):
            offset = navi_links + index * layout['navi_link_size']

            if offset + layout['navi_link_size'] > len(data):
                break

            if layout['navi_link_area'] is None:
                # Vanilla navi links keep the navi node in the lower 10 bits and the tile in the upper 6
                value = struct.unpack_from('<H', data, offset)[0]
                struct.pack_into('<H', data, offset, (map_area(value >> 10) << 10) | (value & 0x3FF))
            else:
                move_area(offset + layout['navi_link_area'])

        return data

    def _convert_vanilla_to_fm92(self, node_file, map_area, delta):
        layout = self.LAYOUT_VANILLA
        counts = node_file['counts']
        nodes_count, _, _, navis_count, links_count = counts

        content = bytearray(self.FM92_PREFIX + b"VER2")
        content += struct.pack('<5I', *counts)

        if node_file['is_empty']:
            return content + self.FM92_EOF

        nodes, navis, links, navi_links, end = self._get_sections(node_file)
        # Some files do not carry every trailing section, in which case they are read as zeroes
        data = node_file['data'].ljust(end + 2 * links_count + self.TRAILER_SIZE, b"\x00")

        for index in range(nodes_count):
            offset = nodes + index * layout['node_size']
            x, y, z, cost, link_id, area, node_id = struct.unpack_from('<3hh3H', data, offset + 8)
            content += data[offset:offset + 8]
            content += struct.pack('<3hh3H', 0, 0, 0, cost, link_id, map_area(area), node_id)
            content += data[offset + 22:offset + 28]
            content += struct.pack('<3i', x + delta[0], y + delta[1], z + delta[2])

        for index in range(navis_count):
            offset = navis + index * layout['navi_size']
            x, y, area = struct.unpack_from('<2hH', data, offset)
            content += struct.pack('<2hH', 0, 0, map_area(area))
            content += data[offset + 6:offset + 14]
            content += struct.pack('<2i', x + delta[0], y + delta[1])

        for index in range(links_count):
            area, node_id = struct.unpack_from('<2H', data, links + index * 4)
            content += struct.pack('<2H', map_area(area), node_id)

        content += data[navi_links - self.FILLER_SIZE:navi_links]

        for index in range(links_count):
            value = struct.unpack_from('<H', data, navi_links + index * 2)[0]
            content += struct.pack('<2H', value & 0x3FF, map_area(value >> 10))

        # Link lengths, path intersection flags and the remaining unused data
        content += data[end:end + 2 * links_count + self.TRAILER_SIZE]
        content += self.FM92_EOF

        return content
