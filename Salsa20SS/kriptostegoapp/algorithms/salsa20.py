import struct


def rotate(v, c):
    return ((v << c) & 0xffffffff) | (v >> (32 - c))

def quarterround(y0, y1, y2, y3):
    y1 ^= rotate((y0 + y3) & 0xffffffff, 7)
    y2 ^= rotate((y1 + y0) & 0xffffffff, 9)
    y3 ^= rotate((y2 + y1) & 0xffffffff, 13)
    y0 ^= rotate((y3 + y2) & 0xffffffff, 18)
    return y0, y1, y2, y3

def rowround(y):
    z = list(y)
    z[0], z[1], z[2], z[3] = quarterround(z[0], z[1], z[2], z[3])
    z[5], z[6], z[7], z[4] = quarterround(z[5], z[6], z[7], z[4])
    z[10], z[11], z[8], z[9] = quarterround(z[10], z[11], z[8], z[9])
    z[15], z[12], z[13], z[14] = quarterround(z[15], z[12], z[13], z[14])
    return z

def columnround(x):
    z = list(x)
    z[0], z[4], z[8], z[12] = quarterround(z[0], z[4], z[8], z[12])
    z[5], z[9], z[13], z[1] = quarterround(z[5], z[9], z[13], z[1])
    z[10], z[14], z[2], z[6] = quarterround(z[10], z[14], z[2], z[6])
    z[15], z[3], z[7], z[11] = quarterround(z[15], z[3], z[7], z[11])
    return z

def doubleround(x):
    return rowround(columnround(x))

def littleendian(b):
    return struct.unpack('<I', b)[0]

def salsa20_hash(seq):
    x = [littleendian(seq[i:i+4]) for i in range(0, 64, 4)]
    z = x[:]
    for j in range(10):
        z = doubleround(z)
    return [(z[k] + x[k]) & 0xffffffff for k in range(16)]

def salsa20_block(key, nonce, counter):
    const = b"expand 32-byte k"
    seq = (const[0:4] + key[0:16] + const[4:8] + nonce + counter.to_bytes(8, 'little') + const[8:12] + key[16:32] + const[12:16])
    output = salsa20_hash(seq)
    return b"".join(struct.pack('<I', o) for o in output)

def salsa20_stream(key, nonce, length):
    keystream = b""
    counter = 0
    while len(keystream) < length:
        keystream += salsa20_block(key, nonce, counter)
        counter += 1
    return keystream[:length]

def encrypt_decrypt(data, key, nonce):
    ks = salsa20_stream(key, nonce, len(data))
    return bytes([d ^ k for d, k in zip(data, ks)])