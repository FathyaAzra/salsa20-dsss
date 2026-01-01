import numpy as np
import soundfile as sf
from django.core.cache import cache

def prng(key: str, L: int) -> np.ndarray:
    seed = sum((i + 1) * ord(c) for i, c in enumerate(key))
    rng = np.random.default_rng(seed)
    return rng.choice([-1.0, 1.0], size=L).astype(np.float32)


def bytes_to_bits(data: bytes, repeat: int = 1) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    return np.repeat(bits, repeat).astype(np.uint8)


def bits_to_bytes(bits: np.ndarray) -> bytes:
    n = len(bits) - (len(bits) % 8)
    return np.packbits(bits[:n]).tobytes()


def majority_vote(bits: np.ndarray, repeat: int) -> np.ndarray:
    bits = bits.astype(np.uint8)
    return np.array(
        [
            1 if np.sum(bits[i:i + repeat]) > repeat // 2 else 0
            for i in range(0, len(bits), repeat)
        ],
        dtype=np.uint8,
    )

def file_to_bytes(path: str) -> bytes:
    return np.fromfile(path, dtype=np.uint8).tobytes()


def dsss_encode(
    in_audio: str,
    out_audio: str,
    payload_bytes: bytes,
    alpha: float,
    L: int,
    key: str,
    repeat: int,
):
    pn = prng(key, L)

    header = len(payload_bytes).to_bytes(4, "big") + b"\x01"
    payload = header + payload_bytes
    payload_bits = bytes_to_bits(payload, repeat)

    with sf.SoundFile(in_audio) as infile:
        channels = infile.channels
        total_samples = infile.frames
        total_blocks = int(np.ceil(total_samples / L))

    required_blocks = len(payload_bits)

    print(f"Payload bytes : {len(payload)}")
    print(f"Required blocks : {required_blocks}")
    print(f"Available blocks : {total_blocks}")

    with sf.SoundFile(in_audio) as infile, sf.SoundFile(
        out_audio,
        mode="w",
        samplerate=infile.samplerate,
        channels=infile.channels,
        format="FLAC",
    ) as outfile:
        for bit in payload_bits:
            block = infile.read(L, dtype="float32")

            if len(block) < L:
                noise = np.random.normal(
                    0.0, 1e-6, size=(L - len(block), channels)
                ).astype(np.float32)
                block = np.vstack((block, noise))

            symbol = 1.0 if bit else -1.0
            block[:, 0] += alpha * symbol * pn

            outfile.write(block)

        while True:
            rest = infile.read(4096, dtype="float32")
            if len(rest) == 0:
                break
            outfile.write(rest)


def dsss_decode(
    stego_audio: str,
    out_file: str,
    L: int,
    key: str,
    repeat: int,
):
    pn = prng(key, L)

    HEADER_BYTES = 5
    HEADER_BITS = HEADER_BYTES * 8
    HEADER_BITS_REP = HEADER_BITS * repeat

    bits = []
    payload_bits_needed = None
    payload_len = 0

    with sf.SoundFile(stego_audio) as infile:
        for block in infile.blocks(blocksize=L, dtype="float32"):

            if block.ndim == 2:
                block = block[:, 0]

            if len(block) < L:
                block = np.pad(block, (0, L - len(block)))

            corr = np.dot(block, pn) / L
            bits.append(1 if corr > 0 else 0)

            if payload_bits_needed is None and len(bits) == HEADER_BITS_REP:
                header_bits = majority_vote(np.array(bits), repeat)
                header = bits_to_bytes(header_bits)

                payload_len = int.from_bytes(header[:4], "big")
                payload_bits_needed = payload_len * 8 * repeat

                if payload_len <= 0:
                    raise ValueError("Invalid payload length")

            if (
                payload_bits_needed is not None
                and len(bits) >= HEADER_BITS_REP + payload_bits_needed
            ):
                break

    payload_bits = np.array(
        bits[HEADER_BITS_REP: HEADER_BITS_REP + payload_bits_needed]
    )
    payload = bits_to_bytes(majority_vote(payload_bits, repeat))

    with open(out_file, "wb") as f:
        f.write(payload)

    return payload_len, len(payload)