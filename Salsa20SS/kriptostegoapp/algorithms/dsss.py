import numpy as np
import soundfile as sf


def prng(key: str, L: int) -> np.ndarray:
    seed = sum((i + 1) * ord(c) for i, c in enumerate(key))
    rng = np.random.default_rng(seed)
    return rng.choice([-1.0, 1.0], size=L).astype(np.float32)


def dsss_encode(
    in_audio: str,
    out_audio: str,
    payload: bytes,
    key: str,
    alpha: float,
    L: int,
    repeat_n: int = 1,
    progress_cb=None,
):
    pn = prng(key, L)
    bits = np.unpackbits(
        np.frombuffer(len(payload).to_bytes(4, "big") + payload, np.uint8)
    ).astype(np.uint8)

    if repeat_n > 1:
        bits = np.repeat(bits, repeat_n)

    total_bits = len(bits)

    with sf.SoundFile(in_audio) as i, sf.SoundFile(
        out_audio,
        mode="w",
        samplerate=i.samplerate,
        channels=i.channels,
        format="FLAC",
    ) as o:

        for idx, bit in enumerate(bits):
            blk = i.read(L, dtype="float32")
            if len(blk) < L:
                blk = np.pad(blk, ((0, L - len(blk)), (0, 0)))
            blk[:, 0] += alpha * (1 if bit else -1) * pn
            o.write(blk)

            if progress_cb:
                progress_cb(int((idx + 1) / total_bits * 100))
        for blk in i.blocks(4096, dtype="float32"):
            o.write(blk)


def dsss_decode(
    stego_audio: str,
    out_file: str,
    key: str,
    L: int,
    repeat_n: int = 1,
    progress_cb=None,
):
    pn = prng(key, L)

    bits = []
    payload_len = None
    total_needed = None

    with sf.SoundFile(stego_audio) as f:
        for idx, blk in enumerate(f.blocks(blocksize=L, dtype="float32")):
            blk = blk[:, 0] if blk.ndim == 2 else blk
            blk = np.pad(blk, (0, max(0, L - len(blk))))

            bits.append(1 if np.dot(blk, pn) > 0 else 0)

            if payload_len is None and len(bits) >= 32 * repeat_n:
                hdr = np.array(bits[: 32 * repeat_n], dtype=np.uint8)
                hdr = hdr[: len(hdr) - (len(hdr) % repeat_n)]
                hdr = (hdr.reshape(-1, repeat_n).sum(axis=1) > (repeat_n // 2))
                payload_len = int.from_bytes(np.packbits(hdr).tobytes(), "big")
                total_needed = (32 + payload_len * 8) * repeat_n

            if payload_len and len(bits) >= total_needed:
                break

            if progress_cb and total_needed:
                progress_cb(int(len(bits) / total_needed * 100))

    payload_bits = np.array(bits[32 * repeat_n:], dtype=np.uint8)
    payload_bits = payload_bits[: len(payload_bits) - (len(payload_bits) % repeat_n)]
    data_bits = (payload_bits.reshape(-1, repeat_n).sum(axis=1) > (repeat_n // 2))

    payload = np.packbits(data_bits).tobytes()[:payload_len]

    with open(out_file, "wb") as f:
        f.write(payload)