import pywintypes
import win32cred

from aurora.providers.base import ProviderError

TARGET = "Aurora/OpenAI"


def read_key() -> str:
    try:
        record = win32cred.CredRead(TARGET, win32cred.CRED_TYPE_GENERIC)
        return record["CredentialBlob"].decode("utf-16-le")
    except pywintypes.error as error:
        if error.winerror == 1168:
            return ""
        raise ProviderError("Windows не удалось прочитать ключ OpenAI.") from None
    except UnicodeError:
        raise ProviderError("Перезапишите ключ OpenAI в настройках.") from None


def write_key(key: str) -> None:
    try:
        win32cred.CredWrite({
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": TARGET,
            "CredentialBlob": key,
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }, 0)
    except pywintypes.error:
        raise ProviderError("Windows не удалось сохранить ключ OpenAI.") from None
