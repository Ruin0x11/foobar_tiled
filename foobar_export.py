"""
Elona Foobar map exporter.
"""

import sys
import re
import tiled as T
from os.path import dirname, splitext, basename, exists
from lib import cpystruct
from struct import pack, unpack
from collections import namedtuple
from math import floor
import gzip


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
    mapping = dict()
    for y in range(mdata.height()):
        for x in range(mdata.width()):
            tile = mdata.cellAt(x, y).tile()
            if not tile.id() in mapping:
                mapping[tile.id()] = tile.propertyAsString("id")
    return mapping


def collect_object_mapping(objs):
    found = dict()
    mapping = dict()
    for i in range(objs.objectCount()):
        o = objs.objectAt(i)
        tile = o.cell().tile()
        id = tile.id()
        if not id in mapping:
            mapping[id] = tile.propertyAsString("id")
    return mapping


def collect_properties_mapping(objs):
    i = 0
    found = dict()
    mapping = dict()
    for i in range(objs.objectCount()):
        o = objs.objectAt(i)
        for key in o.properties().keys():
            if not key in found:
                found[key] = i
                mapping[i] = key
                i += 1
    return (mapping, found)


def encode_tiles(mdata):
    tiles = bytearray()
    for y in range(mdata.height()):
        for x in range(mdata.width()):
            tile = mdata.cellAt(x, y).tile()
            id = tile.id()
            tiles.extend(pack("I", id))
    return tiles


def write_properties(out, obj, found):
    prop_len = 0
    for key in obj.properties().keys():
        if key != "id":
            prop_len += 1

    out.write(pack("I", prop_len))
    for key in obj.properties().keys():
        # TODO handle string properties
        if key == "id":
            continue
        out.write(pack("I", found[key]))
        out.write(pack("I", int(obj.propertyAsString(key))))


def write_object_group(out, m, name, kind, maximum):
    objs = find_object_group(m, name)
    if objs == None:
        raise Exception("No object group named \"" + name + "\" found.")
    mapping = collect_object_mapping(objs)
    props_mapping, props_found = collect_properties_mapping(objs)
    if objs.objectCount() > maximum:
        raise Exception("You can only place " + str(maximum) +
                        " items in layer " + name + ".")

    write_string(out, kind)

    write_mapping(out, mapping)
    write_props_mapping(out, props_mapping)

    out.write(pack("I", objs.objectCount()))

    for i in range(objs.objectCount()):
        obj = objs.objectAt(i)

        x = int(obj.x() / 48)
        y = int(obj.y() / 48)
        if obj.height() == 96:
            y += 1
        out.write(pack("III", obj.cell().tile().id(), x, y))

        write_properties(out, obj, props_found)


def write_mapping(out, mapping):
    out.write(pack("I", len(mapping)))
    for k, v in mapping.items():
        out.write(pack("I", k))
        write_string(out, v)


def write_props_mapping(out, mapping):
    out.write(pack("I", len(mapping)))
    for k, v in mapping.items():
        write_string(out, v)
        out.write(pack("I", k))


def write_string(out, s):
    out.write(str.encode(s))
    out.write(b"\0")


class ElonaFoobar(T.Plugin):
    def __init__(self):
        pass

    @classmethod
    def nameFilter(cls):
        return "Elona Foobar (*.map)"

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

        with gzip.open(splitext(fn)[0] + ".map", "wb") as out:
            mapping = collect_mapping(mdata)

            out.write(pack("II", m.width(), m.height()))
            write_mapping(out, mapping)
            tiles = encode_tiles(mdata)
            out.write(tiles)

            prop_len = 0
            for key in mdata.properties().keys():
                prop_len += 1
            out.write(pack("I", prop_len))

            for key in mdata.properties().keys():
                # TODO handle string properties
                write_string(out, key)
                out.write(pack("I", int(mdata.propertyAsString(key))))

            write_object_group(out, m, "Characters", "core.chara", 188)
            write_object_group(out, m, "Items", "core.item", 400)
            write_object_group(out, m, "Map Objects",
                               "core.feat", m.width() * m.height())

        return True
