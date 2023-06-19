import subprocess
import asyncio
import math
import json
from ...utils.ioUtils import read_int32, write_Int32, write_uInt16, write_float16
from . import generate_wta_wtp_data
from .wta_wtp_utils import *
from ..tegrax1swizzle import compressImageData, getFormatByIndex

# Asynchronously encodes a PNG file to ASTC.
async def encode_astc(filePath, format: str):
    script_file = os.path.realpath(__file__)
    directory = os.path.dirname(script_file).replace("exporter", "")
    appPath = os.path.join(directory, "astcenc-avx2.exe")
    result = subprocess.run([appPath, "-cs", filePath, filePath.replace('.png', '.astc'), format.split("_")[1], "-medium"], cwd=directory)

def main(context, export_filepath_wta, export_filepath_wtp, exportingForGame):
    wta_fp = open(export_filepath_wta,'wb')
    wtp_fp = open(export_filepath_wtp,'wb')

    # Assign data and check if valid
    identifiers_array, texture_paths_array, albedo_indexes, metadata_path = generate_wta_wtp_data.generate(context, exportingForGame)

    if None in [identifiers_array, texture_paths_array, albedo_indexes]:
        print("WTP Export Failed! :{")
        return

    # Assign some shit
    unknown04 = 3
    textureCount = len(texture_paths_array)
    paddingAmount = ((textureCount + 7) // 8) * 8	#rounds up to the nearest 8th integer
    textureOffsetArrayOffset = 32
    textureSizeArrayOffset = textureOffsetArrayOffset + (paddingAmount * 4)
    unknownArrayOffset1 = textureSizeArrayOffset + (paddingAmount * 4)
    textureIdentifierArrayOffset = unknownArrayOffset1 + (paddingAmount * 4)
    textureInfoArrayOffset = textureIdentifierArrayOffset + (paddingAmount * 4)
    wtaTextureOffset = [0] * textureCount
    wtaTextureSize = [0] * textureCount
    wtaTextureIdentifier = [0] * textureCount
    unknownArray1 = [0] * textureCount
    textureInfoArray = []
    paddingAmountArray = []

    # Pad the DDS files
    #pad_dds_files(texture_paths_array)

    current_wtaTextureOffset = 0

    if exportingForGame == "NIER":
        # Open every DDS texture
        for i in range(textureCount):
            dds_fp = open(texture_paths_array[i], 'rb')
            dds_paddedSize = os.stat(texture_paths_array[i]).st_size

            #checks dds dxt and cube map info
            dds_fp.seek(84)
            dxt = dds_fp.read(4)
            dds_fp.seek(112)
            cube = dds_fp.read(4)

            #finds how much padding bytes are added to a dds
            dds_padding = 0
            if i != len(texture_paths_array)-1:
                dds_fp.seek(dds_paddedSize-4)
                dds_padding = read_int32(dds_fp)
            paddingAmountArray.append(dds_padding)

            #wtaTextureOffset
            if i+1 in range(len(wtaTextureSize)):
                """
                if dds_paddedSize < 12289:
                    wtaTextureOffset[i+1] = wtaTextureOffset[i] + 12288
                elif dds_paddedSize < 176129:
                    wtaTextureOffset[i+1] = wtaTextureOffset[i] + 176128
                elif dds_paddedSize < 352257:
                    wtaTextureOffset[i+1] = wtaTextureOffset[i] + 352256
                elif dds_paddedSize < 528385:
                    wtaTextureOffset[i+1] = wtaTextureOffset[i] + 528384
                elif dds_paddedSize < 700417:
                    wtaTextureOffset[i+1] = wtaTextureOffset[i] + 700416
                elif dds_paddedSize < 2797569:
                    wtaTextureOffset[i+1] = wtaTextureOffset[i] + 2797568
                else:
                    wtaTextureOffset[i+1] = dds_paddedSize
                """
                wtaTextureOffset[i+1] = current_wtaTextureOffset + dds_paddedSize
            current_wtaTextureOffset += dds_paddedSize
            #wtaTextureSize
            wtaTextureSize[i] = dds_paddedSize# - dds_padding
            #wtaTextureIdentifier
            wtaTextureIdentifier[i] = identifiers_array[i]
            #unknownArray1
            if i in albedo_indexes:
                unknownArray1[i] = 637534240
            else:
                unknownArray1[i] = 570425376
            #unknownArray2
            if dxt not in [b'DXT1', b'DXT3', b'DXT5']:
                print("Unknown DXT format! Make sure you use DXT1, DXT3 or DXT5!")
                dds_fp.close()
                wta_fp.close()
                return

            if dxt == b'DXT1':
                textureInfoArray.append(71)
                textureInfoArray.append(3)
                if cube == b'\x00\xfe\x00\x00':
                    textureInfoArray.append(4)
                else:
                    textureInfoArray.append(0)
                textureInfoArray.append(1)
                textureInfoArray.append(0)
            if dxt == b'DXT3':
                textureInfoArray.append(74)
                textureInfoArray.append(3)
                if cube == b'\x00\xfe\x00\x00':
                    textureInfoArray.append(4)
                else:
                    textureInfoArray.append(0)
                textureInfoArray.append(1)
                textureInfoArray.append(0)
            if dxt == b'DXT5':
                textureInfoArray.append(77)
                textureInfoArray.append(3)
                if cube == b'\x00\xfe\x00\x00':
                    textureInfoArray.append(4)
                else:
                    textureInfoArray.append(0)
                textureInfoArray.append(1)
                textureInfoArray.append(0)
            
            # Write WTP
            dds_fp.seek(0)
            content = dds_fp.read()
            #print("-Writing dds: " + texture_paths_array[i] + " to file: " + export_filepath + " at position: " + str(i))
            wtp_fp.write(content)
            dds_fp.close()


            dds_fp.close()

        # Write everything
        padding = b''
        for i in range(paddingAmount - textureCount):
            padding += b'\x00\x00\x00\x00'

        wta_fp.write(b'WTB\x00')
        wta_fp.write(to_bytes(unknown04))
        wta_fp.write(to_bytes(textureCount))
        wta_fp.write(to_bytes(textureOffsetArrayOffset))
        wta_fp.write(to_bytes(textureSizeArrayOffset))
        wta_fp.write(to_bytes(unknownArrayOffset1))
        wta_fp.write(to_bytes(textureIdentifierArrayOffset))
        wta_fp.write(to_bytes(textureInfoArrayOffset))
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureOffset[i]))
        wta_fp.write(padding)
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureSize[i]))
        wta_fp.write(padding)
        for i in range(textureCount):
            wta_fp.write(to_bytes(unknownArray1[i]))
        wta_fp.write(padding)
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureIdentifier[i]))
        wta_fp.write(padding)
        for i in range(textureCount):
            wta_fp.write(to_bytes(textureInfoArray[(i*5)]))
            wta_fp.write(to_bytes(textureInfoArray[(i*5)+1]))
            wta_fp.write(to_bytes(textureInfoArray[(i*5)+2]))
            wta_fp.write(to_bytes(textureInfoArray[(i*5)+3]))
            wta_fp.write(to_bytes(textureInfoArray[(i*5)+4]))
        wta_fp.write(padding)
    
    elif exportingForGame == "NIERSWITCH":
        # NIER SWITCH
        
        # Change offsets
        textureSizeArrayOffset = math.ceil((textureOffsetArrayOffset + (textureCount * 4)) / 0x20) * 0x20
        unknownArrayOffset1 = math.ceil((textureSizeArrayOffset + (textureCount * 4)) / 0x20) * 0x20
        textureIdentifierArrayOffset = math.ceil((unknownArrayOffset1 + (textureCount * 4)) / 0x20) * 0x20
        textureInfoArrayOffset = math.ceil((textureIdentifierArrayOffset + (textureCount * 4)) / 0x20) * 0x20

        # Encode all PNG files to ASTC (asynchronously for speed)
        tasks = []
        for i in range(textureCount):
            if ".png" in texture_paths_array[i].lower():
                textureFormat = "ASTC_6x6_UNORM"
                if identifiers_array[i].upper() in metadata.keys():
                    textureFormat = getFormatByIndex(metadata[identifiers_array[i].upper()]["format"])
                tasks.append(asyncio.ensure_future(encode_astc(texture_paths_array[i], textureFormat)))
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))

        # Open every DDS texture
        for i in range(textureCount):
            path = texture_paths_array[i].replace(".png", ".astc")

            #wtaTextureIdentifier
            wtaTextureIdentifier[i] = identifiers_array[i]
            wtaTextureOffset[i] = wtp_fp.tell()

            # Default infos
            info = {
                "magic": b".tex",
                "format": 0x7D,
                "unk1": 1,
                "width": 0,
                "height": 0,
                "depth": 1,
                "mipCount": 1,
                "unk2": 256,
                "unk3": 0.25,
                "unk4": 0,
                # guesses used for swizzling (wtpImportOperator.py)
                "type": 1,
                "textureLayout": [4, 0],
                "arrayCount": 1
            }

            if ".dds" in path.lower():
                dds_fp = open(path, 'rb')
                dds_paddedSize = os.stat(texture_paths_array[i]).st_size

                dds_fp.seek(12)
                info["width"] = int.from_bytes(dds_fp.read(4), "little")
                info["height"] = int.from_bytes(dds_fp.read(4), "little")

                #checks dds dxt and cube map info
                dds_fp.seek(84)
                dxt = dds_fp.read(4)
                dds_fp.seek(112)
                cube = dds_fp.read(4)


                # DXT checking
                if info["format"] == 0x7D: # If not prefilled
                    if dxt == b'DXT1':
                        info["format"] = 0x46 # BC1_UNORM_SRGB
                    elif dxt == b'DXT3':
                        info["format"] = 0x47 # BC2_UNORM_SRGB
                    elif dxt == b'DXT5':
                        info["format"] = 0x48 # BC3_UNORM_SRGB
                    else:
                        info["format"] = 0x50 # BC6H_UF16

                #unknownArray1
                unknownArray1[i] = 1677721632 # DDS textures are always SRGB
                wtaTextureOffset[i] = wtp_fp.tell()

                dds_fp.seek(80)
                blockHeightLog2 = info["textureLayout"][0] & 7
                wtp_fp.write(compressImageData(
                    getFormatByIndex(info['format']),
                    info['width'],
                    info['height'],
                    info['depth'],
                    info['arrayCount'],
                    info['mipCount'],
                    dds_fp.read(),
                    blockHeightLog2
                ))
                wtaTextureSize[i] = wtp_fp.tell() - wtaTextureOffset[i]
                if wtaTextureSize[i] < 90112:
                    wtaTextureSize[i] = 90112
                    while wtp_fp.tell() < (wtaTextureSize[i] + wtaTextureOffset[i]):
                        wtp_fp.write(b'\x00')
                info['imageSize'] = wtaTextureSize[i]
                
                dds_fp.close()
            else:
                # ASTC
                astc_fp = open(path, 'rb')
                astc_fp.seek(7)
                info["width"] = int.from_bytes(astc_fp.read(3), "little")
                info["height"] = int.from_bytes(astc_fp.read(3), "little")
                
                astc_fp.seek(16)
                blockHeightLog2 = info["textureLayout"][0] & 7
                wtp_fp.write(compressImageData(
                    getFormatByIndex(info['format']),
                    info['width'],
                    info['height'],
                    info['depth'],
                    info['arrayCount'],
                    info['mipCount'],
                    astc_fp.read(),
                    blockHeightLog2
                ))
                wtaTextureSize[i] = wtp_fp.tell() - wtaTextureOffset[i]
                if wtaTextureSize[i] < 90112:
                    wtaTextureSize[i] = 90112
                    while wtp_fp.tell() < (wtaTextureSize[i] + wtaTextureOffset[i]):
                        wtp_fp.write(b'\x00')
                info['imageSize'] = wtaTextureSize[i]
                
                if "SRGB" in getFormatByIndex(info["format"]):
                    unknownArray1[i] = (1677721632)
                else:
                    unknownArray1[i] = (1610612768)
                
                astc_fp.close()
                # Remove the temporary ASTC file
                os.remove(path)

            # MipCount needs to be set to 1 -- TODO: find what's causing this
            #info["mipCount"] = int(math.log2(max(info["width"], info["height"]))) + 1
            textureInfoArray.append(info)
            wtp_fp.seek(math.ceil(wtp_fp.tell() / 16) * 16)

        # Write everything
        wta_fp.write(b'WTB\x00')
        wta_fp.write(to_bytes(unknown04))
        wta_fp.write(to_bytes(textureCount))
        wta_fp.write(to_bytes(textureOffsetArrayOffset))
        wta_fp.write(to_bytes(textureSizeArrayOffset))
        wta_fp.write(to_bytes(unknownArrayOffset1))
        wta_fp.write(to_bytes(textureIdentifierArrayOffset))
        wta_fp.write(to_bytes(textureInfoArrayOffset))
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureOffset[i]))
        wta_fp.seek(textureSizeArrayOffset)
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureSize[i]))
        wta_fp.seek(unknownArrayOffset1)
        for i in range(textureCount):
            wta_fp.write(to_bytes(unknownArray1[i]))
        wta_fp.seek(textureIdentifierArrayOffset)
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureIdentifier[i]))
        
        for i in range(textureCount):
            wta_fp.seek(textureInfoArrayOffset + i * 0x100)
            wta_fp.write(textureInfoArray[i]["magic"])
            write_Int32(wta_fp, textureInfoArray[i]["format"])
            write_Int32(wta_fp, 1)
            write_Int32(wta_fp, textureInfoArray[i]["width"])
            write_Int32(wta_fp, textureInfoArray[i]["height"])
            write_Int32(wta_fp, textureInfoArray[i]["depth"])
            write_Int32(wta_fp, textureInfoArray[i]["mipCount"])
            write_Int32(wta_fp, textureInfoArray[i]["unk2"])
            write_float16(wta_fp, textureInfoArray[i]["unk3"])
            write_uInt16(wta_fp, textureInfoArray[i]["unk4"])
        while wta_fp.tell() % 16 != 0:
            wta_fp.write(b'\x00')
    
    elif exportingForGame == "ASTRALCHAIN":
        # ASTRAL CHAIN
        
        # Change offsets
        textureSizeArrayOffset = math.ceil((textureOffsetArrayOffset + (textureCount * 4)) / 0x20) * 0x20
        unknownArrayOffset1 = math.ceil((textureSizeArrayOffset + (textureCount * 4)) / 0x20) * 0x20
        textureIdentifierArrayOffset = math.ceil((unknownArrayOffset1 + (textureCount * 4)) / 0x20) * 0x20
        textureInfoArrayOffset = math.ceil((textureIdentifierArrayOffset + (textureCount * 4)) / 0x20) * 0x20

        # Open metadata
        if metadata_path:
            with open(metadata_path, "r") as metadata_fp:
                metadata = json.load(metadata_fp)
        else:
            metadata = {}

        # Encode all PNG files to ASTC (asynchronously for speed)
        tasks = []
        for i in range(textureCount):
            if ".png" in texture_paths_array[i].lower():
                textureFormat = "ASTC_4x4_UNORM"
                if identifiers_array[i].upper() in metadata.keys():
                    textureFormat = getFormatByIndex(metadata[identifiers_array[i].upper()]["format"])
                tasks.append(asyncio.ensure_future(encode_astc(texture_paths_array[i], textureFormat)))
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))

        # Open every DDS texture
        for i in range(textureCount):
            path = texture_paths_array[i].replace(".png", ".astc")

            #wtaTextureIdentifier
            wtaTextureIdentifier[i] = identifiers_array[i]
            wtaTextureOffset[i] = wtp_fp.tell()

            # Default infos
            info = {
                "magic": b"XT1\x00",
                "unk1": 16777473, # 0x 01 01 00 01
                "imageSize": 0, # Uint64 identical to header (which is weird because the header is uint32, lol)
                "headerSize": 56, # Always 56
                "mipCount": 1,
                "type": 1,
                "format": 0x79,
                "width": 0,
                "height": 0,
                "depth": 1,
                "unk4": 32, # Always 32 (?)
                "textureLayout": [1027, 65543],
                "arrayCount": 1
            }

            if identifiers_array[i].upper() in metadata.keys():
                info["type"] = metadata[identifiers_array[i].upper()]["type"]
                info["format"] = metadata[identifiers_array[i].upper()]["format"]
                info["textureLayout"] = metadata[identifiers_array[i].upper()]["textureLayout"]

            if ".dds" in path.lower():
                dds_fp = open(path, 'rb')
                dds_paddedSize = os.stat(texture_paths_array[i]).st_size

                dds_fp.seek(12)
                info["width"] = int.from_bytes(dds_fp.read(4), "little")
                info["height"] = int.from_bytes(dds_fp.read(4), "little")

                #checks dds dxt and cube map info
                dds_fp.seek(84)
                dxt = dds_fp.read(4)
                dds_fp.seek(112)
                cube = dds_fp.read(4)


                # DXT checking
                if info["format"] == 0x79: # If not prefilled
                    if dxt == b'DXT1':
                        info["format"] = 0x46 # BC1_UNORM_SRGB
                    elif dxt == b'DXT3':
                        info["format"] = 0x47 # BC2_UNORM_SRGB
                    elif dxt == b'DXT5':
                        info["format"] = 0x48 # BC3_UNORM_SRGB
                    else:
                        info["format"] = 0x50 # BC6H_UF16

                # Astral Chain uses no padding (i think); probably unnecessary

                #unknownArray1
                unknownArray1[i] = 1677721632 # DDS textures are always SRGB
                wtaTextureOffset[i] = wtp_fp.tell()

                dds_fp.seek(80)
                blockHeightLog2 = info["textureLayout"][0] & 7
                wtp_fp.write(compressImageData(
                    getFormatByIndex(info['format']),
                    info['width'],
                    info['height'],
                    info['depth'],
                    info['arrayCount'],
                    info['mipCount'],
                    dds_fp.read(),
                    blockHeightLog2
                ))
                wtaTextureSize[i] = wtp_fp.tell() - wtaTextureOffset[i]
                if wtaTextureSize[i] < 90112:
                    wtaTextureSize[i] = 90112
                    while wtp_fp.tell() < (wtaTextureSize[i] + wtaTextureOffset[i]):
                        wtp_fp.write(b'\x00')
                info['imageSize'] = wtaTextureSize[i]
                
                dds_fp.close()
            else:
                # ASTC
                astc_fp = open(path, 'rb')
                astc_fp.seek(7)
                info["width"] = int.from_bytes(astc_fp.read(3), "little")
                info["height"] = int.from_bytes(astc_fp.read(3), "little")
                
                astc_fp.seek(16)
                blockHeightLog2 = info["textureLayout"][0] & 7
                wtp_fp.write(compressImageData(
                    getFormatByIndex(info['format']),
                    info['width'],
                    info['height'],
                    info['depth'],
                    info['arrayCount'],
                    info['mipCount'],
                    astc_fp.read(),
                    blockHeightLog2
                ))
                wtaTextureSize[i] = wtp_fp.tell() - wtaTextureOffset[i]
                if wtaTextureSize[i] < 90112:
                    wtaTextureSize[i] = 90112
                    while wtp_fp.tell() < (wtaTextureSize[i] + wtaTextureOffset[i]):
                        wtp_fp.write(b'\x00')
                info['imageSize'] = wtaTextureSize[i]
                
                if "SRGB" in getFormatByIndex(info["format"]):
                    unknownArray1[i] = (1677721632)
                else:
                    unknownArray1[i] = (1610612768)
                
                astc_fp.close()
                # Remove the temporary ASTC file
                os.remove(path)

            # MipCount needs to be set to 1 -- TODO: find what's causing this
            #info["mipCount"] = int(math.log2(max(info["width"], info["height"]))) + 1
            textureInfoArray.append(info)
            wtp_fp.seek(math.ceil(wtp_fp.tell() / 16) * 16)

        # Write everything
        wta_fp.write(b'WTB\x00')
        wta_fp.write(to_bytes(unknown04))
        wta_fp.write(to_bytes(textureCount))
        wta_fp.write(to_bytes(textureOffsetArrayOffset))
        wta_fp.write(to_bytes(textureSizeArrayOffset))
        wta_fp.write(to_bytes(unknownArrayOffset1))
        wta_fp.write(to_bytes(textureIdentifierArrayOffset))
        wta_fp.write(to_bytes(textureInfoArrayOffset))
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureOffset[i]))
        wta_fp.seek(textureSizeArrayOffset)
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureSize[i]))
        wta_fp.seek(unknownArrayOffset1)
        for i in range(textureCount):
            wta_fp.write(to_bytes(unknownArray1[i]))
        wta_fp.seek(textureIdentifierArrayOffset)
        for i in range(textureCount):
            wta_fp.write(to_bytes(wtaTextureIdentifier[i]))
        wta_fp.seek(textureInfoArrayOffset)
        for i in range(textureCount):
            wta_fp.write(textureInfoArray[i]["magic"])
            write_Int32(wta_fp, textureInfoArray[i]["unk1"])
            write_Int32(wta_fp, 0)
            write_Int32(wta_fp, textureInfoArray[i]["imageSize"])
            write_Int32(wta_fp, textureInfoArray[i]["headerSize"])
            write_Int32(wta_fp, textureInfoArray[i]["mipCount"])
            write_Int32(wta_fp, textureInfoArray[i]["type"])
            write_Int32(wta_fp, textureInfoArray[i]["format"])
            write_Int32(wta_fp, textureInfoArray[i]["width"])
            write_Int32(wta_fp, textureInfoArray[i]["height"])
            write_Int32(wta_fp, textureInfoArray[i]["depth"])
            write_Int32(wta_fp, textureInfoArray[i]["unk4"])
            write_Int32(wta_fp, textureInfoArray[i]["textureLayout"][0])
            write_Int32(wta_fp, textureInfoArray[i]["textureLayout"][1])
        while wta_fp.tell() % 16 != 0:
            wta_fp.write(b'\x00')


    wta_fp.close()
    wtp_fp.close()
    print('WTA + WTP Export Complete. :]}')