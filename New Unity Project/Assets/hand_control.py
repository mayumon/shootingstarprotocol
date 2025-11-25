import cv2
import mediapipe as mp
import math
import sys

print("python script started", flush=True)

# camera
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    model_complexity=1,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.5
)
mp_drawing = mp.solutions.drawing_utils

last_all_hands = []
last_labeled_hands = []   # (landmarks, 'Left'/'Right')
last_bow_hand = None      # right hand used (bow)
frame_count = 0
DETECT_EVERY = 1          # framerate

# bow state
PINCH_THRESHOLD = 0.05     # distance for pinch
MAX_PULL = 0.30            # max x distance for full charge
MIN_PINCH_FRAMES = 5       # min frames pinched to count
MIN_SHOT_STRENGTH = 0.10   # ignore very weak shots

is_pinching_prev = False
pinch_frames = 0
pull_start_x = None
charge_strength = 0.0      # 0.0–1.0
last_shot_strength = 0.0
state = "IDLE"             # idle, loaded, charging, shot
shot_timer = 0             # frames to show 'shot'

# joystick (left hand)
joystick_vector = [0.0, 0.0]   # current vector
last_wrist_pos = None          # last smoothed joint position

# joystick tuning
JOYSTICK_SENSITIVITY = 1.5     # impulse per movement
MAX_VEC = 0.04                 # max vector magnitude
SMOOTHING = 0.6                # joint smoothing factor
JITTER_DEADZONE = 0.004        # ignore tiny movement
MOMENTUM = 0.75                # keep part of previous vector

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # mirror frame
    frame = cv2.flip(frame, 1)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_count += 1

    # run mediapipe periodically
    if frame_count % DETECT_EVERY == 0:
        frame_rgb.flags.writeable = False
        results = hands.process(frame_rgb)
        frame_rgb.flags.writeable = True

        last_all_hands = []
        last_labeled_hands = []
        last_bow_hand = None

        if results.multi_hand_landmarks:
            if results.multi_handedness:
                for lm, handedness in zip(results.multi_hand_landmarks,
                                          results.multi_handedness):
                    label = handedness.classification[0].label  # 'Left' or 'Right'
                    last_all_hands.append(lm)
                    last_labeled_hands.append((lm, label))

                    # pick right hand as bow hand
                    if label == 'Right' and last_bow_hand is None:
                        last_bow_hand = lm
            else:
                last_all_hands = results.multi_hand_landmarks

    # draw all hands
    for hl in last_all_hands:
        mp_drawing.draw_landmarks(
            frame,
            hl,
            mp_hands.HAND_CONNECTIONS
        )

    # --- bow (right hand) logic ---
    is_pinching = False
    bow_hand_index_x = None

    if last_bow_hand is not None:
        hand_landmarks = last_bow_hand

        index_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
        thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]

        dx = index_tip.x - thumb_tip.x
        dy = index_tip.y - thumb_tip.y
        pinch_dist = math.sqrt(dx * dx + dy * dy)

        is_pinching = pinch_dist < PINCH_THRESHOLD
        bow_hand_index_x = index_tip.x

    # start loading
    if is_pinching and not is_pinching_prev and bow_hand_index_x is not None:
        pull_start_x = bow_hand_index_x
        charge_strength = 0.0
        state = "LOADED"
        shot_timer = 0

    # update charge while pinching
    if is_pinching and bow_hand_index_x is not None and pull_start_x is not None:
        dx_pull = bow_hand_index_x - pull_start_x
        pull_amount = max(0.0, dx_pull)
        charge_strength = max(0.0, min(1.0, pull_amount / MAX_PULL))

        if charge_strength > 0.05:
            state = "CHARGING"
        else:
            state = "LOADED"

    # release: possible shot
    if not is_pinching and is_pinching_prev:
        if pinch_frames >= MIN_PINCH_FRAMES and charge_strength >= MIN_SHOT_STRENGTH:
            state = "SHOT"
            last_shot_strength = charge_strength
            shot_timer = 30
        else:
            state = "IDLE"

        charge_strength = 0.0
        pull_start_x = None

    # timeout for shot state
    if state == "SHOT":
        if shot_timer > 0:
            shot_timer -= 1
        else:
            state = "IDLE"

    # update pinch frame counter
    if is_pinching:
        pinch_frames += 1
    else:
        pinch_frames = 0

    is_pinching_prev = is_pinching

    # --- two-hand heart ---
    heart_active = False

    if len(last_labeled_hands) >= 2:
        left_hand_lm = None
        right_hand_lm = None

        for lm, label in last_labeled_hands:
            if label == 'Left' and left_hand_lm is None:
                left_hand_lm = lm
            elif label == 'Right' and right_hand_lm is None:
                right_hand_lm = lm

        if left_hand_lm is None or right_hand_lm is None:
            if len(last_all_hands) >= 2:
                left_hand_lm = last_all_hands[0]
                right_hand_lm = last_all_hands[1]

        if left_hand_lm is not None and right_hand_lm is not None:
            li_tip = left_hand_lm.landmark[8]
            ri_tip = right_hand_lm.landmark[8]
            lt_tip = left_hand_lm.landmark[4]
            rt_tip = right_hand_lm.landmark[4]

            li_pip = left_hand_lm.landmark[6]
            ri_pip = right_hand_lm.landmark[6]

            li_dip = left_hand_lm.landmark[7]
            li_mcp = left_hand_lm.landmark[5]
            ri_dip = right_hand_lm.landmark[7]
            ri_mcp = right_hand_lm.landmark[5]

            INDEX_DIST_MAX = 0.05
            THUMB_DIST_MAX = 0.05
            DRIFT_ALLOWANCE = 0.01

            idx_dist = math.dist((li_tip.x, li_tip.y), (ri_tip.x, ri_tip.y))
            thumb_dist = math.dist((lt_tip.x, lt_tip.y), (rt_tip.x, rt_tip.y))

            index_close = idx_dist < INDEX_DIST_MAX
            thumbs_close = thumb_dist < THUMB_DIST_MAX

            li_good_curve = li_pip.y < li_tip.y + DRIFT_ALLOWANCE
            ri_good_curve = ri_pip.y < ri_tip.y + DRIFT_ALLOWANCE

            thumb_mid_y = (lt_tip.y + rt_tip.y) * 0.5
            all_index_y = [
                li_tip.y, li_pip.y, li_dip.y, li_mcp.y,
                ri_tip.y, ri_pip.y, ri_dip.y, ri_mcp.y
            ]
            thumbs_below = thumb_mid_y > max(all_index_y) - DRIFT_ALLOWANCE

            heart_active = (
                index_close and
                thumbs_close and
                li_good_curve and
                ri_good_curve
                and thumbs_below
            )

    # --- left hand joystick vector ---
    left_hand_lm = None
    for lm, label in last_labeled_hands:
        if label == "Left":
            left_hand_lm = lm
            break

    origin_px = None

    if left_hand_lm is not None:
        joint = left_hand_lm.landmark[5]

        h, w = frame.shape[0], frame.shape[1]
        origin_px = (int(w * joint.x), int(h * joint.y))

        # init smoothed position
        if last_wrist_pos is None:
            last_wrist_pos = (joint.x, joint.y)

        # low-pass filter
        smoothed_x = last_wrist_pos[0] * SMOOTHING + joint.x * (1 - SMOOTHING)
        smoothed_y = last_wrist_pos[1] * SMOOTHING + joint.y * (1 - SMOOTHING)

        # movement of smoothed joint
        dx = smoothed_x - last_wrist_pos[0]
        dy = smoothed_y - last_wrist_pos[1]

        # update memory
        last_wrist_pos = (smoothed_x, smoothed_y)

        # ignore small jitter
        if abs(dx) < JITTER_DEADZONE:
            dx = 0.0
        if abs(dy) < JITTER_DEADZONE:
            dy = 0.0

        # momentum + impulse
        joystick_vector[0] = joystick_vector[0] * MOMENTUM + dx * JOYSTICK_SENSITIVITY
        joystick_vector[1] = joystick_vector[1] * MOMENTUM + dy * JOYSTICK_SENSITIVITY

    else:
        # no left hand: decay vector
        last_wrist_pos = None
        joystick_vector[0] *= MOMENTUM
        joystick_vector[1] *= MOMENTUM

    # clamp joystick magnitude
    mag = math.sqrt(joystick_vector[0] ** 2 + joystick_vector[1] ** 2)
    if mag > MAX_VEC and mag > 0:
        joystick_vector[0] = joystick_vector[0] / mag * MAX_VEC
        joystick_vector[1] = joystick_vector[1] / mag * MAX_VEC

    # send vx vy to unity
    sys.stdout.write(f"{joystick_vector[0]} {joystick_vector[1]}\n")
    sys.stdout.flush()

    # text overlays
    overlay_text = ""
    if state == "LOADED":
        overlay_text = "LOADED ARROW"
    elif state == "CHARGING":
        overlay_text = f"CHARGING - STRENGTH {int(charge_strength * 100)}%"
    elif state == "SHOT":
        overlay_text = f"SHOT - STRENGTH {int(last_shot_strength * 100)}%"

    if overlay_text:
        cv2.putText(
            frame,
            overlay_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (130, 90, 255),
            2,
            cv2.LINE_AA
        )

    if heart_active:
        cv2.putText(
            frame,
            "HEART",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 200, 255),
            2,
            cv2.LINE_AA
        )

    # --- draw joystick arrow (left hand) ---
    if origin_px is not None:
        vx = joystick_vector[0]
        vy = joystick_vector[1]

        ARROW_SCALE = 750
        end_x = int(origin_px[0] + vx * ARROW_SCALE)
        end_y = int(origin_px[1] + vy * ARROW_SCALE)

        cv2.arrowedLine(
            frame,
            origin_px,
            (end_x, end_y),
            (0, 255, 0),
            4,
            tipLength=0.25
        )

        cv2.putText(
            frame,
            f"{vx:.3f}, {vy:.3f}",
            (origin_px[0] + 10, origin_px[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.2,
            (0, 255, 0),
            1,
            cv2.LINE_AA
        )

    # upscale window
    big_frame = cv2.resize(frame, (960, 720), interpolation=cv2.INTER_LINEAR)
    cv2.imshow('meow', big_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
