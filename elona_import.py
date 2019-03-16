from pprint import pprint
"""
Elona 1.22 map importer.
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

maps = {}
tilesets = {}


def getfile(path, ext):
    return splitext(path)[0] + "." + ext


class Elona(T.Plugin):
    @classmethod
    def nameFilter(cls):
        return "Elona 1.22 (*.map)"

    @classmethod
    def supportsFile(cls, f):
        return exists(getfile(f, "idx"))

    @classmethod
    def read(cls, f):
        print('Loading map at', f)
        el = Elona(f)

        m = T.Tiled.Map(T.Tiled.Map.Orthogonal, el.mdata.width,
                        el.mdata.height, 48, 48)
        maps[f] = m

        root = '/home/ruin/Documents'
        atlas = root + '/map%01i.tsx' % el.mdata.atlas
        # atlas = utils.find_sensitive_path(dirname(f)+'/../graphic/map', atlas)
        tileset = T.Tiled.Tileset.create("", 48, 48, 0, 0)
        if not T.loadSharedTilesetFromTsx(tileset, atlas):
            raise Exception("failed to load " + atlas)

        layer_tiles = el.populate_tiles(tileset.data())
        layer_objects = el.populate_objects(tileset.data())

        item_atlas = '/tmp/item.tsx'
        item_tileset = T.Tiled.Tileset.create("", 48, 48, 0, 0)
        if not T.loadSharedTilesetFromTsx(item_tileset, item_atlas):
            raise Exception("failed to load" + item_atlas)

        layer_items = el.populate_items(item_tileset.data())

        chara_atlas = '/tmp/character.tsx'
        chara_tileset = T.Tiled.Tileset.create("", 48, 48, 0, 0)
        if not T.loadSharedTilesetFromTsx(chara_tileset, chara_atlas):
            raise Exception("failed to load" + chara_atlas)

        layer_charas = el.populate_characters(chara_tileset.data())
        # have to pass ownership so can't add tileset before populating layer
        m.addTileset(tileset)
        m.addTileset(item_tileset)
        m.addTileset(chara_tileset)
        m.addLayer(layer_tiles)
        m.addLayer(layer_objects)
        m.addLayer(layer_items)
        m.addLayer(layer_charas)

        return m

    @classmethod
    def write(cls, m, fn):
        return False

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
        obj = getfile(f, "obj")
        idx = getfile(f, "idx")
        with gzip.open(idx, 'rb') as fh:
            mdata = MapData()
            mdata.unpack(fh)
        with gzip.open(f, 'rb') as fh:
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
                for i in range(300):
                    dat = fh.read(5 * 4)
                    dat = unpack("IIIII", dat)
                    if dat[0] != 0:
                        if dat[4] == 0:
                            items.append(
                                Item(id=dat[0], x=dat[1], y=dat[2], own_state=dat[3]))
                        elif dat[4] == 1:
                            charas.append(
                                Character(id=dat[0], x=dat[1], y=dat[2]))
                        elif dat[4] == 2:
                            objs.append(
                                Object(id=self.cell_objs[dat[0]][1], x=dat[1], y=dat[2], param1=self.cell_objs[dat[0]][0], param2=(dat[3] % 1000), param3=(floor(dat[3] / 1000))))

        self.mdata = mdata
        self.tiles = tiles
        self.items = items
        self.charas = charas
        self.objs = objs

    def populate_tiles(self, t):
        l = T.Tiled.TileLayer(
            'Tiles', 0, 0, self.mdata.width, self.mdata.height)
        for y in range(self.mdata.height):
            for x in range(self.mdata.width):
                tpos = self.tiles[y * self.mdata.width + x]
                if tpos < t.tileCount():
                    ti = t.tileAt(tpos)
                    if ti != None:
                        l.setCell(x, y, T.Tiled.Cell(ti))

        l.setProperty("atlas", self.mdata.atlas)
        l.setProperty("next_regenerate_date", self.mdata.regen)
        l.setProperty("stair_up_pos", self.mdata.stairup)

        return l

    def populate_items(self, t):
        o = T.Tiled.ObjectGroup('Items', 0, 0)
        for item in self.items:
            if item.id < t.tileCount():
                ti = t.tileAt(item.id)
                if ti != None:
                    map_object = T.Tiled.MapObject("", "", T.qt.QPointF(
                        item.x * 48, item.y * 48 + 48), T.qt.QSizeF(48, 48))
                    map_object.setProperty("id", ti.propertyAsString("id"))
                    map_object.setProperty("own_state", item.own_state)
                    map_object.setCell(T.Tiled.Cell(ti))
                    o.addObject(map_object)
        return o

    def populate_characters(self, t):
        o = T.Tiled.ObjectGroup('Characters', 0, 0)
        for chara in self.charas:
            if chara.id < t.tileCount():
                ti = t.tileAt(chara.id)
                if ti != None:
                    map_object = T.Tiled.MapObject("", "", T.qt.QPointF(
                        chara.x * 48, chara.y * 48 + 48), T.qt.QSizeF(48, 48))
                    map_object.setProperty("id", ti.propertyAsString("id"))
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
                    map_object.setProperty("id", obj.id)
                    map_object.setProperty("param1", obj.param1)
                    map_object.setProperty("param2", obj.param2)
                    map_object.setProperty("param3", obj.param3)
                    map_object.setCell(T.Tiled.Cell(ti))
                    o.addObject(map_object)
        return o


class MapData(cpystruct.CpyStruct('uint width, height, atlas, regen, stairup;')):
    pass
