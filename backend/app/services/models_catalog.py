from app.models.enums import TaskType


MODEL_CATALOG = [
    {
        "id": "nano_banana",
        "type": TaskType.image,
        "label": "Nano Banana",
        "account_types": ["normal", "pro", "ula"],
        "description": "Flow image model mapped to NARWHAL.",
    },
    {
        "id": "banana_pro",
        "type": TaskType.image,
        "label": "Banana Pro",
        "account_types": ["pro", "ula"],
        "description": "Flow image pro model mapped to GEM_PIX_2.",
    },
    {
        "id": "imagen",
        "type": TaskType.image,
        "label": "Imagen",
        "account_types": ["pro", "ula"],
        "description": "Flow Imagen 4 mapping.",
    },
    {
        "id": "imagen_4k",
        "type": TaskType.image,
        "label": "Imagen 4K",
        "account_types": ["ula"],
        "supports_4k": True,
        "description": "4K image output is restricted to ULA accounts.",
    },
    {
        "id": "omni_flash",
        "type": TaskType.video,
        "label": "OMNI Flash",
        "account_types": ["normal", "pro", "ula"],
        "description": "Default OMNI video model mapped to abra_t2v_10s.",
    },
    {
        "id": "veo_3_1_fast",
        "type": TaskType.video,
        "label": "Veo 3.1 Fast",
        "account_types": ["pro", "ula"],
        "description": "Fast Flow video model when enabled for the account.",
    },
    {
        "id": "veo_3_1_lite",
        "type": TaskType.video,
        "label": "Veo 3.1 Lite",
        "account_types": ["normal", "pro", "ula"],
        "description": "Lite Flow video model when enabled for the account.",
    },
    {
        "id": "veo_3_1_quality",
        "type": TaskType.video,
        "label": "Veo 3.1 Quality",
        "account_types": ["pro", "ula"],
        "description": "Quality Flow video model when enabled for the account.",
    },
]


def list_models(task_type: TaskType | None = None) -> list[dict]:
    rows = MODEL_CATALOG
    if task_type:
        rows = [m for m in rows if m["type"] == task_type]
    return [
        {
            "object": "model",
            "provider": "google-flow",
            "supports_4k": False,
            "supports_image_input": item["type"] == TaskType.video,
            **item,
        }
        for item in rows
    ]
