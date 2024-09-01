#!/usr/bin/env python3

import os
import sys
import io
import yaml

from PIL import Image


def create_tiles(img: Image, tile_size: int):
    tiles = []
    cropped_width = img.size[0] - img.size[0] % tile_size
    cropped_height = img.size[1] - img.size[1] % tile_size

    for y in range(0, cropped_height, tile_size):
        for x in range(0, cropped_width, tile_size):
            tile = img.crop((x, y, x+tile_size, y+tile_size))
            tile = tile.convert(
                mode='P', palette=Image.ADAPTIVE, dither=Image.Dither.NONE, colors=64)
            tiles.append(tile)

    return tiles


def create_source_files(yaml_data: dict, tiles: list, row_length: int, dst_dir: str, out_base: str):
    data_size = 0

    hh_file = open(os.path.join("{}/{}.hh".format(dst_dir, out_base)), "w")
    cc_file = open(os.path.join("{}/{}.cc".format(dst_dir, out_base)), "w")
    hh_file.write("""// This file was generated by tiler.py
#pragma once

#include <array>
#include <cstdint>
#include <span>

// TODO: Hardcoded hacks
// 59.532405, 16.959949 -> 770, 1261 (y,x)
// 59.363773, 17.725971 (at home), 59.284293, 17.880276 -> 1283, 1397 (y,x)
constexpr auto kCornerLatitude = {corner_latitude};
constexpr auto kCornerLongitude = {corner_longitude};
constexpr auto kPixelLatitudeSize = {pixel_latitude_size};
constexpr auto kPixelLongitudeSize = {pixel_longitude_size};

constexpr auto kTileSize = {tile_size};
constexpr auto kRowSize = {row_size};
constexpr auto kColumnSize = {column_size};

""".format(tile_size=tiles[0].size[0], row_size=row_length, column_size=len(tiles) // row_length,
           corner_latitude=yaml_data['corner_position']["latitude"], corner_longitude=yaml_data['corner_position']["longitude"],
           pixel_latitude_size=yaml_data['corner_position']["latitude_pixel_size"],
           pixel_longitude_size=yaml_data['corner_position']["longitude_pixel_size"]))

    cc_file.write("""// This file was generated by tiler.py
#include "{out_base}.hh"

""".format(out_base=out_base))
    for index, tile in enumerate(tiles):
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
    for index in range(0, len(tiles)):
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
    if len(sys.argv) != 4:
        print("Usage: {} <input_yaml_file> <output_dir> <output_base>".format(
            sys.argv[0]))
        sys.exit(1)

    yaml_data = yaml.safe_load(open(sys.argv[1], 'r'))

    if "map_filename" not in yaml_data:
        print("Error: map_filename not found in input yaml file. See mapeditor_metadata.yaml for an example")
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

    tile_size = 240
    tiles = create_tiles(img, tile_size=tile_size)
    # save_tiles(tiles, num_colors=256)
    data_size = create_source_files(yaml_data,
                                    tiles, row_length=int(img.size[0] / tile_size), dst_dir=sys.argv[2], out_base=sys.argv[3])

    print("tiler: Converted to {} tiles, total size: {:.2f} KiB".format(
        len(tiles), data_size / 1024.0))
