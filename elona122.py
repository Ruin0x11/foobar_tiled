"""
Elona 1.22 map importer.
"""

from pprint import pprint
import sys
import re
import tiled as T
import os
from os.path import dirname, splitext, basename, exists, realpath, join
from lib import cpystruct
from struct import pack, unpack
from collections import namedtuple
from math import floor
import gzip


def getfile(path, ext):
    return splitext(path)[0] + "." + ext


def load_tileset(m, filename):
    print("load " + filename)
    if not exists(filename):
        raise Exception("cannot find tileset file " + filename)
    tileset = T.loadTileset(filename)
    if tileset == None:
        raise Exception("failed to load " + filename)
    m.addTileset(tileset)


def load_tilesets(m, atlas, directory):
    tileset_directory = join(directory, "Elona_foobar")

    tile_atlas = join(tileset_directory, "map%01i.tsx" % atlas)
    load_tileset(m, tile_atlas)

    for filename in os.listdir(tileset_directory):
        if filename == "map0.tsx" or filename == "map1.tsx" or filename == "map2.tsx":
            continue
        if filename.endswith(".tsx"):
            print("load " + filename)
            atlas = join(tileset_directory, filename)
            load_tileset(m, atlas)


def find_tileset(m, data_type):
    for i in range(m.tilesetCount()):
        ts = m.tilesetAt(i).data()
        if ts.name() == data_type:
            return ts
    return None


def find_tile_by_legacy(tileset, legacy_id, cache):
    if legacy_id in cache:
        return tileset.tileAt(cache[legacy_id])
    for i in range(tileset.tileCount()):
        tile = tileset.tileAt(i)
        if int(tile.propertyAsString("legacy_id")) == legacy_id:
            cache[legacy_id] = tile.id()
            return tile
    return None


class Elona(T.Plugin):
    @classmethod
    def shortName(cls):
        return "idx"

    @classmethod
    def nameFilter(cls):
        return "Elona 1.22 (*.idx)"

    @classmethod
    def supportsFile(cls, f):
        return exists(getfile(f, "map"))

    @classmethod
    def read(cls, f):
        print('Loading map at', f)
        el = Elona(f)

        m = T.Tiled.Map(T.Tiled.Map.Orthogonal, el.mdata.width,
                        el.mdata.height, 48, 48)

        m.setProperty("atlas", el.mdata.atlas)
        m.setProperty("next_regenerate_date", el.mdata.regen)
        m.setProperty("stair_up_pos", el.mdata.stairup)

        base_directory = dirname(realpath(__file__))
        load_tilesets(m, el.mdata.atlas, base_directory)

        tileset = find_tileset(m, "core.map_chip")
        item_tileset = find_tileset(m, "core.item")
        chara_tileset = find_tileset(m, "core.chara")

        layer_tiles = el.populate_tiles(tileset)
        layer_objects = el.populate_objects(tileset)
        layer_items = el.populate_items(item_tileset)
        layer_charas = el.populate_characters(chara_tileset)

        # have to pass ownership so can't add tileset before populating layer
        m.addLayer(layer_tiles)
        m.addLayer(layer_objects)
        m.addLayer(layer_items)
        m.addLayer(layer_charas)

        return m

    cell_objs = {0: (21, 726),   # dummy
                 1: (21, 726),   # 扉99
                 2: (21, 726),   # 扉0
                 3: (14, 234),   # 罠
                 4: (14, 234),   # 罠
                 5: (10, 232),   # 昇り階段
                 6: (11, 231),   # 降り階段
                 7: (21, 728),   # 扉SF
                 8: (23, 727),   # 掲示板
                 9: (31, 729),   # 投票箱
                 10: (32, 234),  # メダル
                 11: (21, 730),  # 扉JP
                 12: (21, 732),  # 街掲示板
                 13: (21, 733),  # 扉JAIL
                 }

    def __init__(self, f):
        map_ = getfile(f, "map")
        obj = getfile(f, "obj")
        idx = getfile(f, "idx")
        with gzip.open(idx, 'rb') as fh:
            mdata = MapData()
            mdata.unpack(fh)
        with gzip.open(map_, 'rb') as fh:
            tiles = fh.read(mdata.width * mdata.height * 4)
            tiles = unpack('I' * mdata.width * mdata.height, tiles)
        items = []
        charas = []
        objs = []

        if exists(obj):
            Character = namedtuple('Character', 'id x y')
            Item = namedtuple('Item', 'id x y own_state')
            Object = namedtuple('Object', 'id x y param1 param2 param3')

            with gzip.open(obj, 'rb') as fh:
                for i in range(400):
                    dat = fh.read(5 * 4)
                    if len(dat) == 0:
                        print("not reading past " + str(i) + " objects")
                        break
                    dat = unpack("IIIII", dat)
                    if dat[0] != 0:
                        if dat[4] == 0:
                            items.append(
                                Item(id=dat[0], x=dat[1], y=dat[2], own_state=dat[3]))
                        elif dat[4] == 1:
                            charas.append(
                                Character(id=dat[0], x=dat[1], y=dat[2]))
                        elif dat[4] == 2:
                            if dat[0] in self.cell_objs:
                                objs.append(
                                    Object(id=self.cell_objs[dat[0]][1], x=dat[1], y=dat[2], param1=self.cell_objs[dat[0]][0], param2=(dat[3] % 1000), param3=(floor(dat[3] / 1000))))

        self.mdata = mdata
        self.tiles = tiles
        self.items = items
        self.charas = charas
        self.objs = objs

    def populate_tiles(self, t):
        cache = dict()
        l = T.Tiled.TileLayer(
            'Tiles', 0, 0, self.mdata.width, self.mdata.height)
        for y in range(self.mdata.height):
            for x in range(self.mdata.width):
                tpos = self.tiles[y * self.mdata.width + x]
                ti = find_tile_by_legacy(t, tpos, cache)
                if ti != None:
                    l.setCell(x, y, T.Tiled.Cell(ti))

        return l

    def populate_items(self, t):
        cache = dict()
        o = T.Tiled.ObjectGroup('Items', 0, 0)
        for item in self.items:
            if item.id < t.tileCount():
                ti = find_tile_by_legacy(t, item.id, cache)
                if ti != None:
                    map_object = T.Tiled.MapObject("", "", T.qt.QPointF(
                        item.x * 48, item.y * 48 + 48), T.qt.QSizeF(ti.width(), ti.height()))
                    map_object.setProperty("id", ti.propertyAsString("id"))
                    map_object.setProperty("own_state", item.own_state)
                    map_object.setCell(T.Tiled.Cell(ti))
                    o.addObject(map_object)
        return o

    def populate_characters(self, t):
        cache = dict()
        o = T.Tiled.ObjectGroup('Characters', 0, 0)
        for chara in self.charas:
            if chara.id < t.tileCount():
                ti = find_tile_by_legacy(t, chara.id, cache)
                if ti != None:
                    map_object = T.Tiled.MapObject("", "", T.qt.QPointF(
                        chara.x * 48, chara.y * 48 + 48), T.qt.QSizeF(ti.width(), ti.height()))
                    map_object.setProperty("id", ti.propertyAsString("id"))
                    map_object.setCell(T.Tiled.Cell(ti))
                    o.addObject(map_object)
        return o

    def populate_objects(self, t):
        cache = dict()
        o = T.Tiled.ObjectGroup('Map Objects', 0, 0)
        for obj in self.objs:
            if obj.id < t.tileCount():
                ti = find_tile_by_legacy(t, obj.id, cache)
                if ti != None:
                    map_object = T.Tiled.MapObject("", "", T.qt.QPointF(
                        obj.x * 48, obj.y * 48 + 48), T.qt.QSizeF(48, 48))
                    map_object.setProperty("id", obj.id)
                    map_object.setProperty("param1", obj.param1)
                    map_object.setProperty("param2", obj.param2)
                    map_object.setProperty("param3", obj.param3)
                    map_object.setCell(T.Tiled.Cell(ti))
                    o.addObject(map_object)
        return o


class MapData(cpystruct.CpyStruct('uint width, height, atlas, regen, stairup;')):
    pass
