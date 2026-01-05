import os
import random
import numpy as np
import tempfile
from django.shortcuts import render
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import soundfile as sf

from .algorithms.salsa20 import encrypt_decrypt
from .algorithms.dsss import dsss_encode, dsss_decode

def encrypt_file(request):
    encrypted_url = None
    key_url = None

    if request.method == "POST":
        uploaded_file = request.FILES["file"]

        data = uploaded_file.read()

        key = bytes([random.randint(0, 255) for _ in range(32)])
        nonce = b"12345678"

        cipher_bytes = encrypt_decrypt(data, key, nonce)

        encrypted_path = "encrypted/encrypted.bin"
        key_path = "encrypted/key.bin"

        default_storage.save(encrypted_path, ContentFile(cipher_bytes))
        default_storage.save(key_path, ContentFile(key))

        encrypted_url = settings.MEDIA_URL + encrypted_path
        key_url = settings.MEDIA_URL + key_path

    return render(request, "encrypt_salsa20.html", {
        "encrypted": encrypted_url,
        "key": key_url,
    })


def decrypt_file(request):
    recovered_url = None

    if request.method == "POST":
        cipher_bytes = request.FILES["cipher"].read()
        key = request.FILES["key"].read()

        nonce = b"12345678"
        plain_bytes = encrypt_decrypt(cipher_bytes, key, nonce)

        recovered_path = "decrypted/recovered.jpeg"
        default_storage.save(recovered_path, ContentFile(plain_bytes))

        recovered_url = settings.MEDIA_URL + recovered_path

    return render(request, "decrypt_salsa20.html", {
        "recovered": recovered_url
    })


def stegano_encode(request):
    output_url = None
    metadata = None

    if request.method == "POST":
        audio_file = request.FILES["audio"]
        secret_file = request.FILES["secret_file"]
        password = request.POST.get("password", "secret")

        alpha = float(request.POST.get("alpha", 0.01))
        L = int(request.POST.get("L", 512))
        repeat_n = int(request.POST.get("repeat", 3))

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as in_audio:
            in_audio.write(audio_file.read())
            in_audio_path = in_audio.name

        secret_bytes = secret_file.read()
        out_audio_path = in_audio_path.replace(".wav", "_stego.flac")

        dsss_encode(
            in_audio=in_audio_path,
            out_audio=out_audio_path,
            payload=secret_bytes,
            key=password,
            alpha=alpha,
            L=L,
            repeat_n=repeat_n,
        )

        dst = "stego/encoded.flac"
        default_storage.save(dst, ContentFile(open(out_audio_path, "rb").read()))
        output_url = settings.MEDIA_URL + dst

        metadata = {
            "filename": secret_file.name,
            "bytes": len(secret_bytes),
            "bits": len(secret_bytes) * 8,
        }

        os.remove(in_audio_path)
        os.remove(out_audio_path)

    return render(request, "encode_ss.html", {
        "file": output_url,
        "meta": metadata,
    })


def stegano_decode(request):
    output_url = None

    if request.method == "POST":
        stego_audio = request.FILES["audio"]
        password = request.POST.get("password", "secret")

        L = int(request.POST.get("L", 512))
        repeat_n = int(request.POST.get("repeat", 3))

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as in_audio:
            in_audio.write(stego_audio.read())
            stego_path = in_audio.name

        out_path = stego_path.replace(".wav", "_decoded.bin")

        dsss_decode(
            stego_audio=stego_path,
            out_file=out_path,
            key=password,
            L=L,
            repeat_n=repeat_n,
        )

        dst = "stego/recovered.bin"
        default_storage.save(dst, ContentFile(open(out_path, "rb").read()))
        output_url = settings.MEDIA_URL + dst

        os.remove(stego_path)
        os.remove(out_path)

    return render(request, "decode_ss.html", {"file": output_url})
