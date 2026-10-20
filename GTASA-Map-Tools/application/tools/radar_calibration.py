"""
Compares the radar the vanilla style generates of the original map with a reference radar, to
tell how close the generator is to drawing it and where it is not.

Run from the folder of the tool:
    python -m application.tools.radar_calibration <output folder> [--game-dir <unmodified game>]
                                                  [--colors] [--strip-surfaces] [--reuse] [--resolution 256]

--strip-surfaces generates as if every collision had the DEFAULT surface, as many mods do, to
tell how the vanilla style paints those maps.

The game folder should be an unmodified game, as every object of its mods is drawn too. Scores:
agreement is the share of pixels that show the same as the reference, and within two pixels it
is the share that show something the reference shows no more than two pixels away. They are
also given for half of the tiles (the held-out tiles), which anything fitted to the reference
should only be fitted without. The radar of the original game is scored the same way, as the
reference is a repaint of it.

The original map only tells how the vanilla style paints maps like it: every change should also
be checked on the radar of a modded game.
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

from application.tools.radar_generator import ImgArchive, RadarGenerator

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


def read_generated(tiles_dir):
    # The generated radar from its tiles, at their own resolution, as the game shows them
    tiles = []

    for tile_index in range(TILES_PER_ROW * TILES_PER_ROW):
        with open(os.path.join(tiles_dir, f'radar{tile_index:02d}.txd'), 'rb') as txd_file:
            tiles.append(next(iter(RadarGenerator._read_txd(txd_file.read()).values())).convert('RGB'))

    tile_size = tiles[0].size[0]
    radar = Image.new('RGB', (TILES_PER_ROW * tile_size, TILES_PER_ROW * tile_size))

    for tile_index, tile in enumerate(tiles):
        tile_row, tile_col = divmod(tile_index, TILES_PER_ROW)
        radar.paste(tile, (tile_col * tile_size, tile_row * tile_size))

    return radar


def get_game_dir(game_dir=None):
    if game_dir:
        return game_dir

    with open(SETTINGS_PATH, 'r', encoding='utf-8') as settings_file:
        return json.load(settings_file)['game_dir']


def read_original_radar(game_dir):
    # The radar of the original game, which the reference was painted from
    gta3_path = os.path.join(game_dir, 'models', 'gta3.img')

    if not os.path.isfile(gta3_path):
        return None

    archive = ImgArchive(gta3_path)
    radar = Image.new('RGB', (TILES_PER_ROW * TILE_RESOLUTION, TILES_PER_ROW * TILE_RESOLUTION))

    try:
        for tile_index in range(TILES_PER_ROW * TILES_PER_ROW):
            name = f'radar{tile_index:02d}.txd'

            if name not in archive.entries:
                return None

            tile = next(iter(RadarGenerator._read_txd(archive.read(name)).values())).convert('RGB')
            tile_row, tile_col = divmod(tile_index, TILES_PER_ROW)
            radar.paste(tile.resize((TILE_RESOLUTION, TILE_RESOLUTION), Image.BICUBIC),
                        (tile_col * TILE_RESOLUTION, tile_row * TILE_RESOLUTION))
    finally:
        archive.close()

    return radar


class SurfacelessGenerator(RadarGenerator):
    """The generator, as if every collision had the DEFAULT surface, like the ones of many mods."""

    def _build_collision(self, collision_model):
        if collision_model is not None:
            collision_model = dict(collision_model, surfaces=np.zeros_like(collision_model['surfaces']),
                                   box_surfaces=np.zeros_like(collision_model['box_surfaces']))

        return super()._build_collision(collision_model)


def generate(output_dir, resolution, game_dir, strip_surfaces=False):
    print(f'Game folder: {game_dir}')
    generator_class = SurfacelessGenerator if strip_surfaces else RadarGenerator
    radar_generator = generator_class(game_dir, (), lambda elements: False, SURFACES_PATH)
    progress = lambda message: print(message) if '(' not in message or message.endswith('00)') else None
    radar_generator.run(RadarGenerator.VANILLA_MAP_SIZE, os.path.join(output_dir, 'tiles'), progress,
                        RadarGenerator.STYLE_VANILLA, resolution, include_vanilla_map=True)
    return os.path.join(output_dir, 'tiles', 'radar_preview.png')


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


def get_close(reference_classes, classes, distance=2):
    # A pixel is close when what it shows is in the reference no more than the distance away
    size = reference_classes.shape[0]
    close = reference_classes == classes
    padded = np.pad(reference_classes, distance, mode='edge')

    for row in range(2 * distance + 1):
        for col in range(2 * distance + 1):
            close |= padded[row:row + size, col:col + size] == classes

    return close


def get_holdout_tiles():
    # Half of the tiles, as a checkerboard, to check that what is tuned on the others still holds
    rows, cols = np.indices((TILES_PER_ROW, TILES_PER_ROW))
    return (rows + cols) % 2 == 1


def score(reference_classes, classes, tiles=None):
    """
    Returns the agreement and the agreement within two pixels of some classes with the ones of
    the reference, on all of the map or only on the given tiles.
    """
    same = reference_classes == classes
    close = get_close(reference_classes, classes)

    if tiles is not None:
        tile_size = reference_classes.shape[0] // TILES_PER_ROW
        mask = tiles.repeat(tile_size, axis=0).repeat(tile_size, axis=1)
        return same[mask].mean(), close[mask].mean()

    return same.mean(), close.mean()


def print_scores(name, reference_classes, classes):
    holdout = get_holdout_tiles()
    strict, close = score(reference_classes, classes)
    tuned = score(reference_classes, classes, ~holdout)
    held_out = score(reference_classes, classes, holdout)
    print(f'{name:9s} within two pixels {close * 100:6.2f}%, agreement {strict * 100:6.2f}%   '
          f'(tuning tiles {tuned[1] * 100:.2f}% / {tuned[0] * 100:.2f}%, held-out tiles '
          f'{held_out[1] * 100:.2f}% / {held_out[0] * 100:.2f}%)')


def print_classes(reference_classes, classes):
    names = list(CLASSES)
    same = reference_classes == classes
    close = get_close(reference_classes, classes)
    print('\nOf what the reference shows as each kind: how much is drawn as that kind, how much of what is drawn as it '
          'is right (F1 of both), within two pixels, and what else it is drawn as:')

    for index, name in enumerate(names):
        mask = reference_classes == index

        if not mask.any():
            continue

        drawn_as = classes == index
        recall = same[mask].mean()
        precision = same[drawn_as].mean() if drawn_as.any() else 0.0
        f1 = 2 * recall * precision / max(recall + precision, 1e-9)
        drawn = np.bincount(classes[mask], minlength=len(names)) / mask.sum() * 100
        others = ', '.join(f'{names[other]} {drawn[other]:.1f}%' for other in np.argsort(-drawn)
                           if other != index and drawn[other] >= 1)
        print(f'  {name:12s} {mask.mean() * 100:5.1f}% of the map, {recall * 100:5.1f}% right, '
              f'precision {precision * 100:5.1f}%, F1 {f1 * 100:5.1f}, close {close[mask].mean() * 100:5.1f}% ({others})')


def compare(reference, generated, output_dir, original=None):
    size = reference.size[0]
    reference_classes = classify(reference)

    # A bigger radar is classified at its own resolution and each square of pixels takes the
    # class most of them have, as averaging their colors would mix the classes at every edge
    factor = generated.size[0] // size

    if factor > 1 and generated.size[0] == size * factor:
        classes = classify(generated).reshape(size, factor, size, factor).transpose(0, 2, 1, 3).reshape(size, size, -1)
        votes = np.stack([(classes == index).sum(axis=2) for index in range(len(CLASSES))], axis=2)
        generated_classes = votes.argmax(axis=2).astype(np.uint8)
        generated = Image.fromarray(np.array(list(CLASSES.values()), dtype=np.uint8)[generated_classes])
    else:
        generated = generated.resize((size, size), Image.BOX)
        generated_classes = classify(generated)
    same = reference_classes == generated_classes
    close = get_close(reference_classes, generated_classes)

    print()
    print_scores('Generated', reference_classes, generated_classes)

    if original is not None:
        print_scores('Original', reference_classes, classify(original))

    print_classes(reference_classes, generated_classes)

    tile_size = size // TILES_PER_ROW
    tile_scores = close.reshape(TILES_PER_ROW, tile_size, TILES_PER_ROW, tile_size).mean(axis=(1, 3))
    worst = sorted(((tile_scores[row, col], row, col) for row in range(TILES_PER_ROW) for col in range(TILES_PER_ROW)))
    print('\nWorst tiles (within two pixels): ' +
          ', '.join(f'radar{row * TILES_PER_ROW + col:02d} {tile_score * 100:.0f}%' for tile_score, row, col in worst[:12]))

    # What is different is shown in red over a faded reference, and in orange if it is close
    difference = (np.asarray(reference, dtype=np.float32) * 0.35 + 255 * 0.65).astype(np.uint8)
    difference[~same] = (255, 170, 0)
    difference[~close] = (220, 0, 0)
    Image.fromarray(difference).save(os.path.join(output_dir, 'difference.png'))
    reference.save(os.path.join(output_dir, 'reference.png'))
    generated.save(os.path.join(output_dir, 'generated.png'))
    return close.mean()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output_dir')
    parser.add_argument('--game-dir', help='an unmodified game (the folder in settings.json if left out)')
    parser.add_argument('--colors', action='store_true', help='only print the colors the reference uses the most')
    parser.add_argument('--strip-surfaces', action='store_true',
                        help='generate as if every collision had the DEFAULT surface, as many mods do')
    parser.add_argument('--reuse', action='store_true', help='compare the radar that was generated last time')
    parser.add_argument('--resolution', type=int, default=TILE_RESOLUTION)
    arguments = parser.parse_args()
    os.makedirs(arguments.output_dir, exist_ok=True)
    game_dir = get_game_dir(arguments.game_dir)
    reference = read_reference()

    if arguments.colors:
        print_colors(reference)
        return

    preview_path = os.path.join(arguments.output_dir, 'tiles', 'radar_preview.png')

    if not arguments.reuse:
        preview_path = generate(arguments.output_dir, arguments.resolution, game_dir, arguments.strip_surfaces)

    compare(reference, read_generated(os.path.dirname(preview_path)), arguments.output_dir, read_original_radar(game_dir))


if __name__ == '__main__':
    main()
