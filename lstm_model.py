import numpy as np
from collections import deque
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.optimizers import Adam

SEQ_LEN   = 10     # look-back window
THRESHOLD = 2.0    # normalised z-score threshold for anomaly


class CrowdLSTM:
    """Per-camera LSTM anomaly detector.  Instantiate one per camera."""

    def __init__(self):
        self._history: deque = deque(maxlen=SEQ_LEN * 2)
        self._model = None

    # ── private ──────────────────────────────────────────────────────────────
    def _build_model(self):
        m = Sequential([
            LSTM(16, input_shape=(SEQ_LEN, 1)),
            Dense(1),
        ])
        m.compile(optimizer=Adam(0.01), loss="mse")
        return m

    def _get_model(self):
        if self._model is None:
            self._model = self._build_model()
        return self._model

    # ── public ───────────────────────────────────────────────────────────────
    def update_and_detect(self, count: int) -> tuple[bool, str]:
        """
        Append count to history, run one-step online LSTM fit,
        return (anomaly: bool, reason: str).
        """
        if count < 3:          # avoid false spikes at near-zero occupancy
            return False, ""

        self._history.append(float(count))

        if len(self._history) < SEQ_LEN + 1:
            return False, ""

        arr  = np.array(self._history, dtype=np.float32)
        mu, sigma = arr.mean(), arr.std() + 1e-6
        norm = (arr - mu) / sigma

        X      = norm[:-1][-SEQ_LEN:].reshape(1, SEQ_LEN, 1)
        y_true = norm[-1]

        mdl = self._get_model()
        try:
            # Only train every few steps to avoid blocking the video stream
            if len(self._history) % 5 == 0:
                mdl.fit(X, np.array([[y_true]]), epochs=1, verbose=0)
            
            y_pred   = float(mdl.predict(X, verbose=0)[0][0])
            residual = abs(y_true - y_pred)

            if residual > THRESHOLD:
                return True, f"spike detected (residual={residual:.2f})"
        except Exception as e:
            print(f"[LSTM] Inference error: {e}")
        
        return False, ""



# ── backward-compatible module-level API ─────────────────────────────────────
_default_lstm = CrowdLSTM()


def update_and_detect(count: int) -> tuple[bool, str]:
    return _default_lstm.update_and_detect(count)
