import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from flow_cli.migrated_image import (
    MODEL_LABELS,
    _image_format,
    _save_image,
    parse_t2i_request,
)

PROJECT_ID = "123e4567-e89b-42d3-a456-426614174000"


class MigratedImageTests(unittest.TestCase):
    def test_current_models_include_lite_and_exclude_retired_imagen(self):
        self.assertEqual(
            MODEL_LABELS,
            {
                "nano-pro": "Nano Banana Pro",
                "nano2": "Nano Banana 2",
                "nano2-lite": "Nano Banana 2 Lite",
            },
        )

    def test_parse_core_t2i_options(self):
        request = parse_t2i_request(
            [
                "一只白猫",
                "--model",
                "nano2-lite",
                "--aspect",
                "16:9",
                "-n",
                "1",
                "-o",
                "output/cat.png",
                "--project",
                PROJECT_ID,
            ]
        )

        self.assertEqual(request.prompt, "一只白猫")
        self.assertEqual(request.model, "nano2-lite")
        self.assertEqual(request.aspect, "16:9")
        self.assertEqual(request.output, Path("output/cat.png"))

    def test_rejects_multiple_images_with_one_output_path(self):
        with self.assertRaisesRegex(ValueError, "只能生成 1 张"):
            parse_t2i_request(
                ["竹林", "-n", "2", "-o", "one.png", "--project", PROJECT_ID]
            )

    def test_jpeg_response_is_converted_when_png_requested(self):
        source = io.BytesIO()
        Image.new("RGB", (8, 6), (10, 20, 30)).save(source, format="JPEG")
        data = source.getvalue()
        self.assertEqual(_image_format(data), "JPEG")

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "result.png"
            saved = _save_image(data, output)
            with Image.open(saved) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.size, (8, 6))


if __name__ == "__main__":
    unittest.main()
