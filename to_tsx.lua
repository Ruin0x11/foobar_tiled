package.path = package.path .. ";/home/ruin/build/elonafoobar/runtime/data/script/?.lua"
package.path = package.path .. ";/home/ruin/build/elonafoobar/runtime/profile/_/mod/core/?.lua"

local colors = {
   None = {0, 0, 0},
   White = {0, 0, 0},
   Green = {80, 0, 80},
   Red = {0, 100, 100},
   Blue = {80, 80, 0},
   Orange = {0, 40, 80},
   Yellow = {0, 0, 80},
   Grey = {100, 101, 102},
   Purple = {70, 100, 40},
   Cyan = {100, 50, 50},
   LightRed = {0, 60, 70},
   Gold = {20, 40, 100},
   White2 = {0, 0, 0},
   LightBrown = {30, 40, 70},
   DarkGreen = {150, 20, 150},
   LightGrey = {50, 50, 50},
   PaleRed = {0, 30, 30},
   LightBlue = {30, 30, 0},
   LightPurple = {30, 60, 0},
   LightGreen = {40, 0, 40},
   YellowGreen = {45, 5, 95},
}

local function load_data()
   Elona = {
      require = function() return {} end
   }

   _MOD_NAME = "core"
   data = require "kernel/data"
   require "data"
   return data
end

local data = load_data()

local Xmlwriter = require "xml"
local writer = Xmlwriter:new()
local outdir = "/tmp/cache"

local function gen_image(kind, key, file, source, tall, color)
   local folder = string.match(key, "([0-9a-zA-Z_.]+)%.")
   os.execute("mkdir -p " .. outdir .. "/" .. kind .. "/" .. folder)
   local filename = string.gsub(key, "([0-9a-zA-Z_.]+)%.([0-9a-zA-Z_.]+)", "%1/%2") .. ".png"
   local fullpath = outdir .. "/" .. kind .. "/" .. filename
   local _, _, code = os.execute("test -f " .. fullpath)
   if code == 0 then
      return fullpath
   end

   local width = 48
   local height = 48
   if tall then
      height = 96
   end
   local pos = width .. "x" .. height .. "+" .. source.x .. "+" .. source.y
   local color = colors[color]
   if not color then
      color = {0, 0, 0}
   end
   local color_s = (255 - color[1]) / 255 .. " 0 0  0 " .. (255 - color[2]) / 255 .. " 0  0 0 " .. (255 - color[3]) / 255
   local cmd = "convert -crop " .. pos .. " -transparent black -color-matrix \"" .. color_s .. "\" " .. file .. " " .. fullpath
   print(cmd)
   os.execute(cmd)

   return fullpath
end

function resolve_path(mod_path)
   local root = "/home/ruin/build/elonafoobar/"
   local mod, rest = string.match(mod_path, "%__(%w+)__(.*)")

   local part = "runtime/profile/_/mod/" .. mod
   if mod == "BUILTIN" then
      part = "deps/elona"
   end
   return root .. part .. rest
end

local function write_tileset(data_kind, outfile, cb_get_image, atlas_file)
   writer:_set_xml_writer(outfile)
   writer:_xml_declaration()
   writer:_xml_start_tag_unencoded("tileset", {version = "1.2"}, {tiledversion="1.2.3"}, {name=data_kind}, {tilewidth=48},{tileheight=48},{tilecount=0},{columns=0})

   writer:_xml_empty_tag("grid", {{orientation = "orthogonal"}, {width = 1}, {height = 1}})

   local i = 0
   for k, v in pairs(data.raw[data_kind]) do
      writer:_xml_start_tag_unencoded("tile", {{id = v.id}})

      writer:_xml_start_tag("properties")
      writer:_xml_empty_tag("property", {{name="id"},{value=k}})
      writer:_xml_end_tag("properties")

      local image = cb_get_image(v)

      if image then
         if type(image.source) == "table" then
            image = gen_image(data_kind, k, atlas_file, image.source, image.tall, v.color)
         else
            image = resolve_path(image.source)
         end
         writer:_xml_empty_tag("image", {{width=48},{height=48},{trans="000000"},{source=image}})
      end

      writer:_xml_end_tag("tile")
      i = i + 1
   end

   writer:_xml_end_tag("tileset")
end

local function get_image_chara(v)
   local image = ""
   if v.image then
      image = v.image
   elseif v.female_image then
      image = v.female_image
   elseif v.male_image then
      image = v.male_image
   else
      local race = data.raw["core.race"][v.race]
      image = race.female_image
   end
   image = data.by_legacy["core.chara_chip"][image]
   image = data.raw["core.chara_chip"][image]
   return image
end

local function get_image_item(v)
   local image = ""
   image = data.by_legacy["core.item_chip"][v.image]
   image = data.raw["core.item_chip"][image]
   return image
end

write_tileset("core.chara", "/tmp/character.tsx", get_image_chara, resolve_path("__BUILTIN__/graphic/character.bmp"))
write_tileset("core.item", "/tmp/item.tsx", get_image_item, resolve_path("__BUILTIN__/graphic/item.bmp"))
