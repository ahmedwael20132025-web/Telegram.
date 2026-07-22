import os
import time
import requests

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# موديل توليد فيديو من نص (Text-to-Video) على Replicate
# ممكن تستبدله بأي موديل تاني موجود على replicate.com/explore بنفس الطريقة
MODEL_VERSION = "minimax/video-01"

BASE_URL = "https://api.replicate.com/v1"


def generate_video(prompt: str, duration: int = 5) -> str:
    """
    يبعت طلب توليد فيديو لـ Replicate ويستنى لحد ما يخلص، وبيرجع رابط الفيديو الناتج.
    duration: المدة بالثواني (بيتم إرسالها للموديل لو بيدعمها، وإلا بيتجاهلها الموديل).
    """
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # بعض الموديلات على Replicate بتتنادى بالـ model name مباشرة عبر endpoint /models/{model}/predictions
    resp = requests.post(
        f"{BASE_URL}/models/{MODEL_VERSION}/predictions",
        headers=headers,
        json={"input": {"prompt": prompt, "duration": duration}},
        timeout=30,
    )
    resp.raise_for_status()
    prediction = resp.json()
    prediction_id = prediction["id"]

    # Polling لحد ما التوليد يخلص
    status = prediction["status"]
    while status not in ("succeeded", "failed", "canceled"):
        time.sleep(5)
        poll = requests.get(f"{BASE_URL}/predictions/{prediction_id}", headers=headers, timeout=30)
        poll.raise_for_status()
        prediction = poll.json()
        status = prediction["status"]

    if status != "succeeded":
        raise RuntimeError(f"فشل توليد الفيديو: {prediction.get('error')}")

    output = prediction["output"]
    # الناتج ممكن يكون رابط واحد أو ليستة روابط حسب الموديل
    if isinstance(output, list):
        return output[0]
    return output
