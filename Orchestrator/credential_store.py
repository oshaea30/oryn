"""Mac Keychain credentials, never subprocess arguments, logs or project files."""
import ctypes as C
import sys

SERVICE = b"com.oryn.local-generation"
ACCOUNT = b"meshy-api-key"
NOT_FOUND = -25300


class CredentialError(Exception):
    pass


def validate_key(value):
    if not isinstance(value, str) or not 10 <= len(value.strip()) <= 500 or any(c in value for c in '\r\n\0'):
        raise CredentialError("Enter a valid API key.")
    return value.strip()


class MacKeychain:
    """Use the default user Keychain and its standard application access control.

    Security.framework owns returned password buffers; always free them. We do not
    grant all-app access or change the user's Keychain lock/access settings.
    """
    account = ACCOUNT

    def __init__(self, account=ACCOUNT):
        if account not in (ACCOUNT, b'openai-api-key'):
            raise CredentialError('Unknown ORYN credential account.')
        self.account = account
        if sys.platform != 'darwin':
            raise CredentialError("Secure persistence requires macOS Keychain on this prototype.")
        try:
            self.security = C.CDLL('/System/Library/Frameworks/Security.framework/Security')
            self.core = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        except OSError:
            raise CredentialError("macOS Keychain is unavailable.") from None
        pointer, size = C.c_void_p, C.c_uint32
        self.find = self.security.SecKeychainFindGenericPassword
        self.find.argtypes = [pointer, size, C.c_char_p, size, C.c_char_p, C.POINTER(size), C.POINTER(pointer), C.POINTER(pointer)]
        self.add = self.security.SecKeychainAddGenericPassword
        self.add.argtypes = [pointer, size, C.c_char_p, size, C.c_char_p, size, pointer, C.POINTER(pointer)]
        self.modify = self.security.SecKeychainItemModifyAttributesAndData
        self.modify.argtypes = [pointer, pointer, size, pointer]
        self.free = self.security.SecKeychainItemFreeContent
        self.free.argtypes = [pointer, pointer]
        for fn in (self.find, self.add, self.modify, self.free):
            fn.restype = C.c_int32
        self.release = self.core.CFRelease
        self.release.argtypes = [pointer]
        self.release.restype = None

    @staticmethod
    def check(status):
        if status:
            raise CredentialError("Keychain access failed. Unlock your login Keychain and allow ORYN's Python process if macOS asks. No plaintext fallback was used.")

    def load(self):
        length, data = C.c_uint32(), C.c_void_p()
        status = self.find(None, len(SERVICE), SERVICE, len(self.account), self.account, C.byref(length), C.byref(data), None)
        try:
            if status == NOT_FOUND:
                return ''
            self.check(status)
            if not data or not 10 <= length.value <= 2000:
                raise CredentialError("Stored credential is invalid; update the connection settings.")
            try:
                return validate_key(C.string_at(data, length.value).decode('utf-8'))
            except UnicodeError:
                raise CredentialError("Stored credential is invalid; update the connection settings.") from None
        finally:
            if data:
                self.free(None, data)

    def save(self, value):
        raw = validate_key(value).encode('utf-8')
        item = C.c_void_p()
        status = self.find(None, len(SERVICE), SERVICE, len(self.account), self.account, None, None, C.byref(item))
        try:
            if status == NOT_FOUND:
                self.check(self.add(None, len(SERVICE), SERVICE, len(self.account), self.account, len(raw), raw, None))
            else:
                self.check(status)
                self.check(self.modify(item, None, len(raw), raw))
        finally:
            if item:
                self.release(item)
