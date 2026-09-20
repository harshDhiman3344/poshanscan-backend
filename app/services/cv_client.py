import logging
import random
from typing import Optional
import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.cv import CVInferResponse, CVQualityFlags

logger = logging.getLogger("poshanscan-backend.cv")


class CVInferenceError(Exception):
    def __init__(self, status_code: int, error: str, message: str):
        self.status_code = status_code
        self.error = error
        self.message = message
        super().__init__(message)


async def run_cv_inference(
    image_bytes: bytes,
    filename: str = "scan.jpg",
    reference_type: str = "aruco",
    reference_size_mm: float = 50.0,
) -> CVInferResponse:
    """
    Call Yash's Computer Vision microservice (/infer) or generate a mock result.
    Raises CVInferenceError on processing failures (e.g., marker not found).
    """
    if not image_bytes or len(image_bytes) == 0:
        raise CVInferenceError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error="invalid_image",
            message="No image data provided.",
        )

    # 1. Fallback Mock Mode (for local development when ML service is offline)
    if settings.MOCK_CV:
        logger.info("MOCK_CV is enabled: generating simulated CV inference result.")
        # Generate realistic MUAC between 105mm and 135mm
        muac = round(random.uniform(108.0, 134.0), 1)
        if muac < 115.0:
            risk_band = "SAM"
        elif muac < 125.0:
            risk_band = "MAM"
        else:
            risk_band = "Normal"

        return CVInferResponse(
            muac_estimate_mm=muac,
            risk_band=risk_band,
            confidence_score=round(random.uniform(0.75, 0.95), 2),
            quality_flags=CVQualityFlags(
                reference_detected=True,
                arm_detected=True,
                segmentation_ok=True,
            ),
            pipeline_version="v1.0-mock",
        )

    # 2. Live HTTP Request to Yash's Service
    url = f"{settings.CV_SERVICE_URL.rstrip('/')}/infer"
    logger.info("Calling remote CV service at %s", url)

    files = {
        "image": (filename, image_bytes, "image/jpeg"),
    }
    data = {
        "reference_type": reference_type,
        "reference_size_mm": str(reference_size_mm),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, files=files, data=data)
    except httpx.RequestError as exc:
        logger.error("Failed to connect to CV service: %s", exc)
        raise CVInferenceError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error="cv_service_unavailable",
            message="Could not connect to the AI/CV estimation service.",
        )

    if response.status_code == 200:
        payload = response.json()
        return CVInferResponse(**payload)

    # Error handling from Yash's API (422 / 500)
    try:
        err_payload = response.json()
        error_code = err_payload.get("error", "cv_error")
        message = err_payload.get("message", "Error from CV service.")
    except Exception:
        error_code = "cv_error"
        message = response.text or "Error from CV service."

    raise CVInferenceError(
        status_code=response.status_code,
        error=error_code,
        message=message,
    )
