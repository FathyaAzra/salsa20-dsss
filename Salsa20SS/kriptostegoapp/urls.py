from django.urls import path
from . views import encrypt_file, decrypt_file, stegano_decode, stegano_encode, home, pengujian_file

urlpatterns = [
    path("encrypt/", encrypt_file, name="encrypt"),
    path("decrypt/", decrypt_file, name="decrypt"),
    path("encode/", stegano_encode, name="encode"),
    path("decode/", stegano_decode, name="decode"),
    path("test/", pengujian_file, name="test"),
    path('', home, name='home')
]