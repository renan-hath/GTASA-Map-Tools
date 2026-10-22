"""
Scores a generated vanilla-style radar of a mod against a map its author drew, such as the one
of GTA Province. Unlike Proper Radar, an author's map has its own colours, so both maps are
reduced to what they have in common: water, ground, road, paved ground and buildings.

Run from the folder of the tool:
    python -m application.tools.radar_reference_score <radar tiles folder> <output folder>
        [--reference <image>] [--area <left> <bottom> <right> <top>] [--search 40]

The tiles folder is what the radar generator wrote (radarNN.txd). The area is the square of the
world the reference image covers, which is refined by matching the water of both maps. The
held-out score uses half of 500-unit squares, as a checkerboard.
"""
import argparse
import math
import os

import numpy as np
from PIL import Image, ImageFilter

from application.tools.radar_calibration import get_close
from application.tools.radar_generator import RadarGenerator

PROVINCE_REFERENCE = os.path.join('References', 'Generated radars', 'Province_Map', 'GTA_Province.jpg')
PROVINCE_AREA = (3000, -3000, 9000, 3000)
TILE_WORLD_SIZE = RadarGenerator.TILE_WORLD_SIZE
HOLDOUT_CELL = 500

CLASSES = ('water', 'ground', 'road', 'paved', 'building')
WATER, GROUND, ROAD, PAVED, BUILDING = range(len(CLASSES))
IGNORED = 255

# Brightness bands of the author's map of Province: dark water, darker roads, ground, lighter
# paved blocks and the lightest buildings. Street names and the logo are white or yellow
REFERENCE_BANDS = ((46, WATER), (71, ROAD), (91, GROUND), (118, PAVED), (175, BUILDING))
REFERENCE_LABEL_BRIGHTNESS = 175

# The class of each colour of the vanilla style
GENERATED_CLASSES = {
    RadarGenerator.KIND_ROAD: ROAD,
    RadarGenerator.KIND_CONCRETE: PAVED,
    RadarGenerator.KIND_BUILDING: BUILDING,
    RadarGenerator.KIND_DARK_GRASS: GROUND,
    RadarGenerator.KIND_LIGHT_GRASS: GROUND,
    RadarGenerator.KIND_SAND: GROUND,
    RadarGenerator.KIND_DESERT: GROUND,
    RadarGenerator.KIND_DIRT: GROUND,
    RadarGenerator.KIND_RAILWAY: PAVED,
}


def read_reference(path):
    pixels = np.asarray(Image.open(path).convert('RGB'), dtype=np.int32)
    brightness = pixels.mean(axis=2)
    classes = np.full(brightness.shape, IGNORED, dtype=np.uint8)

    for upper in reversed(REFERENCE_BANDS):
        classes[brightness < upper[0]] = upper[1]

    # Labels are left out, with a pixel around them, as what is under them is not known
    labels = (brightness >= REFERENCE_LABEL_BRIGHTNESS) | (np.abs(pixels[:, :, 0] - pixels[:, :, 2]) > 40)
    labels = np.asarray(Image.fromarray(labels.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
    classes[labels] = IGNORED
    return classes


def read_generated(tiles_dir, area):
    # The tiles over the area, stitched at their own resolution, with the world square they cover
    names = [name for name in os.listdir(tiles_dir) if name.startswith('radar') and name.endswith('.txd')]
    tiles_per_row = math.isqrt(max(int(name[5:-4]) for name in names) + 1)
    half = tiles_per_row * TILE_WORLD_SIZE / 2
    left, bottom, right, top = area
    first_col, last_col = int((left + half) // TILE_WORLD_SIZE), int((right + half - 1) // TILE_WORLD_SIZE)
    first_row, last_row = int((half - top) // TILE_WORLD_SIZE), int((half - bottom - 1) // TILE_WORLD_SIZE)
    tiles = {}

    for row in range(first_row - 1, last_row + 2):
        for col in range(first_col - 1, last_col + 2):
            if 0 <= row < tiles_per_row and 0 <= col < tiles_per_row:
                with open(os.path.join(tiles_dir, f'radar{row * tiles_per_row + col:02d}.txd'), 'rb') as txd_file:
                    tiles[row, col] = next(iter(RadarGenerator._read_txd(txd_file.read()).values())).convert('RGB')

    resolution = max(tile.size[0] for tile in tiles.values())
    rows = range(first_row - 1, last_row + 2)
    cols = range(first_col - 1, last_col + 2)
    image = Image.new('RGB', (len(cols) * resolution, len(rows) * resolution))

    for (row, col), tile in tiles.items():
        image.paste(tile.resize((resolution, resolution), Image.NEAREST),
                    ((col - cols[0]) * resolution, (row - rows[0]) * resolution))

    # The world square of the image: x grows to the right and y upwards
    world = (cols[0] * TILE_WORLD_SIZE - half, half - (rows[-1] + 1) * TILE_WORLD_SIZE,
             (cols[-1] + 1) * TILE_WORLD_SIZE - half, half - rows[0] * TILE_WORLD_SIZE)
    water_color = read_water_color(tiles_dir, tiles_per_row)
    return classify_generated(image, water_color), world


def read_water_color(tiles_dir, tiles_per_row):
    # A corner tile of a big map is open sea
    with open(os.path.join(tiles_dir, 'radar00.txd'), 'rb') as txd_file:
        tile = np.asarray(next(iter(RadarGenerator._read_txd(txd_file.read()).values())).convert('RGB'))

    return tuple(int(value) for value in np.median(tile.reshape(-1, 3), axis=0))


def classify_generated(image, water_color):
    colors = [water_color]
    classes = [WATER]

    for kind, class_index in GENERATED_CLASSES.items():
        colors.append(RadarGenerator.VANILLA_PALETTE[kind])
        classes.append(class_index)

    pixels = np.asarray(image, dtype=np.int32)
    colors = np.array(colors, dtype=np.int32)
    nearest = np.empty(pixels.shape[:2], dtype=np.uint8)

    # In bands, as the distances to every colour of a big image take a lot of memory
    for start in range(0, pixels.shape[0], 512):
        band = pixels[start:start + 512]
        nearest[start:start + 512] = ((band[:, :, None, :] - colors[None, None]) ** 2).sum(axis=3).argmin(axis=2)

    return np.array(classes, dtype=np.uint8)[nearest]


def resample(classes, world, area, shape):
    # The classes over the area at the size of the reference: each pixel takes the class most
    # of the generated pixels under it have
    left, bottom, right, top = area
    height, width = classes.shape
    units_per_pixel = (world[2] - world[0]) / width
    crop = (int(round((left - world[0]) / units_per_pixel)), int(round((world[3] - top) / units_per_pixel)),
            int(round((right - world[0]) / units_per_pixel)), int(round((world[3] - bottom) / units_per_pixel)))
    votes = []

    for class_index in range(len(CLASSES)):
        layer = Image.fromarray((classes == class_index).astype(np.float32))
        votes.append(np.asarray(layer.resize((shape[1], shape[0]), Image.BOX, box=crop)))

    return np.stack(votes, axis=2).argmax(axis=2).astype(np.uint8)


def align(reference, classes, world, area, search):
    # The area is shifted and scaled until the water of both maps agrees the most. The water of
    # the generated radar is shrunk first, to about a unit per pixel, so that each try is quick
    reference_water = reference == WATER
    small = (reference.shape[0] // 4, reference.shape[1] // 4)
    reference_small = np.asarray(Image.fromarray(reference_water.astype(np.float32)).resize(small[::-1], Image.BOX)) > 0.5
    factor = max(1, int(classes.shape[0] / ((world[3] - world[1]) / 2)))
    water = Image.fromarray((classes == WATER).astype(np.float32))
    water = water.resize((classes.shape[1] // factor, classes.shape[0] // factor), Image.BOX)
    units_per_pixel = (world[2] - world[0]) / water.size[0]
    left, bottom, right, top = area
    size = right - left
    best = (-1.0, area)

    for scale in (0.98, 0.99, 1.0, 1.01, 1.02):
        for dx in range(-search, search + 1, 8):
            for dy in range(-search, search + 1, 8):
                center_x, center_y = (left + right) / 2 + dx, (bottom + top) / 2 + dy
                half = size * scale / 2
                box = ((center_x - half - world[0]) / units_per_pixel, (world[3] - center_y - half) / units_per_pixel,
                       (center_x + half - world[0]) / units_per_pixel, (world[3] - center_y + half) / units_per_pixel)
                candidate = np.asarray(water.resize(small[::-1], Image.BOX, box=box)) > 0.5
                agreement = (candidate == reference_small).mean()

                if agreement > best[0]:
                    best = (agreement, (center_x - half, center_y - half, center_x + half, center_y + half))

    return best[1]


def print_scores(reference, classes):
    known = reference != IGNORED
    same = (reference == classes) & known
    close = get_close(np.where(known, reference, 254), classes) & known
    rows, cols = np.indices(reference.shape)
    cell = reference.shape[0] * HOLDOUT_CELL // 6000
    held_out = ((rows // cell + cols // cell) % 2 == 1) & known
    print(f'Within two pixels {close.sum() / known.sum() * 100:6.2f}%, agreement {same.sum() / known.sum() * 100:6.2f}%'
          f'   (held-out squares {close[held_out].mean() * 100:.2f}% / {same[held_out].mean() * 100:.2f}%)')
    print('Of what the reference shows as each class: its share, how much is drawn as it, within two pixels, '
          'and what else it is drawn as:')

    for index, name in enumerate(CLASSES):
        mask = reference == index

        if not mask.any():
            continue

        drawn = np.bincount(classes[mask], minlength=len(CLASSES)) / mask.sum() * 100
        others = ', '.join(f'{CLASSES[other]} {drawn[other]:.1f}%' for other in np.argsort(-drawn)
                           if other != index and drawn[other] >= 1)
        print(f'  {name:9s} {mask.sum() / known.sum() * 100:5.1f}% of the map, {drawn[index]:5.1f}% right, '
              f'close {close[mask].mean() * 100:5.1f}% ({others})')

    return close.sum() / known.sum()


def save_images(reference, classes, output_dir):
    colors = np.array([(40, 60, 110), (110, 150, 80), (20, 20, 20), (165, 165, 165), (250, 250, 250)], dtype=np.uint8)
    shown = np.vstack([colors, np.zeros((256 - len(colors), 3), dtype=np.uint8)])
    shown[IGNORED] = (255, 0, 255)
    Image.fromarray(shown[reference]).save(os.path.join(output_dir, 'reference_classes.png'))
    Image.fromarray(shown[classes]).save(os.path.join(output_dir, 'generated_classes.png'))
    known = reference != IGNORED
    close = get_close(np.where(known, reference, 254), classes)
    difference = (shown[reference].astype(np.float32) * 0.35 + 255 * 0.65).astype(np.uint8)
    difference[known & (reference != classes)] = (255, 170, 0)
    difference[known & ~close] = (220, 0, 0)
    Image.fromarray(difference).save(os.path.join(output_dir, 'difference.png'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tiles_dir')
    parser.add_argument('output_dir')
    parser.add_argument('--reference', default=PROVINCE_REFERENCE)
    parser.add_argument('--area', type=float, nargs=4, default=PROVINCE_AREA)
    parser.add_argument('--search', type=int, default=40, help='units the area may be shifted by to match the water')
    parser.add_argument('--paved-as-ground', action='store_true', help='score paved ground as ground on both maps')
    arguments = parser.parse_args()
    os.makedirs(arguments.output_dir, exist_ok=True)

    reference = read_reference(arguments.reference)
    classes, world = read_generated(arguments.tiles_dir, arguments.area)
    area = arguments.area

    if arguments.search:
        area = align(reference, classes, world, area, arguments.search)
        print(f'Area matched to the water: {", ".join(f"{value:.0f}" for value in area)}')

    generated = resample(classes, world, area, reference.shape)

    if arguments.paved_as_ground:
        reference = np.where(reference == PAVED, GROUND, reference).astype(np.uint8)
        generated = np.where(generated == PAVED, GROUND, generated).astype(np.uint8)

    print_scores(reference, generated)
    save_images(reference, generated, arguments.output_dir)


if __name__ == '__main__':
    main()
