from django.urls import path
from . views import encrypt_image, decrypt_image, stegano_decode, stegano_encode

urlpatterns = [
    path("encrypt/", encrypt_image, name="encrypt"),
    path("decrypt/", decrypt_image, name="decrypt"),
    path("encode/", stegano_encode, name="encode"),
    path("decode/", stegano_decode, name="decode"),
]