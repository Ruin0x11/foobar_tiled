from pprint import pprint
"""
Elona Foobar map importer/exporter.
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


def read_properties(fh, mapping):
    props = dict()
    mapping_len = unpack("I", fh.read(4))[0]

    for i in range(mapping_len):
        idx, val = unpack("II", fh.read(4 * 2))
        key = mapping[idx]
        props[key] = val

    return props


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


def read_object_group(fh):
    kind = read_string(fh)
    print(kind)
    mapping = read_mapping(fh)
    props_mapping = read_mapping(fh)
    obj_count = unpack("I", fh.read(4))[0]
    objs = []

    Object = namedtuple("Object", "id x y props")
    for i in range(obj_count):
        id, x, y = unpack("III", fh.read(4 * 3))
        props = read_properties(fh, props_mapping)
        objs.append(Object(id=id, x=x, y=y, props=props))

    return (kind, objs)


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
    write_mapping(out, props_mapping)

    out.write(pack("I", objs.objectCount()))

    for i in range(objs.objectCount()):
        obj = objs.objectAt(i)

        print("writeobj %d" % obj.cell().tile().id())
        x = int(obj.x() / 48)
        y = int(obj.y() / 48) - 1
        if obj.height() == 96:
            y += 1
        out.write(pack("III", obj.cell().tile().id(), x, y))

        write_properties(out, obj, props_found)


def read_string(fh):
    return ''.join(iter(lambda: fh.read(1).decode('ascii'), '\x00'))


def read_mapping(fh):
    mapping = dict()
    mapping_len = unpack("I", fh.read(4))[0]
    print("mapping")
    print(mapping_len)
    for i in range(mapping_len):
        k = unpack("I", fh.read(4))[0]
        v = read_string(fh)
        print("read %d %s" % (k, v))
        mapping[k] = v
    return mapping


def write_mapping(out, mapping):
    out.write(pack("I", len(mapping)))
    for k, v in mapping.items():
        print("write %d %s" % (k, v))
        out.write(pack("I", k))
        write_string(out, v)


def write_string(out, s):
    out.write(str.encode(s))
    out.write(b"\0")


def LengthOfFile(f):
    """ Get the length of the file for a regular file (not a device file)"""
    currentPos = f.tell()
    f.seek(0, 2)          # move to end of file
    length = f.tell()     # get current position
    f.seek(currentPos, 0)  # go back to where we started
    return length


def BytesRemaining(f, f_len):
    """ Get number of bytes left to read, where f_len is the length of the file (probably from f_len=LengthOfFile(f) )"""
    currentPos = f.tell()
    return f_len-currentPos


def BytesRemainingAndSize(f):
    """ Get number of bytes left to read for a regular file (not a device file), returns a tuple of the bytes remaining and the total length of the file
        If your code is going to be doing this alot then use LengthOfFile and  BytesRemaining instead of this function
    """
    currentPos = f.tell()
    l = LengthOfFile(f)
    return l-currentPos, l


class ElonaFoobar(T.Plugin):
    @classmethod
    def nameFilter(cls):
        return "Elona Foobar (*.map)"

    @classmethod
    def supportsFile(cls, f):
        return open(f, 'rb').read(4) == b'FOOM'

    @classmethod
    def read(cls, f):
        foo = ElonaFoobar(f)

        m = T.Tiled.Map(T.Tiled.Map.Orthogonal, foo.width, foo.height, 48, 48)

        root = '/home/ruin/Documents'
        atlas = root + '/map%01i.tsx' % foo.mdata["atlas"]
        tileset = T.Tiled.Tileset.create("", 48, 48, 0, 0)
        if not T.loadSharedTilesetFromTsx(tileset, atlas):
            raise Exception("failed to load " + atlas)

        layer_tiles = foo.populate_tiles(tileset.data())
        layer_objects = foo.populate_objects(tileset.data())

        item_atlas = '/tmp/item.tsx'
        item_tileset = T.Tiled.Tileset.create("", 48, 48, 0, 0)
        if not T.loadSharedTilesetFromTsx(item_tileset, item_atlas):
            raise Exception("failed to load" + item_atlas)

        layer_items = foo.populate_map_objects(
            item_tileset.data(), foo.items, "Items")

        chara_atlas = '/tmp/character.tsx'
        chara_tileset = T.Tiled.Tileset.create("", 48, 48, 0, 0)
        if not T.loadSharedTilesetFromTsx(chara_tileset, chara_atlas):
            raise Exception("failed to load" + chara_atlas)

        layer_charas = foo.populate_map_objects(
            chara_tileset.data(), foo.charas, "Characters")

        m.addTileset(tileset)
        m.addTileset(item_tileset)
        m.addTileset(chara_tileset)
        m.addLayer(layer_tiles)
        m.addLayer(layer_objects)
        m.addLayer(layer_items)
        m.addLayer(layer_charas)

        return m

    def __init__(self, f):
        self.mdata = dict()
        with gzip.open(f, "rb") as fh:
            le = LengthOfFile(fh)
            pprint(BytesRemaining(fh, le))
            fh.read(4)
            self.version = unpack("I", fh.read(4))[0]

            mod_count = unpack("I", fh.read(4))[0]
            self.mods = list()
            for i in range(mod_count):
                mod = read_string(fh)
                print(mod)

            self.width, self.height = unpack("II", fh.read(2 * 4))
            pprint(BytesRemaining(fh, le))

            mapping = read_mapping(fh)
            pprint(mapping)
            pprint(BytesRemaining(fh, le))

            self.tiles = list(
                unpack("I" * (self.width * self.height), fh.read(self.width * self.height * 4)))
            print(len(self.tiles))
            pprint(BytesRemaining(fh, le))

            prop_len = unpack("I", fh.read(4))[0]
            self.mdata = dict()
            for i in range(prop_len):
                key = read_string(fh)
                val = unpack("I", fh.read(4))[0]
                self.mdata[key] = val

            count = unpack("I", fh.read(4))[0]
            pprint(count)

            self.charas = read_object_group(fh)[1]
            self.items = read_object_group(fh)[1]
            self.objs = read_object_group(fh)[1]
            pprint(self.charas)
            pprint(self.items)
            pprint(self.objs)

    def populate_tiles(self, t):
        l = T.Tiled.TileLayer(
            'Tiles', 0, 0, self.width, self.height)
        for y in range(self.height):
            for x in range(self.width):
                tpos = self.tiles[y * self.width + x]
                if tpos < t.tileCount():
                    ti = t.tileAt(tpos)
                    if ti != None:
                        l.setCell(x, y, T.Tiled.Cell(ti))

        for k, v in self.mdata.items():
            l.setProperty(k, v)

        return l

    def populate_map_objects(self, t, objs, name):
        o = T.Tiled.ObjectGroup(name, 0, 0)
        for obj in objs:
            if obj.id < t.tileCount():
                ti = t.tileAt(obj.id)
                if ti != None:
                    map_object = T.Tiled.MapObject("", "", T.qt.QPointF(
                        obj.x * 48, obj.y * 48 + 48), T.qt.QSizeF(48, 48))
                    # TODO
                    # map_object.setProperty("id", ti.propertyAsString("id"))
                    for k, v in obj.props.items():
                        map_object.setProperty(k, v)
                    map_object.setCell(T.Tiled.Cell(ti))
                    o.addObject(map_object)
        return o

    def populate_objects(self, t):
        o = T.Tiled.ObjectGroup('Map Objects', 0, 0)
        for obj in self.objs:
            if obj.id < t.tileCount():
                ti = t.tileAt(obj.id)
                if ti != None:
                    map_object = T.Tiled.MapObject("", "", T.qt.QPointF(
                        obj.x * 48, obj.y * 48 + 48), T.qt.QSizeF(48, 48))
                    for k, v in obj.props.items():
                        map_object.setProperty(k, v)
                    # TODO
                    # map_object.setProperty("id", obj.id)
                    map_object.setCell(T.Tiled.Cell(ti))
                    o.addObject(map_object)
        return o

    @classmethod
    def write(cls, m, fn):
        mdata = find_layer(m, "Tiles")
        cache = dict()
        if mdata == None:
            raise Exception("No layer named \"Tiles\" found.")

        mods = ["core"]

        with gzip.open(splitext(fn)[0] + ".map", "wb") as out:
            out.write(pack("4s", b"FOOM"))

            version = 1
            out.write(pack("I", version))

            out.write(pack("I", len(mods)))
            for mod in mods:
                write_string(out, mod)

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

            out.write(pack("I", 3))
            write_object_group(out, m, "Characters", "core.chara", 188)
            write_object_group(out, m, "Items", "core.item", 400)
            write_object_group(out, m, "Map Objects",
                               "core.feat", m.width() * m.height())
            print(out.tell())

        return True
