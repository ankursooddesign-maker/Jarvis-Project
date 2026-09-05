import cv2
import base64
import requests
import os
import time


TEMP_IMAGE = "data/temp_frame.jpg"


# ── Capture image ────────────────────────────────
def capture_image():

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():

        print("[JARVIS] Could not access camera.")

        return False

    # Better Mac webcam reliability
    cap.set(
        cv2.CAP_PROP_BUFFERSIZE,
        1
    )

    print("[JARVIS] Warming up camera...")

    success = False
    frame = None

    # Warmup frames
    for _ in range(15):

        success, frame = cap.read()

        time.sleep(0.05)

    if not success or frame is None:

        cap.release()

        print("[JARVIS] Failed to capture frame.")

        return False

    # Ensure folder exists
    os.makedirs(
        "data",
        exist_ok=True
    )

    saved = cv2.imwrite(
        TEMP_IMAGE,
        frame
    )

    cap.release()

    if not saved:

        print("[JARVIS] Failed to save image.")

        return False

    if not os.path.exists(TEMP_IMAGE):

        print("[JARVIS] Image file missing.")

        return False

    return True


# ── Analyze image ────────────────────────────────
def analyze_image(

    image_path=TEMP_IMAGE,

    question=(
        "Describe clearly what is visible "
        "in this image. Mention the main "
        "object, colors, materials, people, "
        "environment, and what the object "
        "is commonly used for."
    )
):

    try:

        with open(image_path, "rb") as image_file:

            image_base64 = base64.b64encode(
                image_file.read()
            ).decode("utf-8")

        response = requests.post(

            "http://localhost:11434/api/generate",

            json={

                "model": "llava",

                "prompt": question,

                "images": [image_base64],

                "stream": False
            },

            timeout=120
        )

        data = response.json()

        result = data.get(
            "response",
            "Could not analyze image."
        )

        return result.strip()

    except requests.exceptions.ConnectionError:

        return (
            "Ollama is not running. "
            "Please start Ollama first, sir."
        )

    except Exception as e:

        return (
            f"Analysis failed: {str(e)}"
        )


# ── Scene description ────────────────────────────
def describe_scene():

    print("\n[JARVIS] Capturing image...\n")

    if capture_image():

        print(
            "[JARVIS] Analyzing image...\n"
        )

        result = analyze_image()

        if os.path.exists(TEMP_IMAGE):

            os.remove(TEMP_IMAGE)

        return result

    return "Camera capture failed, sir."


# ── Ask specific question ────────────────────────
def answer_question(question: str):

    print(
        f"\n[JARVIS] Looking for: {question}\n"
    )

    if capture_image():

        # ── Small delay prevents audio overlap ──
        time.sleep(0.5)

        result = analyze_image(
            question=question
        )

        if os.path.exists(TEMP_IMAGE):

            os.remove(TEMP_IMAGE)

        return result

    return "Camera capture failed, sir."