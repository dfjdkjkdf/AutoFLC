import zipfile

import pytest

from autoflc.archive import ArchiveError, decode_zip_member_name, extract_zip


def test_decode_ascii_filename_unchanged():
    assert decode_zip_member_name("main.c") == "main.c"


def test_decode_gbk_mislabeled_as_cp437():
    original_name = "测试.c"
    gbk_bytes = original_name.encode("gbk")
    # This is what zipfile would hand back as `member.filename` for an entry
    # written without the UTF-8 flag: the raw GBK bytes decoded as cp437.
    mangled_name = gbk_bytes.decode("cp437")

    assert decode_zip_member_name(mangled_name) == original_name


def test_extract_zip_preserves_directory_structure(tmp_path):
    zip_path = tmp_path / "src.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("pkg/", "")
        zf.writestr("pkg/main.c", "int main(void) { return 0; }")
        zf.writestr("readme.txt", "hello")

    extract_path = tmp_path / "extracted"
    extract_zip(str(zip_path), str(extract_path))

    assert (extract_path / "pkg" / "main.c").read_text() == "int main(void) { return 0; }"
    assert (extract_path / "readme.txt").read_text() == "hello"


def test_extract_zip_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", "pwned")

    extract_path = tmp_path / "sandbox" / "extracted"
    with pytest.raises(ArchiveError):
        extract_zip(str(zip_path), str(extract_path))

    assert not (tmp_path / "sandbox" / "evil.txt").exists()
    assert not (tmp_path / "evil.txt").exists()
