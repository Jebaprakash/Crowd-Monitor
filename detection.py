import cv2
import numpy as np
from ultralytics import YOLO

model = YOLO("yolov8n.pt")

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

ZONE_NAMES = ["Entry", "Center", "Exit"]


def detect_persons(frame, blur_faces=False):
    """
    Run YOLOv8 on frame.
    Returns: (annotated_frame, count, boxes, zone_counts)
    zone_counts = {"Entry": int, "Center": int, "Exit": int}
    Zones are horizontal thirds: left=Entry, middle=Center, right=Exit.
    If blur_faces=True, Gaussian-blurs detected faces inside each person bbox.
    """
    h, w = frame.shape[:2]
    zone_w = w // 3

    results = model(frame, classes=[0], verbose=False)[0]  # class 0 = person
    count = 0
    boxes = []
    zone_counts = {"Entry": 0, "Center": 0, "Exit": 0}

    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        if conf > 0.4:
            # Determine zone by bbox centre-x
            cx = (x1 + x2) // 2
            if cx < zone_w:
                zone = "Entry"
            elif cx < 2 * zone_w:
                zone = "Center"
            else:
                zone = "Exit"
            zone_counts[zone] += 1

    # Face blur inside person bounding box (Optimized: only if person is large enough)
            if blur_faces and (x2 - x1) > 50:
                roi = frame[max(0, y1):y2, max(0, x1):x2]
                if roi.size > 0:
                    try:
                        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        # Detect faces with more restrictive parameters for speed
                        faces = _face_cascade.detectMultiScale(
                            gray_roi, scaleFactor=1.2, minNeighbors=5, minSize=(30, 30)
                        )
                        for (fx, fy, fw, fh) in faces:
                            face = roi[fy: fy + fh, fx: fx + fw]
                            if face.size > 0:
                                # Use a smaller kernel for Gaussian blur to save CPU
                                roi[fy: fy + fh, fx: fx + fw] = cv2.GaussianBlur(
                                    face, (25, 25), 0
                                )
                    except Exception as e:
                        print(f"[Detection] Face blur error: {e}")

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 80), 2)
            cv2.putText(
                frame,
                f"{zone[0]} {conf:.2f}",
                (x1, max(y1 - 6, 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 80),
                1,
            )
            count += 1
            boxes.append((x1, y1, x2, y2))

    # Zone dividers on frame
    cv2.line(frame, (zone_w, 0), (zone_w, h), (80, 80, 220), 1)
    cv2.line(frame, (2 * zone_w, 0), (2 * zone_w, h), (80, 80, 220), 1)
    for i, lbl in enumerate(["Entry", "Center", "Exit"]):
        cv2.putText(
            frame,
            lbl,
            (i * zone_w + 5, h - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (80, 80, 220),
            1,
        )

    return frame, count, boxes, zone_counts
