import os
import random
import numpy as np
import tempfile
from django.shortcuts import render
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import JsonResponse
import soundfile as sf
import json

from .algorithms.salsa20 import encrypt_decrypt
from .algorithms.dsss import dsss_encode, dsss_decode

DSSS_PROGRESS = {
    "encode": 0,
    "decode": 0,
}

def home(request):
    return render(request, 'home.html')

def encrypt_file(request):
    encrypted_url = None
    key_url = None
    metadata_url = None

    if request.method == "POST":
        uploaded_file = request.FILES["file"]
        data = uploaded_file.read()

        filename = uploaded_file.name
        name, ext = os.path.splitext(filename)

        metadata = {
            "filename": name,
            "extension": ext
        }

        key = bytes([random.randint(0, 255) for _ in range(32)])
        nonce = b"12345678"

        cipher_bytes = encrypt_decrypt(data, key, nonce)

        encrypted_path = "encrypted/encrypted.bin"
        key_path = "encrypted/key.bin"
        meta_path = "encrypted/metadata.json"

        default_storage.save(encrypted_path, ContentFile(cipher_bytes))
        default_storage.save(key_path, ContentFile(key))
        default_storage.save(meta_path, ContentFile(json.dumps(metadata)))

        encrypted_url = settings.MEDIA_URL + encrypted_path
        key_url = settings.MEDIA_URL + key_path
        metadata_url = settings.MEDIA_URL + meta_path

    return render(request, "encrypt_salsa20.html", {
        "encrypted": encrypted_url,
        "key": key_url,
        "metadata": metadata_url,
    })


def decrypt_file(request):
    recovered_url = None

    if request.method == "POST":
        cipher_bytes = request.FILES["cipher"].read()
        key = request.FILES["key"].read()
        meta = json.loads(request.FILES["metadata"].read().decode())

        nonce = b"12345678"
        plain_bytes = encrypt_decrypt(cipher_bytes, key, nonce)

        filename = meta["filename"]
        ext = meta["extension"]

        recovered_path = f"decrypted/{filename}{ext}"

        default_storage.save(recovered_path, ContentFile(plain_bytes))
        recovered_url = settings.MEDIA_URL + recovered_path

    return render(request, "decrypt_salsa20.html", {
        "recovered": recovered_url
    })


def stegano_encode(request):
    output_url = None

    if request.method == "POST":
        DSSS_PROGRESS["encode"] = 0
        audio_file = request.FILES.get("audio_file")
        secret_file = request.FILES.get("secret_file")
        password = request.POST.get("password", "secret")

        if not audio_file or not secret_file:
            return render(request, "encode_ss.html", {
                "error": "Audio WAV dan file BIN wajib diunggah"
            })

        alpha = float(request.POST.get("alpha", 0.01))
        L = int(request.POST.get("L", 512))
        repeat_n = int(request.POST.get("repeat", 3))

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            tmp_audio.write(audio_file.read())
            in_audio = tmp_audio.name

        secret_bytes = secret_file.read()
        out_audio = in_audio.replace(".wav", "_stego.flac")

        def progress_cb(p):
            DSSS_PROGRESS["encode"] = p

        dsss_encode(
            in_audio=in_audio,
            out_audio=out_audio,
            payload=secret_bytes,
            key=password,
            alpha=alpha,
            L=L,
            repeat_n=repeat_n,
            progress_cb=progress_cb,
        )

        dst = "stego/encoded.flac"
        with open(out_audio, "rb") as f:
            default_storage.save(dst, ContentFile(f.read()))

        output_url = settings.MEDIA_URL + dst
        os.remove(in_audio)
        os.remove(out_audio)
        DSSS_PROGRESS["encode"] = 100
    return render(request, "encode_ss.html", {
        "file": output_url
    })


def stegano_decode(request):
    output_url = None

    if request.method == "POST":
        DSSS_PROGRESS["decode"] = 0

        stego_audio = request.FILES.get("audio_file")
        password = request.POST.get("password", "secret")
        L = int(request.POST.get("L", 512))
        repeat_n = int(request.POST.get("repeat", 3))

        if not stego_audio:
            return render(request, "decode_ss.html", {
                "error": "File audio wajib diunggah"
            })

        # ambil ekstensi asli
        ext = os.path.splitext(stego_audio.name)[1].lower()
        if ext not in [".wav", ".flac"]:
            return render(request, "decode_ss.html", {
                "error": "Format harus WAV atau FLAC"
            })

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(stego_audio.read())
            stego_path = tmp.name

        out_path = stego_path + "_decoded.bin"

        def progress_cb(p):
            DSSS_PROGRESS["decode"] = p

        dsss_decode(
            stego_audio=stego_path,
            out_file=out_path,
            key=password,
            L=L,
            repeat_n=repeat_n,
            progress_cb=progress_cb,
        )

        dst = "stego/recovered.bin"
        with open(out_path, "rb") as f:
            default_storage.save(dst, ContentFile(f.read()))

        output_url = settings.MEDIA_URL + dst

        os.remove(stego_path)
        os.remove(out_path)

        DSSS_PROGRESS["decode"] = 100

    return render(request, "decode_ss.html", {
        "file": output_url
    })

    output_url = None

    if request.method == "POST":
        DSSS_PROGRESS["decode"] = 0
        stego_audio = request.FILES.get("audio_file")
        password = request.POST.get("password", "secret")
        L = int(request.POST.get("L", 512))
        repeat_n = int(request.POST.get("repeat", 3))

        if not stego_audio:
            return render(request, "decode_ss.html", {
                "error": "File audio stego wajib diunggah"
            })

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(stego_audio.read())
            stego_path = tmp.name

        out_path = stego_path.replace(".wav", "_decoded.bin")

        def progress_cb(p):
            DSSS_PROGRESS["decode"] = p

        dsss_decode(
            stego_audio=stego_path,
            out_file=out_path,
            key=password,
            L=L,
            repeat_n=repeat_n,
            progress_cb=progress_cb,
        )

        dst = "stego/recovered.bin"
        with open(out_path, "rb") as f:
            default_storage.save(dst, ContentFile(f.read()))

        output_url = settings.MEDIA_URL + dst

        os.remove(stego_path)
        os.remove(out_path)

        DSSS_PROGRESS["decode"] = 100

    return render(request, "decode_ss.html", {
        "file": output_url
    })

def dsss_progress_encode(request):
    return JsonResponse({"progress": DSSS_PROGRESS["encode"]})

def dsss_progress_decode(request):
    return JsonResponse({"progress": DSSS_PROGRESS["decode"]})
