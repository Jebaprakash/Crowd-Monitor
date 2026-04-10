def compute_density(boxes, frame):
    """
    Compute crowd density = total_bbox_area / total_frame_area.
    This gives the percentage of the frame physically occupied by people.
    """
    if not boxes:
        return 0.0
    
    h, w = frame.shape[:2]
    total_frame_area = h * w
    
    total_person_area = 0
    for (x1, y1, x2, y2) in boxes:
        bw = x2 - x1
        bh = y2 - y1
        total_person_area += (bw * bh)
        
    density_ratio = total_person_area / max(total_frame_area, 1)
    return round(density_ratio, 4)


def classify_density(density_ratio):
    # Thresholds based on frame coverage percentage
    if density_ratio < 0.10:
        return "low"
    elif density_ratio <= 0.30:
        return "medium"
    return "high"
