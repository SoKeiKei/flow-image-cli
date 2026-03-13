"""
图片生成模型配置
"""

IMAGE_MODELS = {
    "gemini-2.5-flash-image-landscape": {
        "model_name": "GEM_PIX",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
        "description": "Gemini 2.5 Flash - 横屏"
    },
    "gemini-2.5-flash-image-portrait": {
        "model_name": "GEM_PIX",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "description": "Gemini 2.5 Flash - 竖屏"
    },
    "gemini-3.0-pro-image-landscape": {
        "model_name": "GEM_PIX_2",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
        "description": "Gemini 3.0 Pro - 横屏"
    },
    "gemini-3.0-pro-image-portrait": {
        "model_name": "GEM_PIX_2",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "description": "Gemini 3.0 Pro - 竖屏"
    },
    "gemini-3.0-pro-image-square": {
        "model_name": "GEM_PIX_2",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_SQUARE",
        "description": "Gemini 3.0 Pro - 方图"
    },
    "gemini-3.0-pro-image-four-three": {
        "model_name": "GEM_PIX_2",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE_FOUR_THREE",
        "description": "Gemini 3.0 Pro - 4:3 横屏"
    },
    "gemini-3.0-pro-image-three-four": {
        "model_name": "GEM_PIX_2",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT_THREE_FOUR",
        "description": "Gemini 3.0 Pro - 3:4 竖屏"
    },
    "imagen-4.0-generate-preview-landscape": {
        "model_name": "IMAGEN_3_5",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
        "description": "Imagen 4.0 - 横屏"
    },
    "imagen-4.0-generate-preview-portrait": {
        "model_name": "IMAGEN_3_5",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "description": "Imagen 4.0 - 竖屏"
    },
    "gemini-3.1-flash-image-landscape": {
        "model_name": "NARWHAL",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
        "description": "Gemini 3.1 Flash - 横屏 (推荐)"
    },
    "gemini-3.1-flash-image-portrait": {
        "model_name": "NARWHAL",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "description": "Gemini 3.1 Flash - 竖屏 (推荐)"
    },
    "gemini-3.1-flash-image-square": {
        "model_name": "NARWHAL",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_SQUARE",
        "description": "Gemini 3.1 Flash - 方图 (推荐)"
    },
    "gemini-3.1-flash-image-four-three": {
        "model_name": "NARWHAL",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE_FOUR_THREE",
        "description": "Gemini 3.1 Flash - 4:3 横屏 (推荐)"
    },
    "gemini-3.1-flash-image-three-four": {
        "model_name": "NARWHAL",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT_THREE_FOUR",
        "description": "Gemini 3.1 Flash - 3:4 竖屏 (推荐)"
    },
}

DEFAULT_MODEL = "gemini-3.1-flash-image-landscape"


def list_models():
    """列出所有可用模型"""
    print("\n可用图片生成模型:")
    print("-" * 60)
    for model_id, config in IMAGE_MODELS.items():
        default_mark = " (默认)" if model_id == DEFAULT_MODEL else ""
        print(f"  {model_id}{default_mark}")
        print(f"    └─ {config['description']}")
    print("-" * 60)


def get_model_config(model_id: str) -> dict:
    """获取模型配置"""
    if model_id not in IMAGE_MODELS:
        raise ValueError(f"未知模型: {model_id}")
    return IMAGE_MODELS[model_id]
