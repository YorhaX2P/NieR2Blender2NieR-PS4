import os
import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from struct import pack
import subprocess
import asyncio
import json
from ...utils import ioUtils as io
from ..tegrax1swizzle import getFormatByIndex, getFormatTable, loadImageData


class WTAData:
    def __init__(self, f, wtpFile) -> None:
        # Header
        self.magic = f.read(4)
        self.version = io.read_uint32(f)
        self.num_files = io.read_uint32(f)
        self.offsetTextureOffsets = io.read_uint32(f)
        self.offsetTextureSizes = io.read_uint32(f)
        self.offsetTextureFlags = io.read_uint32(f)
        self.offsetTextureIdx = io.read_uint32(f)
        self.offsetTextureInfo = io.read_uint32(f)

        # Texture Offsets
        f.seek(self.offsetTextureOffsets)
        self.offsets = []
        for i in range(self.num_files):
            self.offsets.append(io.read_uint32(f))
        
        # Texture Sizes
        f.seek(self.offsetTextureSizes)
        self.sizes = []
        for i in range(self.num_files):
            self.sizes.append(io.read_uint32(f))

        # Texture Flags
        f.seek(self.offsetTextureFlags)
        self.flags = []
        for i in range(self.num_files):
            self.flags.append(io.read_uint32(f))

        # Texture Idx
        f.seek(self.offsetTextureIdx)
        self.idx = []
        for i in range(self.num_files):
            self.idx.append(io.read_uint32(f))

        # Texture Info
        f.seek(self.offsetTextureInfo)
        self.infos = []

        infoFormat = f.read(4)
        if infoFormat == b'XT1\x00':
            # Astral Chain, Bayonetta 3 WTA format 
            self.type = "XT1"
            f.seek(f.tell() - 4)
            for i in range(self.num_files):
                info = {
                    "magic": f.read(4),
                    "unk1": io.read_uint32(f),
                    "imageSize": io.read_uint64(f),
                    "headerSize": io.read_uint32(f),
                    "mipCount": io.read_uint32(f),
                    "type": io.read_uint32(f),
                    "format": io.read_uint32(f),
                    "width": io.read_uint32(f),
                    "height": io.read_uint32(f),
                    "depth": io.read_uint32(f),
                    "specialPad": io.read_uint32(f),
                    "blockHeightLog2": io.read_uint8(f),
                    "flags": io.read_uint8(f), # 0x4: use specialPad
                    "unk2": io.read_uint8(f),
                    "unk3": io.read_uint8(f),
                    "unk4": io.read_uint32(f),
                    "arrayCount": 1
                }
                if info["type"] == 3 or info["type"] == 8: # T_Cube or T_Cube_Array
                    info["arrayCount"] = 6
                self.infos.append(info)
        
        elif infoFormat == b'.tex':
            # NieR Switch WTA format
            self.type = "TEX"
            for i in range(self.num_files):
                f.seek(self.offsetTextureInfo + i * 0x100)
                info = {
                    "magic": f.read(4),
                    "format": io.read_uint32(f),
                    "unk1": io.read_uint32(f),
                    "width": io.read_uint32(f),
                    "height": io.read_uint32(f),
                    "depth": io.read_uint32(f),
                    "mipCount": io.read_uint32(f),
                    "headerSize": io.read_uint32(f),
                    "textureSize": io.read_uint64(f), # identical to the one in the headers
                    "type": 1,
                    "blockHeightLog2": 4,
                    "arrayCount": 1
                }

                if info["width"] < 256:
                    info["blockHeightLog2"] = 8 & 7
                if info["width"] < 128:
                    info["blockHeightLog2"] = 16 & 7

                self.infos.append(info)
        else:
            self.type = "PC"

        self.data = wtpFile.read()

        self.wtaPath = f.name

    def extract_textures(self, extractionDir):
        count = 0
        fileName = os.path.basename(self.wtaPath)
        dir = os.path.dirname(self.wtaPath)

        if self.type == "PC":
            for i in range(self.num_files):
                os.makedirs(extractionDir, exist_ok=True)
                with open(os.path.join(extractionDir, f"{self.idx[i]:0>8X}.dds"), "wb") as f:
                    f.write(self.data[self.offsets[i]:self.offsets[i]+self.sizes[i]])
                count += 1
        else:
            # Switch games must construct the DDS/ASTC headers manually.
            tasks = []
            for i in range(self.num_files):
                os.makedirs(extractionDir, exist_ok=True)
                # Unswizzle
                textureFormat = getFormatByIndex(self.infos[i]["format"])
                
                specialPad = 1
                if "specialPad" in self.infos[i].keys() and "flags" in self.infos[i].keys() and self.infos[i]["flags"] & 0x4:
                    specialPad = self.infos[i]["specialPad"]
                
                texture = loadImageData(
                    textureFormat,
                    self.infos[i]['width'],
                    self.infos[i]['height'],
                    self.infos[i]['depth'],
                    self.infos[i]['arrayCount'],
                    self.infos[i]['mipCount'],
                    self.data[self.offsets[i]:self.offsets[i]+self.sizes[i]],
                    self.infos[i]["blockHeightLog2"],
                    specialPad=specialPad
                    )

                # Construct headers
                if "ASTC" in textureFormat:
                    # ASTC
                    formatInfo = getFormatTable(textureFormat)
                    with open(os.path.join(extractionDir, f"{self.idx[i]:0>8X}.astc"), "wb") as f:
                        f.write(b''.join([
                            b'\x13\xAB\xA1\x5C', formatInfo[1].to_bytes(1, "little"),
                            formatInfo[2].to_bytes(1, "little"), b'\1',
                            self.infos[i]['width'].to_bytes(3, "little"),
                            self.infos[i]['height'].to_bytes(3, "little"), b'\1\0\0',
                            texture,
                        ]))
                    
                    tasks.append(asyncio.ensure_future(decode_astc(os.path.join(extractionDir, f"{self.idx[i]:0>8X}.astc"))))
                else:
                    # DDS
                    headerDataObject = DDSHeader(textureFormat, self.infos[i]['width'], self.infos[i]['height'], self.infos[i]['depth'])
                    with open(os.path.join(extractionDir, f"{self.idx[i]:0>8X}.dds"), "wb") as f:
                        f.write(headerDataObject.save())
                        f.write(texture)
                
                count += 1
            
            loop = asyncio.get_event_loop()
            loop.run_until_complete(asyncio.gather(*tasks))

            # Write metadata file (need to store format and other data for later)
            metadata = {}
            for i in range(self.num_files):
                metadata[f"{self.idx[i]:0>8X}"] = {
                    "type": self.infos[i]["type"],
                    "format": self.infos[i]["format"],
                    "blockHeightLog2": self.infos[i]["blockHeightLog2"],
                }

                if "specialPad" in self.infos[i].keys():
                    # add AC/B3 specialPad
                    metadata[f"{self.idx[i]:0>8X}"]["specialPad"] = self.infos[i]["specialPad"]
                    metadata[f"{self.idx[i]:0>8X}"]["blockHeightLog2"] = self.infos[i]["blockHeightLog2"]
                    metadata[f"{self.idx[i]:0>8X}"]["flags"] = self.infos[i]["flags"]
                    metadata[f"{self.idx[i]:0>8X}"]["unk2"] = self.infos[i]["unk2"]
                    metadata[f"{self.idx[i]:0>8X}"]["unk3"] = self.infos[i]["unk3"]
                    metadata[f"{self.idx[i]:0>8X}"]["unk4"] = self.infos[i]["unk4"]

            with open(os.path.join(extractionDir, "xt1_info.json"), "w") as f:
                f.write(json.dumps(metadata, indent=4))

        return count

# Asynchronously decodes an ASTC file to PNG.
async def decode_astc(filePath):
    script_file = os.path.realpath(__file__)
    directory = os.path.dirname(script_file).replace("importer", "")
    appPath = os.path.join(directory, "astcenc-avx2.exe")
    result = subprocess.run([appPath, "-ds", filePath, filePath.replace('.astc', '.png')], cwd=directory)
    os.remove(filePath)

# WAY too lazy to reimplement this; remind me later i guess?
class DDSHeader(object):
    # https://docs.microsoft.com/en-us/windows/win32/direct3ddds/dds-header
    class DDSPixelFormat(object):
        def __init__(self, textureFormat):
            self.size = 32
            self.flags = 4 # contains fourcc
            if textureFormat == "BC6H_UF16":
                self.fourCC = b'DX10'
            elif textureFormat.startswith("BC1"):
                self.fourCC = b'DXT1'
            elif textureFormat.startswith("BC2"):
                self.fourCC = b'DXT3'
            else:
                self.fourCC = b'DXT5'
            # BC1 = DXT1, BC2 = DXT3, above is DXT5 i think; BC6H is the only DX10 format
            self.RGBBitCount = 0
            self.RBitMask = 0x00000000
            self.GBitMask = 0x00000000
            self.BBitMask = 0x00000000
            self.ABitMask = 0x00000000

    def __init__(self, textureFormat, width, height, depth):
        self.magic = b'DDS\x20'
        self.size = 124
        self.flags = 0x1 + 0x2 + 0x4 + 0x1000 + 0x20000 + 0x80000 # Defaults (caps, height, width, pixelformat) + mipmapcount and linearsize
        self.height = height
        self.width = width
        self.format = textureFormat
        if self.format == "R8G8B8A8_UNORM":
            self.pitchOrLinearSize = ((self.width + 1) >> 1) * 4
        else:
            self.pitchOrLinearSize = int(max(1, ((self.width+3)/4) ) * getFormatTable(self.format)[0]) # https://docs.microsoft.com/en-us/windows/win32/direct3ddds/dx-graphics-dds-pguide
        self.depth = depth
        self.mipmapCount = 1#texture.mipCount # Setting this to the normal value breaks everything, don't do that
        self.reserved1 = [0x00000000] * 11
        self.ddspf = self.DDSPixelFormat(textureFormat)
        self.caps = 4198408 # Defaults (DDSCAPS_TEXTURE) + mipmap and complex
        self.caps2 = 0 
        self.caps3 = 0
        self.caps4 = 0
        self.reserved2 = 0

    def save(self):
        output = self.magic + pack("20I4s10I", self.size, self.flags, self.height, self.width, self.pitchOrLinearSize, self.depth,
            self.mipmapCount, self.reserved1[0], self.reserved1[1], self.reserved1[2], self.reserved1[3], self.reserved1[4],
            self.reserved1[5], self.reserved1[6], self.reserved1[7], self.reserved1[8], self.reserved1[9], self.reserved1[10],
            self.ddspf.size, self.ddspf.flags, self.ddspf.fourCC, self.ddspf.RGBBitCount, self.ddspf.RBitMask, self.ddspf.GBitMask,
            self.ddspf.BBitMask, self.ddspf.ABitMask, self.caps, self.caps2, self.caps3, self.caps4, self.reserved2)
        if self.format == "BC6H_UF16":
            output += bytearray(b"\x5F\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00")
        return output

class ExtractNierWtaWtp(bpy.types.Operator, ImportHelper):
    '''Extract textures from WTA/WTP files'''
    bl_idname = "import_scene.nier_wta_wtp"
    bl_label = "Extract WTA/WTP textures"
    bl_options = {'PRESET'}
    filename_ext = ".wta"
    filter_glob: StringProperty(default="*.wta", options={'HIDDEN'})

    extract_bulk: bpy.props.BoolProperty(name="Extract Bulk", default=False)

    def execute(self, context):
        if self.extract_bulk:
            extractedDdsCount = 0
            extractedWtpCount = 0
            dir = self.filepath if os.path.isdir(self.filepath) else os.path.dirname(self.filepath)
            for wtaPath in os.listdir(dir):
                if not wtaPath.endswith(".wta"):
                    continue
                full_wtaPath = os.path.join(dir, wtaPath)
                full_wtpPath = full_wtaPath[:-4] + ".wtp"
                extractDir = os.path.join(dir, "nier2blender_extracted", os.path.basename(wtaPath), "textures")
                extractedDdsCount += extractFromWta(full_wtaPath, full_wtpPath, extractDir)
                extractedWtpCount += 1
            print(f"Extracted {extractedDdsCount} DDS files and {extractedWtpCount} WTP files")
        else:
            dir = os.path.dirname(self.filepath)
            full_wtaPath = self.filepath
            full_wtpPath = full_wtaPath[:-4] + ".wtp"
            extractDir = os.path.join(dir, "nier2blender_extracted", os.path.basename(self.filepath), "textures")
            extractedDdsCount = extractFromWta(full_wtaPath, full_wtpPath, extractDir)
            print(f"Extracted {extractedDdsCount} DDS files")
        
        self.report({'INFO'}, f"{extractedDdsCount} textures extracted")

        return {'FINISHED'}

def extractFromWta(wtaPath, wtpPath, extractDir) -> int:
    with open(wtaPath, "rb") as wtaFile:
        with open(wtpPath, "rb") as wtpFile:
            wta = WTAData(wtaFile, wtpFile)
    extractedCount = wta.extract_textures(extractDir)
    return extractedCount
