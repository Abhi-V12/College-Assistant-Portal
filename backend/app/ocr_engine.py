import easyocr
_reader = None
def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['en'], gpu=False)
    return _reader

def extract_lines(image_bytes: bytes) -> list[str]:
    return get_reader().readtext(image_bytes, detail=0, paragraph=True)