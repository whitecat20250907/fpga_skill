"""Array-only geometry derived from the pinned deployed MediaPipeFaceAlignment.
Keep its rounding, eye gates and ROI definitions; no neural call or mp.Image.
Original GazeFollower attribution/license remain in the app and baseline source.
"""
import math
import numpy as np
from gazefollower.misc import FaceInfo

def from_array(self,p,image_shape,timestamp,sequence=None):
    if int(timestamp)!=timestamp or timestamp<0:raise ValueError('Nonnegative integer timestamp required')
    face_info=FaceInfo();face_info.timestamp=timestamp;face_info.capture_sequence=sequence
    image_height,image_width=image_shape[:2];face_info.img_w=image_width;face_info.img_h=image_height
    if p is None:
        self.reset_filters();return face_info
    coordinates = np.asarray(p, dtype=np.float64)
    if (coordinates.shape not in ((468,3),(478,3)) or not np.isfinite(coordinates).all()
            or np.max(np.abs(coordinates)) > 10
            or np.ptp(coordinates[:,0]) <= 1e-6 or np.ptp(coordinates[:,1]) <= 1e-6):
        self.reset_filters()
        return face_info
    face_info.status = True
    precise_pixels = coordinates * [image_width,image_height,image_width]
    scaled_landmarks = np.rint(precise_pixels)
    _face_mesh = scaled_landmarks.astype(np.int16)

    # Preserve genuine dense geometry even when a separate eye ROI is unusable.
    face_info.face_landmarks = _face_mesh
    face_info.landmarks_valid = True
    face_info.left_eye_ear = self.eye_aspect_ratio(precise_pixels, (33,160,158,133,153,144))
    face_info.right_eye_ear = self.eye_aspect_ratio(precise_pixels, (362,385,387,263,373,380))
    face_info.left_eye_openness = self.calculate_polygon_area(_face_mesh[self.left_vertices_index,:2])
    face_info.right_eye_openness = self.calculate_polygon_area(_face_mesh[self.right_vertices_index,:2])

    # Computing face box from the face mesh
    max_x = np.max(_face_mesh[:, 0])
    min_x = np.min(_face_mesh[:, 0])
    max_y = np.max(_face_mesh[:, 1])
    min_y = np.min(_face_mesh[:, 1])

    if min_x < 0:
        min_x = 0
    if min_y < 0:
        min_y = 0
    if max_x > image_width:
        max_x = image_width
    if max_y > image_height:
        max_y = image_height

    # Filtering the instances near the screen edge
    lip_position_y = np.mean(_face_mesh[:, 1][self.lip_vertices_index])

    if lip_position_y >= image_height:
        face_info.status = True
        face_info.can_gaze_estimation = False
        self.reset_filters()
        return face_info

    face_height = math.fabs(min_y - max_y)
    face_width = math.fabs(min_x - max_x)

    delta = (face_width - face_height) / 4

    left_top_face_point = [min_x + delta, min_y - delta]
    right_bottom_face_point = [max_x - delta, max_y + delta]

    if right_bottom_face_point[1] > image_height:
        right_bottom_face_point[1] = image_height - 1
    if left_top_face_point[1] < 0:
        left_top_face_point[1] = 0
    if left_top_face_point[0] < 0:
        left_top_face_point[0] = 0
    if right_bottom_face_point[0] > image_width:
        right_bottom_face_point[0] = image_width - 1

    # face box to integer format
    left_top_face_point[0] = int(left_top_face_point[0])
    left_top_face_point[1] = int(left_top_face_point[1])
    right_bottom_face_point[0] = int(right_bottom_face_point[0])
    right_bottom_face_point[1] = int(right_bottom_face_point[1])

    # Get the mirrored eye box,
    # which means the left eye box is the right eye box in non-mirror.

    # split the distance between the inner eye corners into 100 units
    scale = math.fabs(scaled_landmarks[362,0] - scaled_landmarks[133,0]) / 100
    x_padding = 20  # padding the eye corners
    y_0 = 0.6  # less area for upper portion of the eye area
    y_1 = 0.4  # more area for the lower portion of the eye area

    # get the X-coords for the left eye
    eye_left_xs = [scaled_landmarks[33,0] - x_padding * scale, scaled_landmarks[133,0] + x_padding * scale]
    # height of the eyebox is 0.75 of the width of the eyebox
    eye_left_height = math.fabs(eye_left_xs[0] - eye_left_xs[1]) * 0.75
    # get the Y-coords for the left eye
    eye_left_y = (scaled_landmarks[33,1] + scaled_landmarks[133,1]) / 2.0
    eye_left_ys = [eye_left_y - eye_left_height * y_0, eye_left_y + eye_left_height * y_1]

    # get the X-coords for the right eye
    eye_right_xs = [scaled_landmarks[362,0] - x_padding * scale, scaled_landmarks[263,0] + x_padding * scale]
    # height of the eyebox is 0.75 of the width of the eyebox
    eye_right_height = math.fabs(eye_right_xs[0] - eye_right_xs[1]) * 0.75
    # get the Y-coords for the right eye
    eye_right_y = (scaled_landmarks[362,1] + scaled_landmarks[263,1]) / 2.0
    eye_right_ys = [eye_right_y - eye_right_height * y_0, eye_right_y + eye_right_height * y_1]

    # get the eye coords for json files
    left_top_eye_left_point = [int(eye_left_xs[0]), int(eye_left_ys[0])]
    right_bottom_eye_left_point = [int(eye_left_xs[1]), int(eye_left_ys[1])]
    left_top_eye_right_point = [int(eye_right_xs[0]), int(eye_right_ys[0])]
    right_bottom_eye_right_point = [int(eye_right_xs[1]), int(eye_right_ys[1])]

    def usable(a,b):
        return bool(0 < a[0] < b[0] < image_width and 0 < a[1] < b[1] < image_height)
    face_info.left_eye_valid = usable(left_top_eye_left_point,right_bottom_eye_left_point)
    face_info.right_eye_valid = usable(left_top_eye_right_point,right_bottom_eye_right_point)
    def iris_available(start):
        return bool(len(coordinates)==478 and np.all(coordinates[start:start+5,:2] > 0)
                    and np.all(coordinates[start:start+5,:2] < 1))
    face_info.left_iris_valid = face_info.left_eye_valid and iris_available(468)
    face_info.right_iris_valid = face_info.right_eye_valid and iris_available(473)

    # Filter eyes out of image
    if (left_top_eye_left_point[0] <= 0) or (left_top_eye_left_point[1] <= 0) \
            or (right_bottom_eye_left_point[0] >= image_width) or (right_bottom_eye_left_point[1] >= image_height):
        face_info.can_gaze_estimation = False
        self.reset_filters()
        return face_info

    if (left_top_eye_right_point[0] <= 0) or (left_top_eye_right_point[1] <= 0) \
            or (right_bottom_eye_right_point[0] >= image_width) or (
            right_bottom_eye_right_point[1] >= image_height):
        face_info.can_gaze_estimation = False
        self.reset_filters()
        return face_info

    raw_face_rect = np.array([
        left_top_face_point[0],
        left_top_face_point[1],
        right_bottom_face_point[0] - left_top_face_point[0],
        right_bottom_face_point[1] - left_top_face_point[1],
    ], dtype=np.float64)

    raw_left_rect = np.array([
        left_top_eye_left_point[0],
        left_top_eye_left_point[1],
        right_bottom_eye_left_point[0] - left_top_eye_left_point[0],
        right_bottom_eye_left_point[1] - left_top_eye_left_point[1],
    ], dtype=np.float64)

    raw_right_rect = np.array([
        left_top_eye_right_point[0],
        left_top_eye_right_point[1],
        right_bottom_eye_right_point[0] - left_top_eye_right_point[0],
        right_bottom_eye_right_point[1] - left_top_eye_right_point[1],
    ], dtype=np.float64)

    if self.enable_filter:
        filtered_face_rect = self.face_rect_filter.filter(raw_face_rect, timestamp=timestamp)
        filtered_left_rect = self.left_rect_filter.filter(raw_left_rect, timestamp=timestamp)
        filtered_right_rect = self.right_rect_filter.filter(raw_right_rect, timestamp=timestamp)
        _face_mesh = self.landmarks_filter.filter(_face_mesh, timestamp=timestamp)

        fx, fy, fw, fh = filtered_face_rect
        lx, ly, lw, lh = filtered_left_rect
        rx, ry, rw, rh = filtered_right_rect

        fx = max(0, min(int(round(fx)), image_width - 1))
        fy = max(0, min(int(round(fy)), image_height - 1))
        fw = max(5, min(int(round(fw)), image_width - fx))
        fh = max(5, min(int(round(fh)), image_height - fy))

        lx = max(0, min(int(round(lx)), image_width - 1))
        ly = max(0, min(int(round(ly)), image_height - 1))
        lw = max(5, min(int(round(lw)), image_width - lx))
        lh = max(5, min(int(round(lh)), image_height - ly))

        rx = max(0, min(int(round(rx)), image_width - 1))
        ry = max(0, min(int(round(ry)), image_height - 1))
        rw = max(5, min(int(round(rw)), image_width - rx))
        rh = max(5, min(int(round(rh)), image_height - ry))

        face_info.face_rect = [fx, fy, fw, fh]
        face_info.left_rect = [lx, ly, lw, lh]
        face_info.right_rect = [rx, ry, rw, rh]
    else:
        face_info.face_rect = [int(v) for v in raw_face_rect]
        face_info.left_rect = [int(v) for v in raw_left_rect]
        face_info.right_rect = [int(v) for v in raw_right_rect]

    face_info.face_landmarks = _face_mesh
    face_info.can_gaze_estimation = True
    # print(f"Time cost in {time.time() - s_time} s")
    return face_info
