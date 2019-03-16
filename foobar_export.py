"""
Elona Foobar map exporter.
"""

import sys
import re
import tiled as T
from os.path import dirname, splitext, basename, exists
from lib import cpystruct, lua_table_writer
from struct import pack, unpack
from collections import namedtuple
from math import floor
from base64 import b64encode
import zlib


def find_layer(m, name):
    for i in range(m.layerCount()):
        if T.isTileLayerAt(m, i):
            l = T.tileLayerAt(m, i)
            if l.name() == name:
                return l
    return None


def find_object_group(m, name):
    for i in range(m.objectGroupCount() + 1):
        if T.isObjectGroupAt(m, i):
            o = T.objectGroupAt(m, i)
            if o.name() == name:
                return o
    return None


def find_tile(m, id):
    for i in range(m.tilesetCount()):
        if m.isTilesetUsed(i):
            ti = m.tilesetAt(i)
            for j in range(ti.tileCount()):
                tile = ti.tileAt(j)
                if tile.id() == id:
                    return tile.propertyAsString("id")
    return None


def collect_mapping(mdata):
    i = 0
    found = dict()
    mapping = dict()
    for y in range(mdata.height()):
        for x in range(mdata.width()):
            tile = mdata.cellAt(x, y).tile()
            if not tile.id() in found:
                found[tile.id()] = i
                mapping[i] = tile.propertyAsString("id")
                i += 1
    return (mapping, found)


def encode_tiles(mdata, found):
    tiles = bytearray()
    for y in range(mdata.height()):
        for x in range(mdata.width()):
            tile = mdata.cellAt(x, y).tile()
            id = found[tile.id()]
            tiles.extend(pack("I", id))
    tiles = zlib.compress(tiles)
    tiles = b64encode(tiles)
    return str(tiles)


def write_object_group(out, m, name, kind):
    objs = find_object_group(m, name)
    if objs == None:
        raise Exception("No object group named \"" + name + "\" found.")
    out.write_table_start("[\"" + kind + "\"]")
    for i in range(objs.objectCount()):
        obj = objs.objectAt(i)
        out.write_bare_table_start()

        out.write_key_and_value("id", obj.propertyAsString("id"))
        out.write_key_and_unquoted_value("x", str(int(obj.x() / 48)))
        out.write_key_and_unquoted_value("y", str(int(obj.y() / 48)))

        found = False
        for key in obj.properties().keys():
            if key != "id":
                found = True
                break

        if found:
            out.write_table_start("props")
            for key in obj.properties().keys():
                # TODO handle string properties
                if key == "id":
                    continue
                out.write_key_and_unquoted_value(
                    key, obj.propertyAsString(key))
            out.write_table_end()

        out.write_bare_table_end()
    out.write_table_end()


class ElonaFoobar(T.Plugin):
    def __init__(self):
        pass

    @classmethod
    def nameFilter(cls):
        return "Elona Foobar (*.lua)"

    @classmethod
    def supportsFile(cls, f):
        return False

    @classmethod
    def read(cls, f):
        raise NotImplementedError()

    @classmethod
    def write(cls, m, fn):
        out = ElonaFoobar()
        mdata = find_layer(m, "Tiles")
        cache = dict()
        if mdata == None:
            raise Exception("No layer named \"Tiles\" found.")

        with lua_table_writer.LuaTableWriter(fn) as out:
            out.write_key_and_unquoted_value("width", str(m.width()))
            out.write_key_and_unquoted_value("height", str(m.height()))

            mapping, found = collect_mapping(mdata)
            out.write_table_start("mapping")
            for k, v in mapping.items():
                out.write_key_and_value("[" + str(k) + "]", str(v))
            out.write_table_end()

            tiles = encode_tiles(mdata, found)
            out.write_key_and_value("tiles", tiles)

            out.write_table_start("props")
            for key in mdata.properties().keys():
                # TODO handle string properties
                out.write_key_and_unquoted_value(
                    key, mdata.propertyAsString(key))
            out.write_table_end()

            out.write_table_start("objects")
            write_object_group(out, m, "Characters", "core.chara")
            write_object_group(out, m, "Items", "core.item")
            write_object_group(out, m, "Map Objects", "core.feat")
            out.write_table_end()

        return True
