"""Patch the captured RK FIT image, preserving kernel and partition size.

FDT is parsed by tokens and rebuilt with the original total size. All FIT image
SHA256 hashes are checked before and after; no raw string replacement is used.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

def align4(n):
    return (n + 3) & ~3

class Fdt:
    def __init__(self, data):
        self.h = list(struct.unpack_from('>10I', data))
        assert self.h[0] == 0xd00dfeed
        self.data = data[:self.h[1]]
        self.strings = self.data[self.h[3]:self.h[3]+self.h[8]]
        self.tokens = []
        stack = []
        i = self.h[2]
        while i < self.h[2] + self.h[9]:
            tag = struct.unpack_from('>I', self.data, i)[0]
            i += 4
            if tag == 1:
                end = self.data.index(0, i)
                name = self.data[i:end].decode()
                stack.append(name)
                self.tokens.append([tag, '/'.join(stack), name])
                i = align4(end+1)
            elif tag == 2:
                self.tokens.append([tag, '/'.join(stack)])
                stack.pop()
            elif tag == 3:
                length, nameoff = struct.unpack_from('>II', self.data, i)
                i += 8
                end = self.strings.index(0, nameoff)
                name = self.strings[nameoff:end].decode()
                self.tokens.append([tag, '/'.join(stack), name, self.data[i:i+length]])
                i = align4(i+length)
            elif tag in (4, 9):
                self.tokens.append([tag])
                if tag == 9:
                    break
            else:
                raise ValueError(f'Invalid FDT token {tag}')

    def get(self, path, name):
        for token in self.tokens:
            if token[0] == 3 and token[1:3] == [path, name]:
                return token[3]
        raise KeyError((path, name))

    def set(self, path, name, value):
        for token in self.tokens:
            if token[0] == 3 and token[1:3] == [path, name]:
                token[3] = value
                return
        for i, token in enumerate(self.tokens):
            if token[0] == 1 and token[1] == path:
                self.tokens.insert(i+1, [3, path, name, value])
                return
        raise KeyError(path)

    def delete(self, path, name):
        self.tokens = [t for t in self.tokens if not (t[0] == 3 and t[1:3] == [path, name])]

    def props(self):
        return {(t[1], t[2]): t[3] for t in self.tokens if t[0] == 3}

    def encode(self):
        strings = bytearray(self.strings)
        payload = bytearray()
        for token in self.tokens:
            tag = token[0]
            payload += struct.pack('>I', tag)
            if tag == 1:
                value = token[2].encode() + b'\0'
                payload += value + bytes(align4(len(value))-len(value))
            elif tag == 3:
                name, value = token[2], token[3]
                needle = name.encode()+b'\0'
                off = strings.find(needle)
                if off < 0:
                    off = len(strings)
                    strings += needle
                payload += struct.pack('>II', len(value), off)
                payload += value + bytes(align4(len(value))-len(value))
        header = self.h.copy()
        header[3] = header[2] + len(payload)
        header[8], header[9] = len(strings), len(payload)
        used = header[3] + len(strings)
        if used > header[1]:
            raise ValueError(f'FDT requires {used} bytes; original capacity {header[1]}')
        prefix = struct.pack('>10I', *header) + self.data[40:header[2]]
        result = prefix + payload + strings + bytes(header[1]-used)
        assert Fdt(result).props() == self.props()
        return result

def images(fit):
    for token in fit.tokens:
        if token[0] == 1 and token[1].startswith('/images/') and token[1].count('/') == 2:
            path = token[1]
            yield path, struct.unpack('>I', fit.get(path, 'data-position'))[0], struct.unpack('>I', fit.get(path, 'data-size'))[0]

def verify_fit(blob):
    fit = Fdt(blob)
    for path, offset, size in images(fit):
        if size <= 0 or offset < fit.h[1] or offset + size > len(blob):
            raise ValueError(f'FIT payload outside image bounds: {path}')
        expected = fit.get(path+'/hash', 'value')
        assert fit.get(path+'/hash', 'algo') == b'sha256\0'
        assert hashlib.sha256(blob[offset:offset+size]).digest() == expected, f'FIT hash mismatch: {path}'
    return fit

def patch(source, dest, cma_mb=None):
    if source.resolve() == dest.resolve():
        raise ValueError('Source backup and patched output must be different files')
    before = source.read_bytes()
    fit = verify_fit(before)
    signature_values = [t[1] for t in fit.tokens
                        if t[0] == 3 and '/signature' in t[1]
                        and t[2] == 'value' and t[3]]
    if signature_values:
        raise ValueError('Signed FIT requires a valid signing workflow; '
                         f'refusing hash-only patch: {signature_values}')
    fdtpos = struct.unpack('>I', fit.get('/images/fdt', 'data-position'))[0]
    fdtsize = struct.unpack('>I', fit.get('/images/fdt', 'data-size'))[0]
    dtbytes = before[fdtpos:fdtpos+fdtsize]
    dt = Fdt(dtbytes)
    oldprops = dt.props()
    usb, pci = '/usb@23400000', '/pcie@2a210000'
    assert dt.get(usb, 'status') == b'okay\0'
    assert len(dt.get(usb, 'phys')) == 12
    usbphys = dt.get(usb, 'phys')
    assert usbphys[4:8] == dt.get(pci, 'phys')[:4]
    # RK3576 has a bus-level exclusion, not just a shared SuperSpeed PHY.
    # USB OTG1 (including USB2) cannot coexist with PCIe1. See Rockchip
    # RK3576 USB Developer Guide V1.1.0, pages 5-6 (PDF indices 4-5).
    # Board Wi-Fi is behind OTG1, so PCIe operation requires Ethernet or
    # another independent connection. Never promise onboard Wi-Fi here.
    dt.set(usb, 'status', b'disabled\0')
    # Inactive-controller flags free structure space for reset-gpios without
    # shifting the kernel/resource FIT payloads or changing partition size.
    for prop in ('snps,dis-u1-entry-quirk', 'snps,dis-u2-entry-quirk',
                 'snps,parkmode-disable-ss-quirk'):
        dt.delete(usb, prop)
    dt.set(pci, 'status', b'okay\0')
    gpio1 = dt.get('/aliases', 'gpio1').rstrip(b'\0').decode()
    gpiohandle = dt.get(gpio1, 'phandle')
    dt.set(pci, 'reset-gpios', gpiohandle + struct.pack('>II', 16, 0))
    if cma_mb is not None:
        assert cma_mb in (64, 96, 128)
        bootargs = dt.get('/chosen', 'bootargs').rstrip(b'\0')
        assert b'cma=' not in bootargs
        dt.set('/chosen', 'bootargs', bootargs + f' cma={cma_mb}M'.encode() + b'\0')
    newdt = dt.encode()
    assert len(newdt) == len(dtbytes)
    output = bytearray(before)
    offsets = []
    at = 0
    while True:
        at = before.find(dtbytes, at)
        if at < 0:
            break
        output[at:at+len(newdt)] = newdt
        offsets.append(at)
        at += len(dtbytes)
    assert offsets and fdtpos in offsets
    resource_hashes = []
    for path, offset, size in images(fit):
        if path != '/images/resource':
            continue
        resource = before[offset:offset+size]
        assert resource[:4] == b'RSCE' and resource[8:11] == b'\x01\x01\x01'
        count = struct.unpack_from('<I', resource, 12)[0]
        for index in range(count):
            entry = 512 + index*512
            assert resource[entry:entry+4] == b'ENTR'
            hash_size, file_blocks, file_size = struct.unpack_from('<III', resource, entry+256)
            assert hash_size in (20, 32)
            start = offset + file_blocks*512
            oldfile = before[start:start+file_size]
            digest = hashlib.sha1 if hash_size == 20 else hashlib.sha256
            assert digest(oldfile).digest() == resource[entry+224:entry+224+hash_size]
            newhash = digest(output[start:start+file_size]).digest()
            output[offset+entry+224:offset+entry+224+hash_size] = newhash
            resource_hashes.append({'path': resource[entry+4:entry+224].split(b'\0')[0].decode(),
                                    'verified': True, 'updated': newhash != digest(oldfile).digest()})
    for path, offset, size in images(fit):
        fit.set(path+'/hash', 'value', hashlib.sha256(output[offset:offset+size]).digest())
    newfit = fit.encode()
    output[:len(newfit)] = newfit
    verify_fit(output)
    assert len(output) == len(before)
    kernelpos = struct.unpack('>I', fit.get('/images/kernel', 'data-position'))[0]
    kernelsize = struct.unpack('>I', fit.get('/images/kernel', 'data-size'))[0]
    assert output[kernelpos:kernelpos+kernelsize] == before[kernelpos:kernelpos+kernelsize]
    dest.write_bytes(output)
    newprops = dt.props()
    differences = [{'node': k[0], 'property': k[1],
                    'before_present': k in oldprops, 'after_present': k in newprops,
                    'before': oldprops.get(k,b'').hex(), 'after': newprops.get(k,b'').hex()}
                   for k in sorted(set(oldprops)|set(newprops)) if oldprops.get(k)!=newprops.get(k)]
    report = {'source_sha256': hashlib.sha256(before).hexdigest(), 'fixed_sha256': hashlib.sha256(output).hexdigest(),
              'dtb_offsets': offsets, 'changes': differences, 'resource_hashes': resource_hashes,
              'fit_hashes_verified': True, 'signature_values_present': False,
              'kernel_unchanged': True}
    dest.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('dest', type=Path)
    parser.add_argument('--cma-mb', type=int, choices=(64, 96, 128))
    args = parser.parse_args()
    patch(args.source, args.dest, args.cma_mb)
