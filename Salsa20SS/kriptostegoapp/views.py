import os
import random
import numpy as np
from PIL import Image
from django.shortcuts import render
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import soundfile as sf

from .algorithms.salsa20 import encrypt_decrypt
from .algorithms.dsss import dsss_enc_split, dsss_dec_split


def encrypt_image(request):
    encrypted_bin_url = None
    metadata_url = None
    key_url = None

    if request.method == "POST":
        img = Image.open(request.FILES["image"]).convert("RGB")
        width, height = img.size
        data = np.array(img).tobytes()

        key = os.urandom(32)
        nonce = b"12345678"

        cipher_bytes = encrypt_decrypt(data, key, nonce)

        encrypted_path = "encrypted/encrypted.bin"
        metadata_path = "encrypted/metadata.txt"
        key_path = "encrypted/key.bin"

        default_storage.save(encrypted_path, ContentFile(cipher_bytes))
        default_storage.save(metadata_path, ContentFile(f"{width},{height}".encode()))
        default_storage.save(key_path, ContentFile(key))

        encrypted_bin_url = settings.MEDIA_URL + encrypted_path
        metadata_url = settings.MEDIA_URL + metadata_path
        key_url = settings.MEDIA_URL + key_path

    return render(request, "encrypt_salsa20.html", {
        "bin": encrypted_bin_url,
        "metadata": metadata_url,
        "key": key_url,
    })


def decrypt_image(request):
    decrypted_url = None

    if request.method == "POST":
        cipher_bytes = request.FILES["cipher"].read()
        width, height = map(int, request.FILES["metadata"].read().decode().split(","))
        key = request.FILES["key"].read()

        nonce = b"12345678"
        plain_bytes = encrypt_decrypt(cipher_bytes, key, nonce)

        img = Image.frombytes("RGB", (width, height), plain_bytes)

        out_path = "decrypted/decrypted.png"
        img.save(settings.MEDIA_ROOT / out_path)

        decrypted_url = settings.MEDIA_URL + out_path

    return render(request, "decrypt_salsa20.html", {"decrypted": decrypted_url})

def stegano_encode(request):
    result_files = []
    metadata = None

    if request.method == "POST":
        audio_file = request.FILES["audio"]
        secret_file = request.FILES["secret_file"]
        password = request.POST.get("password", "secret")

        signal, sr = sf.read(audio_file)
        signal = signal.astype(float)

        secret_name = secret_file.name
        secret_bytes = secret_file.read()

        generated = dsss_enc_split(signal, secret_bytes, password=password, prefix="stego", samplerate=sr)

        for file_path in generated:
            dst = f"stego/enc/{os.path.basename(file_path)}"
            default_storage.save(dst, ContentFile(open(file_path, "rb").read()))
            os.remove(file_path)
            result_files.append(settings.MEDIA_URL + dst)

        metadata = {
            "filename": secret_name,
            "size": len(secret_bytes),
            "bits": len(secret_bytes) * 8,
        }

    return render(request, "encode_ss.html", {
        "files": result_files,
        "meta": metadata
    })


def stegano_decode(request):
    output_url = None

    if request.method == "POST":
        files = request.FILES.getlist("files")
        password = request.POST.get("password", "secret")

        paths = []
        for f in files:
            saved = default_storage.save(f"stego/dec/{f.name}", ContentFile(f.read()))
            paths.append(os.path.join(settings.MEDIA_ROOT, saved))

        result_bytes = dsss_dec_split(paths, password=password)

        recovered_path = "stego/recovered.bin"
        default_storage.save(recovered_path, ContentFile(result_bytes))
        output_url = settings.MEDIA_URL + recovered_path

    return render(request, "decode_ss.html", {"file": output_url})
