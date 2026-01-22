import numpy as np
import soundfile as sf


def prng(key: str, L: int) -> np.ndarray:
  seed = sum((i + 1) * ord(c) for i, c in enumerate(key))
  rng = np.random.default_rng(seed)
  return rng.choice([-1.0, 1.0], size=L).astype(np.float32)


def repeat(bits: np.ndarray, r: int, decode=False) -> np.ndarray:
    if r <= 1:
        return bits.astype(np.uint8)
    bits = bits.astype(np.uint8)
    if not decode:
        return np.repeat(bits, r)
    bits = bits[: len(bits) - (len(bits) % r)]
    return (bits.reshape(-1, r).sum(axis=1) > (r // 2)).astype(np.uint8)


def dsss_encode(
    in_audio: str,
    out_audio: str,
    payload: bytes,
    key: str,
    alpha: float,
    L: int,
    repeat_n: int = 1,
):
    pn = prng(key, L)

    bits = np.unpackbits(np.frombuffer(len(payload).to_bytes(4, "big") + payload, np.uint8))
    if repeat_n > 1:
        bits = np.repeat(bits.astype(np.uint8), repeat_n)

    with sf.SoundFile(in_audio) as i, sf.SoundFile(
        out_audio, "w",
        samplerate=i.samplerate,
        channels=i.channels,
        format="FLAC",
    ) as o:

        for b in bits:
            blk = i.read(L, dtype="float32")
            if len(blk) < L:
                blk = np.pad(blk, ((0, L - len(blk)), (0, 0)))

            blk[:, 0] += alpha * (1 if b else -1) * pn
            o.write(blk)

        for blk in i.blocks(4096, dtype="float32"):
            o.write(blk)

    print(f"Embedded payload bytes  : {len(payload)}")
    print()

def dsss_decode(
    stego_audio: str,
    out_file: str,
    key: str,
    L: int,
    repeat_n: int = 1,
) -> bytes:
    pn = prng(key, L)

    bits = []
    payload_len = None

    with sf.SoundFile(stego_audio) as f:
        for blk in f.blocks(blocksize=L, dtype="float32"):
            blk = blk[:, 0] if blk.ndim == 2 else blk
            blk = np.pad(blk, (0, max(0, L - len(blk))))

            bits.append(1 if np.dot(blk, pn) > 0 else 0)

            if payload_len is None and len(bits) >= 32 * repeat_n:
                hdr_bits = np.array(bits[: 32 * repeat_n], dtype=np.uint8)
                hdr_bits = hdr_bits[: len(hdr_bits) - (len(hdr_bits) % repeat_n)]
                hdr = (hdr_bits.reshape(-1, repeat_n).sum(axis=1) > (repeat_n // 2)).astype(np.uint8)
                payload_len = int.from_bytes(np.packbits(hdr).tobytes(), "big")

            if payload_len is not None:
                need = (32 + payload_len * 8) * repeat_n
                if len(bits) >= need:
                    break

    payload_bits = np.array(bits[32 * repeat_n :], dtype=np.uint8)
    payload_bits = payload_bits[: len(payload_bits) - (len(payload_bits) % repeat_n)]
    data_bits = (payload_bits.reshape(-1, repeat_n).sum(axis=1)> (repeat_n // 2)).astype(np.uint8)

    payload = np.packbits(data_bits).tobytes()[:payload_len]

    with open(out_file, "wb") as f:
        f.write(payload)

    print(
        f"Recovery ratio : {len(payload) / payload_len:.2%}"
        if payload_len > 0 else "N/A"
    )