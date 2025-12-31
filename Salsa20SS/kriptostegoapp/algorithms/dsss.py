import numpy as np
import soundfile as sf
from django.core.cache import cache


def dsss_enc_split(signal: np.ndarray, secret_bits: list[int], password: str = "secret", L_min: int = 8 * 1024, alpha: float = 0.005, prefix: str = "stego", samplerate: int = 44100):

    samples, _ = signal.shape
    total_bits = len(secret_bits)

    L2 = samples // total_bits if total_bits > 0 else 0
    L = max(L_min, L2)

    nframe = samples // L
    capacity_bits = nframe - (nframe % 8)

    chunks = [secret_bits[i:i + capacity_bits] for i in range(0, total_bits, capacity_bits)]
    spreading_seq = prng(password, L)

    outputs = []
    total = len(chunks)

    for idx, chunk in enumerate(chunks):
        cache.set("encode_progress", int((idx + 1) / total * 100))

        stego = embed_bits(signal, chunk, spreading_seq, alpha, L)
        filename = f"{prefix}_{idx + 1:04d}.wav"
        sf.write(filename, stego, samplerate)
        outputs.append(filename)

    cache.set("encode_progress", 100)
    return outputs


def dsss_dec_split(files: list, password: str = "secret", L_min: int = 8 * 1024) -> bytes:
    bitstream = ""

    for path in files:
        signal, _ = sf.read(path)
        samples = signal.shape[0]

        L = L_min
        nframe = samples // L
        N = nframe - (nframe % 8)

        xsig = np.reshape(signal[:N * L, 0], (L, N), order="F")
        spreading_seq = prng(password, L)

        corr = np.sum(xsig * spreading_seq[:, None], axis=0) / L
        bitstream += ''.join('1' if c >= 0 else '0' for c in corr)

    return bits_to_bytes(bitstream)


def bytes_to_bits(data: bytes) -> list[int]:
    return [int(bit) for byte in data for bit in format(byte, "08b")]


def bits_to_bytes(bitstream: str) -> bytes:
    return bytes(int(bitstream[i:i + 8], 2)
        for i in range(0, len(bitstream), 8))


def embed_bits(signal: np.ndarray, bits: list[int], spreading_seq, alpha: float, L: int):
    stego = signal.copy()
    samples = signal.shape[0]

    for i, bit in enumerate(bits):
        start = i * L
        end = start + L
        if end > samples:
            break
        chip = spreading_seq if bit == 1 else -spreading_seq
        stego[start:end, 0] += alpha * chip

    return stego


def prng(password: str, L: int):
    seed = sum(ord(ch) * i for i, ch in enumerate(password, start=1))
    rng = np.random.RandomState(seed)
    return np.where(rng.rand(L) > 0.5, 1, -1)
