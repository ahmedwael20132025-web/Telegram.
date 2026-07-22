import os
import time
import requests

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# موديل توليد صور من نص (Text-to-Image) على Replicate - سريع ورخيص
# ممكن تستبدله بأي موديل تاني من replicate.com/explore?category=text-to-image
MODEL_VERSION = "black-forest-labs/flux-schnell"

BASE_URL = "https://api.replicate.com/v1"


def generate_image(prompt: str) -> str:
    """
    يبعت طلب توليد صورة لـ Replicate ويستنى لحد ما يخلص، وبيرجع رابط الصورة الناتجة.
    """
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        f"{BASE_URL}/models/{MODEL_VERSION}/predictions",
        headers=headers,
        json={"input": {"prompt": prompt}},
        timeout=30,
    )
    resp.raise_for_status()
    prediction = resp.json()
    prediction_id = prediction["id"]

    status = prediction["status"]
    while status not in ("succeeded", "failed", "canceled"):
        time.sleep(3)
        poll = requests.get(f"{BASE_URL}/predictions/{prediction_id}", headers=headers, timeout=30)
        poll.raise_for_status()
        prediction = poll.json()
        status = prediction["status"]

    if status != "succeeded":
        raise RuntimeError(f"فشل توليد الصورة: {prediction.get('error')}")

    output = prediction["output"]
    if isinstance(output, list):
        return output[0]
    return output
