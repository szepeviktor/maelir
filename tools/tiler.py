#!/usr/bin/env python3

import os
import sys
import io
import yaml

import PIL
from PIL import Image

# Allow huge images
PIL.Image.MAX_IMAGE_PIXELS = 933120000

def get_tile_positions_to_ignore(yaml_data: dict, img: Image, tile_size: int):
    out = {}
    cropped_width = img.size[0] - img.size[0] % tile_size
    cropped_height = img.size[1] - img.size[1] % tile_size

    for entry in yaml_data["all_land_tiles"]:
        out[entry['x_pixel'], entry['y_pixel']] = True

    to_remove = []
    for key, _ in out.items():
        x,y = key

        has_water = False
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                dx *= tile_size
                dy *= tile_size

                if dx == 0 and dy == 0:
                    continue
                if x + dx < 0 or x + dx >= cropped_width:
                    continue
                if y + dy < 0 or y + dy >= cropped_height:
                    continue
                if (x + dx,y + dy) not in out:
                    has_water = True
                    break
        if has_water:
            to_remove.append(key)

    for key in to_remove:
        del out[key]

    return out

def create_tiles(yaml_data : dict, img: Image, to_ignore : dict, tile_size: int):
    tiles = []
    cropped_width = img.size[0] - img.size[0] % tile_size
    cropped_height = img.size[1] - img.size[1] % tile_size

    for y in range(0, cropped_height, tile_size):
        for x in range(0, cropped_width, tile_size):

            if (x, y) in to_ignore:
                tiles.append(None)
                continue

            tile = img.crop((x, y, x+tile_size, y+tile_size))
            tile = tile.convert(
                mode='P', palette=Image.ADAPTIVE, dither=Image.Dither.NONE, colors=64)
            tiles.append(tile)

    return tiles


def create_land_mask_cpp(yaml_data: dict, row_length: int, dst_dir: str, out_base: str):
    hh_file = open(os.path.join("{}/{}.hh".format(dst_dir, out_base)), "w")
    cc_file = open(os.path.join("{}/{}.cc".format(dst_dir, out_base)), "w")

    data = yaml_data['land_mask']

    hh_file.write(f"""// This file was generated by tiler.py
#pragma once

#include <cstdint>

constexpr auto kLandMaskRowSize = {row_length};
constexpr auto kLandMaskRows = {len(data) // (row_length // 32)};

extern const uint32_t kLandMask[];
""")

    cc_file.write(f"""// This file was generated by tiler.py
#include "{out_base}.hh"

const uint32_t kLandMask[] = {{
    """)

    for i in range(0, len(data)):
        cc_file.write(f"0x{data[i]:08x}, ")
        if i % 8 == 7:
            cc_file.write("\n    ")

    cc_file.write("\n};\n")


def create_tile_cpp(yaml_data: dict, tiles: list, row_length: int, dst_dir: str, out_base: str):
    data_size = 0

    tile_size = 0
    for tile in tiles:
        if tile is not None:
            tile_size = tile.size[0]
            break

    land_only_tile = Image.new('P', (tile_size, tile_size), 0)
    r = yaml_data['land_pixel_colors'][0]['r']
    g = yaml_data['land_pixel_colors'][0]['g']
    b = yaml_data['land_pixel_colors'][0]['b']

    # Fill land_only_tile with the color of the land (r,g,b)
    for y in range(0, land_only_tile.size[1]):
        for x in range(0, land_only_tile.size[0]):
            land_only_tile.putpixel((x, y), (r, g, b))

    hh_file = open(os.path.join("{}/{}.hh".format(dst_dir, out_base)), "w")
    cc_file = open(os.path.join("{}/{}.cc".format(dst_dir, out_base)), "w")
    hh_file.write("""// This file was generated by tiler.py
#pragma once

#include <array>
#include <cstdint>
#include <span>

constexpr auto kCornerLatitude = {corner_latitude};
constexpr auto kCornerLongitude = {corner_longitude};
constexpr auto kPixelLatitudeSize = {pixel_latitude_size};
constexpr auto kPixelLongitudeSize = {pixel_longitude_size};

constexpr auto kRowSize = {row_size};
constexpr auto kColumnSize = {column_size};

""".format(tile_size=tile_size, row_size=row_length, column_size=len(tiles) // row_length,
           corner_latitude=yaml_data['corner_position']["latitude"], corner_longitude=yaml_data['corner_position']["longitude"],
           pixel_latitude_size=yaml_data['corner_position']["latitude_pixel_size"],
           pixel_longitude_size=yaml_data['corner_position']["longitude_pixel_size"]))

    cc_file.write("""// This file was generated by tiler.py
#include "{out_base}.hh"

""".format(out_base=out_base))

    output = io.BytesIO()
    land_only_tile.save(output, format='PNG')
    bytes = output.getvalue()
    data_size += len(bytes)

    cc_file.write("const std::array<const std::byte, {len}> land_only_tile = {{\n    ".format(
        len=len(bytes)))
    for b in range(0, len(bytes)):
        cur = bytes[b]
        cc_file.write("std::byte(0x{:02x}),{}".format(
            cur, "\n    " if b % 7 == 6 and b != len(bytes) - 1 else ""))

    cc_file.write("\n};\n\n")

    hh_file.write("extern const std::array<const std::byte, {len}> land_only_tile;\n".format(
        len=len(bytes)))


    for index, tile in enumerate(tiles):
        bytes = []

        if tile is None:
            continue

        output = io.BytesIO()
        tile.save(output, format='PNG')
        bytes = output.getvalue()
        data_size += len(bytes)

        cc_file.write("const std::array<const std::byte, {len}> {name} = {{\n    ".format(
            len=len(bytes), name=f"tile_{index}"))
        for b in range(0, len(bytes)):
            cur = bytes[b]
            cc_file.write("std::byte(0x{:02x}),{}".format(
                cur, "\n    " if b % 7 == 6 and b != len(bytes) - 1 else ""))

        cc_file.write("\n};\n\n")

        hh_file.write("extern const std::array<const std::byte, {len}> {name};\n".format(
            len=len(bytes), name=f"tile_{index}"))

    hh_file.write("\n\nconstexpr auto tile_array = std::array {\n")
    for index, tile in enumerate(tiles):
        if tile is None:
            hh_file.write("    std::span<const std::byte> {{land_only_tile.data(), land_only_tile.size()}},\n".format(
                index=index))
        else:
            hh_file.write("    std::span<const std::byte> {{tile_{index}.data(), tile_{index}.size()}},\n".format(
                index=index))
    hh_file.write("};\n")

    return data_size


def save_tiles(tiles: list, num_colors):
    for i, tile in enumerate(tiles):
        tile = tile.convert(mode='P', palette=Image.ADAPTIVE,
                            dither=None, colors=num_colors)
        tile.save(f'tile_{i}.png', optimize=True, format="PNG")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: {} <input_yaml_file> <output_dir> <tile_output_base> <path_finder_output_base>".format(
            sys.argv[0]))
        sys.exit(1)

    yaml_data = yaml.safe_load(open(sys.argv[1], 'r'))

    if "map_filename" not in yaml_data or "tile_size" not in yaml_data:
        print("Error: map_filename/tile_size not found in input yaml file. See mapeditor_metadata.yaml for an example")
        sys.exit(1)

    if "corner_position" not in yaml_data:
        print("Error: corner_position not found in input yaml file. See mapeditor_metadata.yaml for an example")
        sys.exit(1)

    if ["latitude", "longitude", "latitude_pixel_size", "longitude_pixel_size"] != list(yaml_data["corner_position"].keys()):
        print("Error: corner_position should have latitude, longitude, latitude_pixel_size, longitude_pixel_size keys")
        sys.exit(1)

    img = Image.open(yaml_data['map_filename'])

    num_pixels = img.size[0]*img.size[1]
    num_colors = len(img.getcolors(num_pixels))

    tile_size = yaml_data['tile_size']
    path_finder_tile_size = yaml_data['path_finder_tile_size']

    to_ignore = get_tile_positions_to_ignore(yaml_data, img, tile_size)

    tiles = create_tiles(yaml_data, img, to_ignore, tile_size=tile_size)
    # save_tiles(tiles, num_colors=256)
    tile_row_length = int(img.size[0] / tile_size)
    path_finder_row_length = int((
        tile_row_length * tile_size) / path_finder_tile_size)

    create_land_mask_cpp(yaml_data, row_length=path_finder_row_length,
                         dst_dir=sys.argv[2], out_base=sys.argv[4])
    data_size = create_tile_cpp(yaml_data,
                                tiles, row_length=tile_row_length, dst_dir=sys.argv[2], out_base=sys.argv[3])

    print("tiler: Converted to {} tiles ({} ignored), total size: {:.2f} KiB".format(
        len(tiles), len(to_ignore), data_size / 1024.0))
