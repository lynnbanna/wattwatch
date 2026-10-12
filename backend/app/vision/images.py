from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"PNG", "JPEG"}


class ImageValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_image(data: bytes, max_pixels: int) -> Image.Image:
    """Decode an uploaded image, trusting its content rather than its declared type.

    Returns an RGB image with EXIF orientation applied.
    """
    try:
        image = Image.open(BytesIO(data))
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ImageValidationError(
            "unsupported_file_type", "File is not a PNG or JPEG image"
        ) from exc

    if image.format not in ALLOWED_FORMATS:
        raise ImageValidationError("unsupported_file_type", "File is not a PNG or JPEG image")

    width, height = image.size
    if width * height > max_pixels:
        raise ImageValidationError(
            "image_too_large",
            f"Image is {width}x{height} px; the limit is {max_pixels:,} pixels",
        )

    try:
        image.load()
    except OSError as exc:
        raise ImageValidationError("invalid_image", "Image data is corrupt or truncated") from exc

    return ImageOps.exif_transpose(image).convert("RGB")
