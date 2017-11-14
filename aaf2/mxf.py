from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
import sys
import struct
import uuid
from uuid import UUID
from io import BytesIO

from .utils import (read_u8, read_u16be,
                   read_u32be, read_s32be,
                   read_u64be, read_s64be)
from .mobid import MobID
from .model import datadefs

class MXFRef(UUID):
    pass

class MXFRefArray(list):
    pass

def read_uuid_be(f):
    data = f.read(16)
    if data:
        return uuid.UUID(bytes=data)

def read_strongref(f):
    data = f.read(16)
    if data:
        return MXFRef(bytes=data)


def decode_strong_ref_array(data):
    f = BytesIO(data)
    count = read_u32be(f)
    f.read(4)
    refs = MXFRefArray()
    for i in range(count):
        refs.append(read_strongref(f))
    return refs


def decode_utf16be(data):
    size = 0
    data = bytearray(data)
    for i in range(0, len(data), 2):
        if i+1 >= len(data):
            size = i
            break

        if data[i] == 0x00 and data[i+1] == 0x00:
            size = i
            break

    return data[:size].decode('utf-16-be')

def decode_uuid(data):
    return uuid.UUID(bytes=data)

def reverse_uuid(data):
    new = data.hex[16:] + data.hex[:16]
    return UUID(new)

def decode_datadef(data):
    datadef = reverse_uuid(uuid.UUID(bytes=data))
    return datadefs.DataDefs.get(str(datadef), (None, None))[0]

def decode_strongref(data):
    return MXFRef(bytes=data)

def decode_rational(data):
    f = BytesIO(data)
    num = read_u32be(f)
    den = read_u32be(f)

    return "%d/%d" % (num, den)

def decode_video_line_map(data):
    f = BytesIO(data)
    count = read_u32be(f)
    size = read_u32be(f)
    line_map = []
    if size == 4:
        if count > 0:
            line_map.append(read_u32be(f))
        else:
            line_map.append(0)
        if count > 1:
            line_map.append(read_u32be(f))
        else:
            line_map.append(0)
    return line_map

def decode_pixel_layout(data):
    f = BytesIO(data)
    layout = []
    for i in range(8):
        code = read_u8(f)
        depth = read_u8(f)
        if not code:
            break
        layout.append((chr(code), depth))
    return layout

class MXFObject(object):
    def __init__(self):
        self.instance_id = None
        self.data = {}

    def read_tag(self, tag, data):
        if tag == 0x3c0a:
            self.instance_id = decode_uuid(data)

    def read_properties(self, f, length, local_tags):
        for tag, data in iter_tags(f, length):
            self.read_tag(tag, data)
            uid = local_tags.get(tag, None)
            if uid == UUID("a0240060-94eb-75cb-ce2a-ca5051ab11d3"):
                self.data['FrameSampleSize'] = read_u32be(BytesIO(data))
            elif uid == UUID("a0240060-94eb-75cb-ce2a-ca4d51ab11d3"):
                self.data['ResolutionID'] = read_u32be(BytesIO(data))

    def __repr__(self):
        return str(self.data)

class MXFPreface(MXFObject):
    def read_tag(self, tag, data):
        super(MXFPreface, self).read_tag(tag, data)

        if tag == 0x3b09:
            self.data['OperationalPattern'] = decode_uuid(data)
        elif tag == 0x3b03:
            self.data['ContentStorage'] = decode_strongref(data)

class MXFContentStorage(MXFObject):
    def read_tag(self, tag, data):
        super(MXFContentStorage, self).read_tag(tag, data)

        if tag == 0x1902:
            self.data['EssenceContainerData'] = decode_strong_ref_array(data)
        elif tag == 0x1901:
            self.data['Packages'] = decode_strong_ref_array(data)


class MXFPackage(MXFObject):

    def read_tag(self, tag, data):
        super(MXFPackage, self).read_tag(tag, data)

        if tag == 0x4403:
            self.data['Slots'] = decode_strong_ref_array(data)
        elif tag == 0x4401:
            self.data['MobID'] = MobID(bytes_le=data)
        elif tag == 0x4402:
            self.data['Name'] = decode_utf16be(data)
        elif tag == 0x4701:
            self.data['Descriptor'] = decode_strongref(data)

class MXFMaterialPackage(MXFPackage):
    pass

class MXFSourcePackage(MXFPackage):
    pass

class MXFTrack(MXFObject):

    def read_tag(self, tag, data):
        super(MXFTrack, self).read_tag(tag, data)

        if tag == 0x4b02:
            self.data['Origin'] = read_s64be(BytesIO(data))
        elif tag == 0x4b01:
            self.data['EditRate'] = decode_rational(data)
        elif tag == 0x4803:
            self.data['Segment'] = decode_strongref(data)
        elif tag == 0x4804:
            self.data['TrackNumber'] = read_s32be(BytesIO(data))
        elif tag == 0x4801:
            self.data['SlotID'] = read_u32be(BytesIO(data))
        elif tag == 0x4802:
            self.data['Name'] = decode_utf16be(data)

class MXFComponent(MXFObject):
    def read_tag(self, tag, data):
        super(MXFComponent, self).read_tag(tag, data)

        if tag == 0x1001:
            self.data['Components'] = decode_strong_ref_array(data)
        elif tag == 0x1201:
            self.data['StartTime'] = read_u64be(BytesIO(data))
        elif tag == 0x1102:
            self.data['SlotID'] = read_u32be(BytesIO(data))
        elif tag == 0x1101:
            self.data['MobID'] = MobID(bytes_le=data)
        elif tag == 0x0202:
            self.data['Length'] = read_u64be(BytesIO(data))
        elif tag == 0x0201:
            self.data['DataDef'] = decode_datadef(data)
        elif tag == 0x1503:
            self.data['DropFrame'] = read_u8(BytesIO(data)) == 1
        elif tag == 0x1502:
            self.data['FPS'] = read_u16be(BytesIO(data))
        elif tag == 0x1501:
            self.data['Start'] = read_u64be(BytesIO(data))
        elif tag == 0x0501:
            self.data['Choices'] = decode_strong_ref_array(data)
        elif tag == 0x0502:
            self.data['StillFrame'] = decode_strongref(data)

class MXFSequence(MXFComponent):
    pass

class MXFSourceClip(MXFComponent):
    pass

class MXFTimecode(MXFComponent):
    pass

class MXFEssenceGroup(MXFComponent):
    pass

class MXFDescriptor(MXFObject):

    def read_tag(self, tag, data):
        super(MXFDescriptor, self).read_tag(tag, data)
        if tag == 0x3f01:
            self.data['SubDescriptors'] = decode_strong_ref_array(data)
        elif tag == 0x3004:
            self.data['EssenceContainer'] = reverse_uuid(decode_uuid(data))
        elif tag == 0x3006:
            self.data['LinkedTrackID'] = read_u32be(BytesIO(data))
        elif tag == 0x3203:
            self.data['StoredWidth'] = read_u32be(BytesIO(data))
        elif tag == 0x3202:
            self.data['SampledHeight'] = read_u32be(BytesIO(data))
        elif tag == 0x320d:
            self.data['VideoLineMap'] = decode_video_line_map(data)
        elif tag == 0x3211:
            self.data['ImageAlignmentOffset'] = read_u32be(BytesIO(data))
        elif tag == 0x3002:
            self.data['Length'] = read_u32be(BytesIO(data))
        elif tag == 0x3001:
            self.data['SampleRate'] = decode_rational(data)
        elif tag == 0x3d03:
            self.data['AudioSamplingRate'] = decode_rational(data)
        elif tag == 0x3d0a:
            self.data['BlockAlign'] = read_u16be(BytesIO(data))
        elif tag == 0x3d01:
            self.data['QuantizationBits'] = read_u32be(BytesIO(data))
        elif tag == 0x3d07:
            self.data['Channels'] = read_u32be(BytesIO(data))
        elif tag == 0x3d0a:
            self.data['AverageBPS'] = read_u32be(BytesIO(data))
        elif tag == 0x3d02:
            self.data['Locked'] = read_u8(BytesIO(data)) == 1
        elif tag == 0x3301:
            self.data['ComponentWidth'] = read_u32be(BytesIO(data))
        elif tag == 0x320c:
            self.data['FrameLayout'] = read_u8(BytesIO(data))
        elif tag == 0x320e:
            self.data['ImageAspectRatio'] = decode_rational(data)
        elif tag == None:
            self.data['FrameSampleSize'] = None
        elif tag == 0x3d06:
            self.data['SoundCompression'] =  reverse_uuid(decode_uuid(data))
        elif tag == 0x3201:
            self.data['Compression'] = reverse_uuid(decode_uuid(data))
        elif tag == 0x3302:
            self.data['HorizontalSubsampling'] = read_u32be(BytesIO(data))
        elif tag == 0x3308:
            self.data['VerticalSubsampling'] = read_u32be(BytesIO(data))
        elif tag == 0x2f01:
            self.data['Locators'] = decode_strong_ref_array(data)
        elif tag == 0x3401:
            self.data['PixelLayout'] = decode_pixel_layout(data)

class MXFMultipleDescriptor(MXFDescriptor):
    pass

class MXFCDCIDescriptor(MXFDescriptor):
    pass

class MXFRGBADescriptor(MXFDescriptor):
    pass

class MXFSoundDescriptor(MXFDescriptor):
    pass

class MXFPCMDescriptor(MXFDescriptor):
    pass

class MXFImportDescriptor(MXFDescriptor):
    pass

class MXFTapeDescriptor(MXFDescriptor):
    pass


class MXFLocator(MXFObject):
    def read_tag(self, tag, data):
        super(MXFLocator, self).read_tag(tag, data)

        if tag == 0x4001:
            self.data['Path'] =  decode_utf16be(data)

class MXFNetworkLocator(MXFLocator):
    pass

class MXFEssenceData(MXFObject):
    def read_tag(self, tag, data):
        super(MXFEssenceData, self).read_tag(tag, data)

        if tag == 0x2701:
            self.data['MobID'] = MobID(bytes_le=data)

read_table = {
UUID("060e2b34-0253-0101-0d01-010101012f00") : MXFPreface,
UUID("060e2b34-0253-0101-0d01-010101011800") : MXFContentStorage,
UUID("060e2b34-0253-0101-0d01-010101013600") : MXFMaterialPackage,
UUID("060e2b34-0253-0101-0d01-010101013700") : MXFSourcePackage,
UUID("060e2b34-0253-0101-0d01-010101013b00") : MXFTrack,
UUID("060e2b34-0253-0101-0d01-010101010f00") : MXFSequence,
UUID("060e2b34-0253-0101-0d01-010101011100") : MXFSourceClip,
UUID("060e2b34-0253-0101-0d01-010101011400") : MXFTimecode,
UUID("060e2b34-0253-0101-0d01-010101014400") : MXFMultipleDescriptor,
UUID("060e2b34-0253-0101-0d01-010101012800") : MXFCDCIDescriptor,
UUID("060e2b34-0253-0101-0d01-010101012900") : MXFRGBADescriptor,
UUID("060e2b34-0253-0101-0d01-010101014200") : MXFSoundDescriptor,
UUID("060e2b34-0253-0101-0d01-010101014800") : MXFPCMDescriptor,
UUID("060e2b34-0253-0101-0d01-010101014a00") : MXFImportDescriptor,
UUID("060e2b34-0253-0101-0d01-010101012e00") : MXFTapeDescriptor,
UUID("060e2b34-0253-0101-0d01-010101013200") : MXFNetworkLocator,
UUID("060e2b34-0253-0101-0d01-010101010500") : MXFEssenceGroup,
UUID("060e2b34-0253-0101-0d01-010101012300") : MXFEssenceData,
}

def ber_length(f):

    length = read_u8(f)

    bytes_read = 1
    if length > 127:
        bytes_read += length - 128
        length = int(f.read(length - 128).encode('hex'), 16)
    return length


def iter_kl(f):
    pos = f.tell()
    while True:
        # read the key
        f.seek(pos)
        key = read_uuid_be(f)
        if not key:
            break
        # read the ber_length
        length = ber_length(f)

        pos = f.tell() + length
        yield key, length

def iter_tags(f, length):
    while length > 0:
        tag = read_u16be(f)
        size = read_u16be(f)
        # print("   tag 0x%04x %d" % (tag, size))
        if size:
            yield tag, f.read(size)
        length -= 4 + size

def uuid_to_str_list(v, sep=','):
    return sep.join('0x%02x' % i  for i in bytearray(v.bytes))

class MXFFile(object):

    def __init__(self, path):
        self.objects = {}
        self.local_tags = {}
        self.preface = None
        self.header_operation_pattern = None
        with open(path, 'rb') as f:

            local_tags = {}
            for key, length in iter_kl(f):

                if key == UUID("060e2b34-0205-0101-0d01-020101050100"):
                    self.local_tags = self.read_primer(f, length)

                if key == UUID("060e2b34-0205-0101-0d01-020101020400"):
                    self.read_header(f, length)

                obj = self.read_object(f, key, length)
                if obj:
                    self.objects[obj.instance_id] = obj

                if isinstance(obj, MXFPreface):
                    self.preface = obj

    def read_header(self, f, length):
        major_version = read_u16be(f)
        minor_version = read_u16be(f)
        kag_size = read_u32be(f)
        this_partion = read_u64be(f)
        prev_partion = read_u64be(f)
        footer_partion = read_u64be(f)
        header_byte_count = read_u64be(f)
        index_byte_count = read_u64be(f)
        index_sid = read_u32be(f)
        body_offset = read_u64be(f)
        body_sid = read_u32be(f)
        self.header_operation_pattern = read_uuid_be(f)

    def read_primer(self, f, length):

        item_num = read_u32be(f)
        item_len = read_u32be(f)
        if item_len != 18:
            return
        if item_num > 65536:
            return

        tags = {}
        for i in range(item_num):
            tag = read_u16be(f)
            uid = read_uuid_be(f)
            # print("%04x" % tag, ':', uid)
            tags[tag] = uid

        return tags

    def read_object(self, f, key, length):

        b = bytearray(key.bytes)
        if not b[5] == 0x53:
            return

        obj_class = read_table.get(key, None)
        if obj_class:

            obj = obj_class()

            obj.read_properties(f, length, self.local_tags)
            return obj
        else:
            for tag, data in iter_tags(f, length):
                pass

    def dump_flat(self):
        for key,value in self.objects.items():
            print(value.__class__.__name__, key)
            for p, v in value.data.items():
                print("  ",p, v)

    def dump(self, obj=None, space=""):
        if obj is None:
            obj = self.preface

        print (space, obj.__class__.__name__, obj.instance_id)

        space += " "
        for key, value in sorted(obj.data.items()):
            if isinstance(value, MXFRef):
                c = self.objects.get(value, None)
                if c:
                    self.dump(c, space)
                else:
                    print(space, None)

            elif isinstance(value, MXFRefArray):
                print (space, key)
                for item in value:
                    c = self.objects.get(item, None)
                    if c:
                        self.dump(c, space + " ")
                    else:
                        print(space, None)
            else:
                print (space, key, value)

    @property
    def operation_pattern(self):

        if self.header_operation_pattern:
            op = self.header_operation_pattern
        else:
            op = self.preface.data.get('OperationalPattern', None)

        if not op:
            return

        op = bytearray(op.bytes)

        prefix1 = bytearray([0x06, 0x0e, 0x2b, 0x34, 0x04, 0x01, 0x01, 0x01, 0x0d, 0x01, 0x02, 0x01])
        prefix2 = bytearray([0x06, 0x0e, 0x2b, 0x34, 0x04, 0x01, 0x01, 0x02, 0x0d, 0x01, 0x02, 0x01])
        prefix3 = bytearray([0x06, 0x0e, 0x2b, 0x34, 0x04, 0x01, 0x01, 0x03, 0x0d, 0x01, 0x02, 0x01])

        prefix_valid = False
        for prefix in (prefix1, prefix2, prefix3):
            if op[:len(prefix)] == prefix:
                prefix_valid = True
                break

        if not prefix_valid:
            return

        complexity = op[12]

        if complexity >= 1 and complexity <= 3:
            package_complexity = op[13]
            letter = {1:'a', 2:'b', 3:'c'}.get(package_complexity, None)
            if letter:
                return 'OP%d%s' % (complexity, letter)

        elif complexity >= 0x10 and complexity <= 0x7f:
            if complexity == 0x10:
                return 'OPAtom'