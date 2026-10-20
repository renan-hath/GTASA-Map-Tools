"""
Compares the radar the vanilla style generates of the original map with a reference radar, to
tell how close the generator is to drawing it and where it is not.

Run from the folder of the tool:
    python -m application.tools.radar_calibration <output folder> [--colors] [--reuse] [--resolution 256]
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

from application.tools.radar_generator import RadarGenerator

REFERENCE_DIR = os.path.join('References', 'Proper Radar')
SURFACES_PATH = os.path.join('resources', 'vanilla_surfaces.txt')
SETTINGS_PATH = 'settings.json'
TILES_PER_ROW = RadarGenerator.VANILLA_TILES_PER_ROW
TILE_RESOLUTION = RadarGenerator.VANILLA_TILE_RESOLUTION

# What the radar shows, with the color the reference gives to each one
CLASSES = {
    'water': (115, 138, 173),
    'road': (0, 0, 0),
    'concrete': (161, 160, 161),
    'building': (255, 255, 255),
    'dark grass': (57, 106, 41),
    'light grass': (123, 139, 57),
    'sand': (231, 195, 99),
    'desert': (156, 136, 115),
    'dirt': (115, 102, 82),
    'railway': (74, 12, 0),
}


def read_reference():
    reference = Image.new('RGB', (TILES_PER_ROW * TILE_RESOLUTION, TILES_PER_ROW * TILE_RESOLUTION))

    for tile_index in range(TILES_PER_ROW * TILES_PER_ROW):
        with open(os.path.join(REFERENCE_DIR, f'radar{tile_index:02d}.txd'), 'rb') as txd_file:
            textures = RadarGenerator._read_txd(txd_file.read())

        tile = next(iter(textures.values())).convert('RGB').resize((TILE_RESOLUTION, TILE_RESOLUTION), Image.BICUBIC)
        tile_row, tile_col = divmod(tile_index, TILES_PER_ROW)
        reference.paste(tile, (tile_col * TILE_RESOLUTION, tile_row * TILE_RESOLUTION))

    return reference


def generate(output_dir, resolution):
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as settings_file:
        game_dir = json.load(settings_file)['game_dir']

    print(f'Game folder: {game_dir}')
    radar_generator = RadarGenerator(game_dir, (), lambda elements: False, SURFACES_PATH)
    progress = lambda message: print(message) if '(' not in message or message.endswith('00)') else None
    radar_generator.run(RadarGenerator.VANILLA_MAP_SIZE, os.path.join(output_dir, 'tiles'), progress,
                        RadarGenerator.STYLE_VANILLA, resolution, include_vanilla_map=True)
    return os.path.join(output_dir, 'tiles', 'radar_preview.png')


class SurfaceReader(RadarGenerator):
    """
    Draws what the vanilla style knows of each pixel before it decides its color: the surface
    and the kind of ground of the collision, its height, and the color and the height of the model.
    """

    SUPERSAMPLING = 1

    def _build_collision(self, collision_model):
        collision = super()._build_collision(collision_model)

        if collision is not None:
            box_surfaces = collision_model['box_surfaces']
            collision['surfaces'] = np.concatenate((collision_model['surfaces'], box_surfaces, box_surfaces)).astype(np.uint8)

        return collision

    def _build_scene(self, models, collisions):
        scene = RadarGenerator._build_scene(models, collisions)
        scene['collision_surfaces'] = (np.concatenate([collision['surfaces'] for collision in collisions])
                                       if collisions else np.zeros(0, dtype=np.uint8))
        return scene

    def _render_block(self, block, scene, style):
        from application.tools.procobj_converter import ProcObjConverter

        block_row, block_col, block_instances, radar_map_size = block
        half = radar_map_size / 2
        resolution = self.block_tiles * self.tile_resolution
        units_per_pixel = self.TILE_WORLD_SIZE / self.tile_resolution
        left = -half + block_col * self.block_tiles * self.TILE_WORLD_SIZE
        top = half - block_row * self.block_tiles * self.TILE_WORLD_SIZE
        placements = []
        triangles, kinds, surfaces = [], [], []

        for model_index, collision_index, rotation, position in block_instances:
            matrix = np.array(ProcObjConverter.get_instance_matrix(rotation), dtype=np.float32)
            position = np.array(position, dtype=np.float32)
            placements.append((model_index, collision_index, matrix, position))
            start, end = scene['collision_ranges'][collision_index]
            triangles.append(scene['collision_triangles'][start:end] @ matrix + position)
            kinds.append(scene['collision_kinds'][start:end])
            surfaces.append(scene['collision_surfaces'][start:end])

        triangles = np.concatenate(triangles)
        screen = ((triangles[:, :, 0] - left) / units_per_pixel, (top - triangles[:, :, 1]) / units_per_pixel, triangles[:, :, 2])
        result = {}

        for name, labels in (('kinds', kinds), ('surfaces', surfaces)):
            depth = np.full(resolution * resolution, -np.inf, dtype=np.float32)
            buffer = np.full(resolution * resolution, 255 if name == 'surfaces' else 0, dtype=np.uint8)
            self._rasterize(*screen, resolution, depth, labels=np.concatenate(labels), label_buffer=buffer)
            result[name] = buffer.reshape(resolution, resolution)
            result['heights'] = depth.reshape(resolution, resolution)

        depth = np.full(resolution * resolution, -np.inf, dtype=np.float32)
        color = np.zeros((resolution * resolution, 3), dtype=np.uint8)
        self._draw_models(placements, scene, (left, top, units_per_pixel, resolution), depth, color, None)
        result['colors'] = color.reshape(resolution, resolution, 3)
        result['model_heights'] = depth.reshape(resolution, resolution)
        return block_row, block_col, result


def read_surfaces(output_dir):
    """
    Saves what the vanilla style knows of each pixel of the original map, to look for what
    tells apart the kinds of ground the reference shows.
    """
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as settings_file:
        game_dir = json.load(settings_file)['game_dir']

    reader = SurfaceReader(game_dir, (), lambda elements: False, SURFACES_PATH)
    reader.include_vanilla_map = True
    reader.excluded_mods = set()
    reader.tile_resolution = TILE_RESOLUTION
    reader.block_tiles = RadarGenerator.MAX_BLOCK_TILES
    reader.texture_sample_size = RadarGenerator.TEXTURE_SAMPLE_SIZE
    reader.light_intensity = 1.0

    mod_files = reader._list_mod_files()
    reader._index_assets(mod_files)
    reader._read_ide_files(mod_files)
    instances = reader._read_instances(mod_files)
    collisions = reader._read_collisions({entry['ide_object'][0].lower() for entry in instances}, mod_files)
    reader._textures = [np.full((reader.texture_sample_size, reader.texture_sample_size, 4), (128, 128, 128, 255), dtype=np.uint8)]
    blocks, scene = reader._assign_instances_to_blocks(instances, collisions, RadarGenerator.VANILLA_MAP_SIZE,
                                                       TILES_PER_ROW, lambda message: None)
    scene['atlas'] = np.stack(reader._textures)
    scene['water_quads'] = reader._read_water_quads(mod_files)

    size = TILES_PER_ROW * TILE_RESOLUTION
    block_size = reader.block_tiles * TILE_RESOLUTION
    layers = {'kinds': np.zeros((size, size), np.uint8), 'surfaces': np.full((size, size), 255, np.uint8),
              'heights': np.full((size, size), -np.inf, np.float32), 'colors': np.zeros((size, size, 3), np.uint8),
              'model_heights': np.full((size, size), -np.inf, np.float32)}

    for block in blocks:
        block_row, block_col, result = reader._render_block(block, scene, RadarGenerator.STYLE_VANILLA)
        print(f'Block {block_row}, {block_col} read')

        for name, layer in layers.items():
            layer[block_row * block_size:(block_row + 1) * block_size,
                  block_col * block_size:(block_col + 1) * block_size] = result[name]

    water = np.full(size * size, -np.inf, dtype=np.float32)
    water_quads = scene['water_quads']
    units_per_pixel = RadarGenerator.TILE_WORLD_SIZE / TILE_RESOLUTION
    half = RadarGenerator.VANILLA_MAP_SIZE / 2
    reader._rasterize((water_quads[:, :, 0] + half) / units_per_pixel, (half - water_quads[:, :, 1]) / units_per_pixel,
                      water_quads[:, :, 2], size, water)
    layers['water'] = water.reshape(size, size)
    layers['reference'] = classify(read_reference())
    np.savez_compressed(os.path.join(output_dir, 'surfaces.npz'), **layers)

    for archive in reader._archives:
        archive.close()


def classify(image):
    pixels = np.asarray(image, dtype=np.int32)
    colors = np.array(list(CLASSES.values()), dtype=np.int32)
    distances = ((pixels[:, :, None, :] - colors[None, None, :, :]) ** 2).sum(axis=3)
    return distances.argmin(axis=2).astype(np.uint8)


def print_colors(image, count=24):
    pixels = np.asarray(image).reshape(-1, 3)
    # Colors that are almost the same are counted together, as the tiles are compressed
    keys = (pixels // 8).astype(np.int32)
    keys = keys[:, 0] * 1024 + keys[:, 1] * 32 + keys[:, 2]
    values, counts = np.unique(keys, return_counts=True)

    for index in np.argsort(-counts)[:count]:
        same = pixels[keys == values[index]]
        print(f'{counts[index] / len(pixels) * 100:6.2f}%  {tuple(int(v) for v in np.median(same, axis=0))}')


def compare(reference, generated, output_dir):
    names = list(CLASSES)
    size = reference.size[0]
    generated = generated.resize((size, size), Image.BOX)
    reference_classes = classify(reference)
    generated_classes = classify(generated)
    same = reference_classes == generated_classes

    # A pixel is close when what it shows is in the reference no more than two pixels away
    close = same.copy()
    padded = np.pad(reference_classes, 2, mode='edge')

    for row in range(5):
        for col in range(5):
            close |= padded[row:row + size, col:col + size] == generated_classes

    print(f'\nAgreement: {same.mean() * 100:.2f}% (within two pixels: {close.mean() * 100:.2f}%)')
    print('\nOf what the reference shows as each kind, how much is drawn as that kind, and as what else:')

    for index, name in enumerate(names):
        mask = reference_classes == index

        if not mask.any():
            continue

        drawn = np.bincount(generated_classes[mask], minlength=len(names)) / mask.sum() * 100
        others = ', '.join(f'{names[other]} {drawn[other]:.1f}%' for other in np.argsort(-drawn)
                           if other != index and drawn[other] >= 1)
        print(f'  {name:12s} {mask.mean() * 100:5.1f}% of the map, {drawn[index]:5.1f}% right ({others})')

    tile_size = size // TILES_PER_ROW
    tile_scores = same.reshape(TILES_PER_ROW, tile_size, TILES_PER_ROW, tile_size).mean(axis=(1, 3))
    worst = sorted(((tile_scores[row, col], row, col) for row in range(TILES_PER_ROW) for col in range(TILES_PER_ROW)))
    print('\nWorst tiles: ' + ', '.join(f'radar{row * TILES_PER_ROW + col:02d} {score * 100:.0f}%' for score, row, col in worst[:12]))

    # What is different is shown in red over a faded reference
    difference = (np.asarray(reference, dtype=np.float32) * 0.35 + 255 * 0.65).astype(np.uint8)
    difference[~same] = (220, 0, 0)
    Image.fromarray(difference).save(os.path.join(output_dir, 'difference.png'))
    reference.save(os.path.join(output_dir, 'reference.png'))
    generated.save(os.path.join(output_dir, 'generated.png'))
    return same.mean()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output_dir')
    parser.add_argument('--colors', action='store_true', help='only print the colors the reference uses the most')
    parser.add_argument('--surfaces', action='store_true', help='only save what is known of each pixel, as surfaces.npz')
    parser.add_argument('--reuse', action='store_true', help='compare the radar that was generated last time')
    parser.add_argument('--resolution', type=int, default=TILE_RESOLUTION)
    arguments = parser.parse_args()
    os.makedirs(arguments.output_dir, exist_ok=True)
    reference = read_reference()

    if arguments.colors:
        print_colors(reference)
        return

    if arguments.surfaces:
        read_surfaces(arguments.output_dir)
        return

    preview_path = os.path.join(arguments.output_dir, 'tiles', 'radar_preview.png')

    if not arguments.reuse:
        preview_path = generate(arguments.output_dir, arguments.resolution)

    compare(reference, Image.open(preview_path).convert('RGB'), arguments.output_dir)


if __name__ == '__main__':
    main()
