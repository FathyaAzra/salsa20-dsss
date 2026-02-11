import os, json, time, math, tempfile
import numpy as np
from PIL import Image
import soundfile as sf
from skimage.metrics import structural_similarity as ssim

from django.shortcuts import render
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

from .algorithms.salsa20 import encrypt_decrypt
from .algorithms.dsss import dsss_encode, dsss_decode

ALPHA = 0.005
L = 1024
REPEAT_N = 1


def home(request):
    return render(request, "home.html")


def encrypt_file(request):
    context = {
        "upload_info": None
    }

    if request.method == "POST":
        uploaded = request.FILES["file"]
        raw = uploaded.read()
        uploaded.seek(0)

        original_name = uploaded.name
        original_size = uploaded.size
        name, ext = os.path.splitext(original_name)

        key = os.urandom(32)
        nonce = os.urandom(8)

        metadata_data = {
            "original_name": name,
            "extension": ext,
            "original_size": original_size,
            "nonce": nonce.hex()
        }

        start = time.time()
        cipher = encrypt_decrypt(raw, key, nonce)
        exec_time = time.time() - start

        cipher_size = len(cipher)
        ts = int(time.time())

        cipher_filename = f"{name}_{ts}.bin"
        key_filename = f"{name}_{ts}.key"
        meta_filename = f"{name}_{ts}.json"

        cipher_path = f"encrypted/{cipher_filename}"
        key_path = f"encrypted/{key_filename}"
        meta_path = f"encrypted/{meta_filename}"

        default_storage.save(cipher_path, ContentFile(cipher))
        default_storage.save(key_path, ContentFile(key))
        default_storage.save(
            meta_path,
            ContentFile(json.dumps(metadata_data, indent=2))
        )

        context.update({
            "upload_info": [
                {"label": "original", "name": original_name, "size": original_size},
                {"label": "encrypted", "name": cipher_filename, "size": cipher_size},
                {"label": "key", "name": key_filename, "size": len(key)},
                {"label": "metadata", "name": meta_filename, "size": len(json.dumps(metadata_data))}
            ],
            "encrypted": settings.MEDIA_URL + cipher_path,
            "key": settings.MEDIA_URL + key_path,
            "metadata": settings.MEDIA_URL + meta_path,
            "original_filename": original_name,
            "original_filesize": original_size,
            "cipher_filename": cipher_filename,
            "cipher_filesize": cipher_size,
            "key_filesize": len(key),
            "meta_filesize": len(json.dumps(metadata_data)),
            "metrics": {
                "execution_time": exec_time,
            }
        })


    return render(request, "encrypt_salsa20.html", context)

def decrypt_file(request):
    context = {}

    if request.method == "POST":
        cipher_file = request.FILES.get("cipher")
        key_file = request.FILES.get("key")
        meta_file = request.FILES.get("metadata")

        cipher_bytes = cipher_file.read()
        key_bytes = key_file.read()
        metadata = json.loads(meta_file.read())

        context.update({
            "upload_info": [
                {"label": "Cipher", "name": cipher_file.name, "size": cipher_file.size},
                {"label": "Key", "name": key_file.name, "size": key_file.size},
                {"label": "Metadata", "name": meta_file.name, "size": meta_file.size},
            ]
        })

        start = time.time()
        nonce = bytes.fromhex(metadata["nonce"])
        plain = encrypt_decrypt(cipher_bytes, key_bytes, nonce)
        exec_time = time.time() - start

        recovered_name = metadata["original_name"] + metadata["extension"]
        recovered_path = f"decrypted/{recovered_name}"
        default_storage.save(recovered_path, ContentFile(plain))

        context.update({
            "recovered": settings.MEDIA_URL + recovered_path,

            "cipher_filename": cipher_file.name,
            "cipher_filesize": len(cipher_bytes),

            "recovered_filename": recovered_name,
            "recovered_filesize": len(plain),

            "metrics": {
                "execution_time": exec_time,
                "input_size": len(cipher_bytes),
                "output_size": len(plain),
            }
        })

    return render(request, "decrypt_salsa20.html", context)


def stegano_encode(request):
    context = {}

    if request.method != "POST":
        return render(request, "encode_ss.html", context)

    audio_file = request.FILES.get("audio_file")
    secret_file = request.FILES.get("secret_file")
    password = request.POST.get("password") or "secret"

    if not audio_file or not secret_file:
        context["error"] = "Audio dan file rahasia wajib diunggah"
        return render(request, "encode_ss.html", context)

    context["upload_info"] = [
        {
            "label": "cipher",
            "name": secret_file.name,
            "size": secret_file.size,
        },
        {
            "label": "audio",
            "name": audio_file.name,
            "size": audio_file.size,
        },
    ]

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
        tmp_audio.write(audio_file.read())
        in_audio_path = tmp_audio.name

    payload = secret_file.read()
    out_audio_path = in_audio_path.replace(".wav", "_stego.flac")

    with sf.SoundFile(in_audio_path) as audio:
        samplerate = audio.samplerate
        channels = audio.channels
        frames = len(audio)

    capacity = frames // L
    required_capacity = (len(payload) * 8 + 32) * REPEAT_N
    padding = max(0, required_capacity - capacity)

    start_time = time.time()
    dsss_encode(
        in_audio=in_audio_path,
        out_audio=out_audio_path,
        payload=payload,
        key=password,
        alpha=ALPHA,
        L=L,
        repeat_n=REPEAT_N,
    )
    execution_time = time.time() - start_time

    audio_size = os.path.getsize(in_audio_path)
    stego_size = os.path.getsize(out_audio_path)

    stego_filename = f"encoded_{int(time.time())}.flac"
    stego_path = f"stego/{stego_filename}"

    with open(out_audio_path, "rb") as f:
        default_storage.save(stego_path, ContentFile(f.read()))

    context.update({
        "file": settings.MEDIA_URL + stego_path,

        "message_name": secret_file.name,
        "message_size": len(payload),

        "audio_name": audio_file.name,
        "audio_size": audio_size,

        "stego_name": stego_filename,
        "stego_size": stego_size,

        "samplerate": samplerate,
        "channel": channels,

        "capacity": capacity,
        "required_capacity": required_capacity,
        "padding": padding,

        "L": L,
        "repeat_n": REPEAT_N,
        "alpha": ALPHA,

        "execution_time": execution_time,
    })

    for path in (in_audio_path, out_audio_path):
        if os.path.exists(path):
            os.remove(path)

    return render(request, "encode_ss.html", context)

def stegano_decode(request):
    context = {}

    if request.method != "POST":
        return render(request, "decode_ss.html", context)

    stego_file = request.FILES.get("audio_file")
    password = request.POST.get("password") or "secret"


    if not stego_file:
        context["error"] = "File audio stego wajib diunggah"
        return render(request, "decode_ss.html", context)

    ext = os.path.splitext(stego_file.name)[1].lower()
    if ext not in [".flac"]:
        context["error"] = "Format harus FLAC"
        return render(request, "decode_ss.html", context)

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(stego_file.read())
        stego_path = tmp.name

    out_path = stego_path + "_decoded.bin"

    start_time = time.time()
    dsss_decode(
        stego_audio=stego_path,
        out_file=out_path,
        key=password,
        L=L,
        repeat_n=REPEAT_N,
    )
    execution_time = time.time() - start_time

    dst = f"stego/recovered_{int(time.time())}.bin"
    with open(out_path, "rb") as f:
        default_storage.save(dst, ContentFile(f.read()))

    recovered_size = os.path.getsize(out_path)

    context.update({
        "file": settings.MEDIA_URL + dst,

        "stego_name": stego_file.name,
        "stego_size": stego_file.size,

        "recovered_name": os.path.basename(dst),
        "recovered_size": recovered_size,

        "L": L,
        "repeat_n": REPEAT_N,
        "execution_time": execution_time,
    })

    for path in (stego_path, out_path):
        if os.path.exists(path):
            os.remove(path)

    return render(request, "decode_ss.html", context)


def pengujian_file(request):
    context = {}

    if request.method != "POST":
        return render(request, "pengujian.html", context)

    mode = request.POST.get("mode")

    if mode == "audio":
        audio_orig = request.FILES.get("audio_original")
        audio_stego = request.FILES.get("audio_stego")

        if not audio_orig or not audio_stego:
            context["error"] = "Audio original dan stego wajib diunggah"
            return render(request, "pengujian.html", context)

        context["upload_info"] = [
            {"label": "Audio Original", "name": audio_orig.name, "size": audio_orig.size},
            {"label": "Audio Stego", "name": audio_stego.name, "size": audio_stego.size},
        ]

        BLOCK_SIZE = 44100
        MAX_SECONDS = 60
        max_blocks = MAX_SECONDS

        mse_sum = 0.0
        sample_count = 0
        ssim_values = []

        with sf.SoundFile(audio_orig) as f_o, sf.SoundFile(audio_stego) as f_s:

            if f_o.samplerate != f_s.samplerate:
                context["error"] = "Sample rate audio tidak sama"
                return render(request, "pengujian.html", context)

            for _ in range(max_blocks):
                block_o = f_o.read(BLOCK_SIZE, dtype="float32")
                block_s = f_s.read(BLOCK_SIZE, dtype="float32")

                if len(block_o) == 0 or len(block_s) == 0:
                    break

                if block_o.ndim > 1:
                    block_o = block_o.mean(axis=1)
                if block_s.ndim > 1:
                    block_s = block_s.mean(axis=1)

                min_len = min(len(block_o), len(block_s))
                block_o = block_o[:min_len]
                block_s = block_s[:min_len]

                diff = block_o - block_s
                mse_sum += np.sum(diff ** 2)
                sample_count += min_len

                if min_len > 100:
                    ssim_values.append(
                        ssim(block_o, block_s,
                             data_range=block_o.max() - block_o.min())
                    )

        mse_audio = mse_sum / sample_count if sample_count else 0.0
        psnr_audio = calculate_psnr(mse_audio, 1.0)
        ssim_audio = float(np.mean(ssim_values)) if ssim_values else 1.0

        context["metrics"] = {
            "audio": {
                "mse": mse_audio,
                "psnr": psnr_audio,
                "ssim": ssim_audio,
            }
        }

    elif mode == "message":
        message_orig = request.FILES.get("message_original")
        message_recv = request.FILES.get("message_recovered")

        if not message_orig or not message_recv:
            context["error"] = "Pesan asli dan pesan hasil wajib diunggah"
            return render(request, "pengujian.html", context)

        context["upload_info"] = [
            {"label": "Message Original", "name": message_orig.name, "size": message_orig.size},
            {"label": "Message Recovered", "name": message_recv.name, "size": message_recv.size},
        ]

        msg_o = message_orig.read()
        msg_r = message_recv.read()

        min_len_msg = min(len(msg_o), len(msg_r))
        msg_o = msg_o[:min_len_msg]
        msg_r = msg_r[:min_len_msg]

        ber_message = calculate_ber(msg_o, msg_r)

        context["metrics"] = {
            "message": {
                "ber": ber_message,
            }
        }

    return render(request, "pengujian.html", context)

def calculate_mse(a, b):
    return np.mean((a - b) ** 2)


def calculate_psnr(mse, max_val):
    if mse == 0:
        return float("inf")
    return 20 * math.log10(max_val / math.sqrt(mse))


def calculate_ssim_audio(a, b):
    return ssim(a, b, data_range=b.max() - b.min())


def calculate_ber(a, b):
    total_bits = len(a) * 8
    error_bits = sum(bin(x ^ y).count("1") for x, y in zip(a, b))
    return error_bits / total_bits
