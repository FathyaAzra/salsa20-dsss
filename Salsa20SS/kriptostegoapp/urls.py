from django.urls import path
from . views import encrypt_file, decrypt_file, stegano_decode, stegano_encode, home, dsss_progress_encode, dsss_progress_decode

urlpatterns = [
    path("encrypt/", encrypt_file, name="encrypt"),
    path("decrypt/", decrypt_file, name="decrypt"),
    path("encode/", stegano_encode, name="encode"),
    path("decode/", stegano_decode, name="decode"),
    path("encode/progress/", dsss_progress_encode),
    path("decode/progress/", dsss_progress_decode),
    path('', home, name='home')

]