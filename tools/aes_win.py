"""AES-256-ECB usando a CNG nativa do Windows (bcrypt.dll), sem dependencias externas."""
import ctypes
from ctypes import wintypes

_bcrypt = ctypes.WinDLL("bcrypt.dll")
_BCRYPT_ALG_HANDLE = wintypes.HANDLE
_BCRYPT_KEY_HANDLE = wintypes.HANDLE


def _check(status, what):
    if status != 0:
        raise OSError(f"{what} falhou: NTSTATUS 0x{status & 0xFFFFFFFF:08X}")


class AesEcb:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("chave AES-256 precisa ter 32 bytes")
        self._alg = _BCRYPT_ALG_HANDLE()
        _check(_bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(self._alg), "AES", None, 0),
               "BCryptOpenAlgorithmProvider")
        mode = ctypes.create_unicode_buffer("ChainingModeECB")
        _check(_bcrypt.BCryptSetProperty(self._alg, "ChainingMode", mode,
                                         ctypes.sizeof(mode), 0), "BCryptSetProperty")
        self._key = _BCRYPT_KEY_HANDLE()
        kbuf = ctypes.create_string_buffer(key, len(key))
        _check(_bcrypt.BCryptGenerateSymmetricKey(self._alg, ctypes.byref(self._key), None, 0,
                                                  kbuf, len(key), 0),
               "BCryptGenerateSymmetricKey")

    def decrypt(self, data: bytes) -> bytes:
        if len(data) % 16:
            raise ValueError("dados precisam ser multiplos de 16 bytes")
        inp = ctypes.create_string_buffer(data, len(data))
        out = ctypes.create_string_buffer(len(data))
        written = wintypes.ULONG()
        _check(_bcrypt.BCryptDecrypt(self._key, inp, len(data), None, None, 0,
                                     out, len(data), ctypes.byref(written), 0),
               "BCryptDecrypt")
        return out.raw[:written.value]

    def close(self):
        if self._key:
            _bcrypt.BCryptDestroyKey(self._key)
            self._key = None
        if self._alg:
            _bcrypt.BCryptCloseAlgorithmProvider(self._alg, 0)
            self._alg = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        self.close()
