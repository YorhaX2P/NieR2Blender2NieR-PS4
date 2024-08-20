# TegraX1Swizzle.py - cabalex [Updated Aug 2024]
# Based on:
# KillzXGaming's Switch Toolbox texture decoding - https://github.com/KillzXGaming/Switch-Toolbox/blob/604f7b3d369bc97d9d05632da3211ed11b990ba7/Switch_Toolbox_Library/Texture%20Decoding/Switch/TegraX1Swizzle.cs
# aboood40091's BNTX-Extractor - https://github.com/aboood40091/BNTX-Extractor/blob/master/swizzle.py
# [Format table] Ryujinx's image table - https://github.com/Ryujinx/Ryujinx/blob/c86aacde76b5f8e503e2b412385c8491ecc86b3b/Ryujinx.Graphics/Graphics3d/Texture/ImageUtils.cs

# Aug 2024: Added special padding to GOB offsets.

formatTable = {
	"R8G8B8A8_UNORM": [4, 1, 1, 1],
	"BC1_UNORM": [8, 4, 4, 1],
	"BC2_UNORM": [16, 4, 4, 1],
	"BC3_UNORM": [16, 4, 4, 1],
	"BC4_UNORM": [8, 4, 4, 1],
	"BC1_UNORM_SRGB": [8, 4, 4, 1],
	"BC2_UNORM_SRGB": [16, 4, 4, 1],
	"BC3_UNORM_SRGB": [16, 4, 4, 1],
	"BC4_SNORM": [8, 4, 4, 1],
	"BC6H_UF16": [16, 4, 4, 1],
	"ASTC_4x4_UNORM": [16, 4, 4, 1],
	"ASTC_6x6_UNORM": [16, 6, 6, 1],
	"ASTC_8x8_UNORM": [16, 8, 8, 1],
	"ASTC_4x4_SRGB": [16, 4, 4, 1],
	"ASTC_6x6_SRGB": [16, 6, 6, 1],
	"ASTC_8x8_SRGB": [16, 8, 8, 1]
}
# each one: bytesPerPixel, blockWidth, blockHeight, blockDepth, targetBuffer (but i removed targetBuffer)

formats = {
	# DDS
	0x25: "R8G8B8A8_UNORM",
	0x42: "BC1_UNORM",
	0x43: "BC2_UNORM",
	0x44: "BC3_UNORM",
	0x45: "BC4_UNORM",
	0x46: "BC1_UNORM_SRGB",
	0x47: "BC2_UNORM_SRGB",
	0x48: "BC3_UNORM_SRGB",
	0x49: "BC4_SNORM",
	0x50: "BC6H_UF16",
	# ASTC (weird texture formats ??)
	0x2D: "ASTC_4x4_UNORM",
	0x38: "ASTC_8x8_UNORM",
	0x3A: "ASTC_12x12_UNORM",
	# ASTC
	0x79: "ASTC_4x4_UNORM",
	0x80: "ASTC_8x8_UNORM",
	0x87: "ASTC_4x4_SRGB",
	0x8E: "ASTC_8x8_SRGB",

	# Unknown NieR switch formats
    0x7D: "ASTC_6x6_UNORM",
    0x8B: "ASTC_6x6_SRGB",
}

def getFormatTable(_format):
	return formatTable[_format]

def getFormatByIndex(_format):
	return formats[_format]

def pow2_round_up(x):
	x -= 1
	x |= x >> 1
	x |= x >> 2
	x |= x >> 4
	x |= x >> 8
	x |= x >> 16
	return x + 1

def DIV_ROUND_UP(n, d):
	return (n + d - 1) // d

def subArray(data, offset, length):
	return data[offset:offset+length]

def round_up(x, y):
	return ((x - 1) | (y - 1)) + 1


def _swizzle(width, height, depth, blkWidth, blkHeight, blkDepth, roundPitch, bpp, tileMode, blockHeightLog2, specialPad, data, toSwizzle):
	block_height = 1 << blockHeightLog2

	width = DIV_ROUND_UP(width, blkWidth)
	height = DIV_ROUND_UP(height, blkHeight)
	depth = DIV_ROUND_UP(depth, blkDepth)

	if tileMode == 1:
		if roundPitch == 1:
			pitch = round_up(width * bpp, 32)
		else:
			pitch = width * bpp
		surfSize = round_up(pitch * height, 32)

	else:
		pitch = round_up(width * bpp, 64)
		surfSize = pitch * round_up(height, block_height * 8)

	result = bytearray(surfSize)

	for y in range(height):
		for x in range(width):
			if tileMode == 1:
				pos = y * pitch + x * bpp

			else:
				pos = getAddrBlockLinear(x, y, width, bpp, 0, block_height, specialPad)

			pos_ = (y * width + x) * bpp

			if pos + bpp <= surfSize:
				if toSwizzle == 1:
					result[pos:pos + bpp] = data[pos_:pos_ + bpp]

				else:
					result[pos_:pos_ + bpp] = data[pos:pos + bpp]
	size = width * height * bpp
	return result[:size]

#def deswizzle(width, height, blkWidth, blkHeight, bpp, tileMode, alignment, size_range, data):
def deswizzle(width, height, depth, blkWidth, blkHeight, blkDepth, roundPitch, bpp, tileMode, size_range, specialPad, data):
	return _swizzle(width, height, depth, blkWidth, blkHeight, blkDepth, roundPitch, bpp, tileMode, size_range, specialPad, bytes(data), 0)
	#return _swizzle(width, height, blkWidth, blkHeight, bpp, tileMode, alignment, size_range, bytes(data), 0)


def swizzle(width, height, depth, blkWidth, blkHeight, blkDepth, roundPitch, bpp, tileMode, size_range, specialPad, data):
	return _swizzle(width, height, depth, blkWidth, blkHeight, blkDepth, roundPitch, bpp, tileMode, size_range, specialPad, bytes(data), 1)


def getAddrBlockLinear(x, y, image_width, bytes_per_pixel, base_address, block_height, specialPad):
	"""
	From the Tegra X1 TRM
	"""
	image_width_in_gobs = DIV_ROUND_UP(round_up(image_width, specialPad) * bytes_per_pixel, 64)

	GOB_address = (base_address
				   + (y // (8 * block_height)) * 512 * block_height * image_width_in_gobs
				   + (x * bytes_per_pixel // 64) * 512 * block_height
				   + (y % (8 * block_height) // 8) * 512)

	x *= bytes_per_pixel

	Address = (GOB_address + ((x % 64) // 32) * 256 + ((y % 8) // 2) * 64
			   + ((x % 32) // 16) * 32 + (y % 2) * 16 + (x % 16))

	return Address

def loadImageData(format: str, width: int, height: int, depth: int, arrayCount: int, mipCount: int, imageData, blockHeightLog2, target=1, linearTileMode=False, specialPad=1):
	[bpp, blkWidth, blkHeight, blkDepth] = getFormatTable(format)
	blockHeight = DIV_ROUND_UP(height, blkHeight)
	pitch = 0
	dataAlignment = 512
	if linearTileMode:
		tileMode = 1
	else:
		tileMode = 0
	if depth > 1:
		numDepth = depth
	else:
		numDepth = 1
	linesPerBlockHeight = (1 << int(blockHeightLog2)) * 8
	arrayOffset = 0
	for depthLevel in range(numDepth):
		for arrayLevel in range(arrayCount):
			surfaceSize = 0
			blockHeightShift = 0
			mipOffsets = []
			for mipLevel in range(mipCount):
				width = max(1, width >> mipLevel)
				height = max(1, height >> mipLevel)
				depth = max(1, depth >> mipLevel)
				size = DIV_ROUND_UP(width, blkWidth) * DIV_ROUND_UP(height, blkHeight) * bpp
				if pow2_round_up(DIV_ROUND_UP(height, blkWidth)) < linesPerBlockHeight:
					blockHeightShift += 1
				width__ = DIV_ROUND_UP(width, blkWidth)
				height__ = DIV_ROUND_UP(height, blkHeight)

				# calculate the mip size instead
				alignedData = bytearray(round_up(surfaceSize, dataAlignment) - surfaceSize)
				surfaceSize += len(alignedData)
				mipOffsets.append(surfaceSize)

				# get the first mip offset and current one and the total image size
				msize = int((mipOffsets[0] + len(imageData) - mipOffsets[mipLevel]) / arrayCount)
				
				data_ = subArray(imageData, arrayOffset + mipOffsets[mipLevel], msize)
				try:
					pitch = round_up(width__ * bpp, 64)
					surfaceSize += pitch * round_up(height__, max(1, blockHeight >> blockHeightShift) * 8)
					result = deswizzle(width, height, depth, blkWidth, blkHeight, blkDepth, target, bpp, tileMode, max(0, blockHeightLog2 - blockHeightShift), specialPad, data_)

					# the program creates a copy and uses that to remove unneeded data
					# yeah, i'm not doing that
					return result
				except Exception as e:
					raise e
					print(f"Failed to swizzle texture! {e}")
					return False
			arrayOffset += len(imageData) / arrayCount
	return False

def compressImageData(format: str, width: int, height: int, depth: int, arrayCount: int, mipCount: int, imageData, blockHeightLog2, target=1, linearTileMode=False, specialPad=1):
	bpp = formatTable[format][0]
	blkWidth = formatTable[format][1]
	blkHeight = formatTable[format][2]
	blkDepth = formatTable[format][3]
	blockHeight = DIV_ROUND_UP(height, blkHeight)
	pitch = 0
	dataAlignment = 512
	if linearTileMode:
		tileMode = 1
	else:
		tileMode = 0
	if depth > 1:
		numDepth = depth
	else:
		numDepth = 1
	linesPerBlockHeight = (1 << int(blockHeightLog2)) * 8
	arrayOffset = 0
	for depthLevel in range(numDepth):
		for arrayLevel in range(arrayCount):
			surfaceSize = 0
			blockHeightShift = 0
			mipOffsets = []
			for mipLevel in range(mipCount):
				width = max(1, width >> mipLevel)
				height = max(1, height >> mipLevel)
				depth = max(1, depth >> mipLevel)
				size = DIV_ROUND_UP(width, blkWidth) * DIV_ROUND_UP(height, blkHeight) * bpp
				if pow2_round_up(DIV_ROUND_UP(height, blkWidth)) < linesPerBlockHeight:
					blockHeightShift += 1
				width__ = DIV_ROUND_UP(width, blkWidth)
				height__ = DIV_ROUND_UP(height, blkHeight)

				# calculate the mip size instead
				alignedData = bytearray(round_up(surfaceSize, dataAlignment) - surfaceSize)
				surfaceSize += len(alignedData)
				mipOffsets.append(surfaceSize)

				# get the first mip offset and current one and the total image size
				msize = int((mipOffsets[0] + len(imageData) - mipOffsets[mipLevel]) / arrayCount)
				
				data_ = subArray(imageData, arrayOffset + mipOffsets[mipLevel], msize)
				try:
					pitch = round_up(width__ * bpp, 64)
					surfaceSize += pitch * round_up(height__, max(1, blockHeight >> blockHeightShift) * 8)
					result = swizzle(width, height, depth, blkWidth, blkHeight, blkDepth, target, bpp, tileMode, max(0, blockHeightLog2 - blockHeightShift), specialPad, data_)

					# the program creates a copy and uses that to remove unneeded data
					# yeah, i'm not doing that
					return result
				except Exception as e:
					raise e
					print(f"Failed to swizzle texture! {e}")
					return False
			arrayOffset += len(imageData) / arrayCount
	return False