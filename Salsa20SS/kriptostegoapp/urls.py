from django.urls import path
from . views import encrypt_file, decrypt_file, stegano_decode, stegano_encode

urlpatterns = [
    path("encrypt/", encrypt_file, name="encrypt"),
    path("decrypt/", decrypt_file, name="decrypt"),
    path("encode/", stegano_encode, name="encode"),
    path("decode/", stegano_decode, name="decode"),
]