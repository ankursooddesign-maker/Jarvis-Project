import cv2
import mediapipe as mp

mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils


def detect_faces(frame):

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    with mp_face_detection.FaceDetection(
        model_selection=0,
        min_detection_confidence=0.5
    ) as face_detection:

        results = face_detection.process(rgb_frame)

        if results.detections:

            for detection in results.detections:

                mp_drawing.draw_detection(
                    frame,
                    detection
                )

                confidence = int(
                    detection.score[0] * 100
                )

                cv2.putText(
                    frame,
                    f"Human Detected {confidence}%",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )

    return frame