import os
import shutil
import zipfile

FALLBACK_ENCODINGS = ["gbk", "utf-8", "gb2312", "latin1"]


class ArchiveError(Exception):
    """Raised when a zip archive cannot be safely extracted."""


def decode_zip_member_name(filename):
    """Recover the intended filename from a zip entry mis-labeled as cp437.

    Zip files created on Windows with non-English filenames are commonly
    written without the UTF-8 flag, so Python's zipfile module decodes them
    as cp437 by default, mangling e.g. Chinese filenames. This re-encodes
    back to bytes and tries a few common encodings, preferring the first one
    that actually decodes to non-ASCII text (if any).
    """
    encoded_name = filename.encode("cp437")
    for enc in FALLBACK_ENCODINGS:
        try:
            decoded_name = encoded_name.decode(enc)
            if any(ord(c) > 127 for c in decoded_name):
                return decoded_name
        except UnicodeDecodeError:
            continue
    return encoded_name.decode("utf-8", errors="replace")


def _is_within_directory(directory, target):
    directory = os.path.abspath(directory)
    target = os.path.abspath(target)
    return os.path.commonpath([directory, target]) == directory


def extract_zip(zip_path, extract_path):
    """Extract a zip archive into extract_path, guarding against zip-slip path traversal."""
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for member in zip_ref.infolist():
            decoded_name = decode_zip_member_name(member.filename)
            target_path = os.path.join(extract_path, decoded_name)

            if not _is_within_directory(extract_path, target_path):
                raise ArchiveError(f"Rejected zip entry outside extraction directory: {member.filename}")

            if member.is_dir():
                os.makedirs(target_path, exist_ok=True)
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zip_ref.open(member, "r") as source, open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)
