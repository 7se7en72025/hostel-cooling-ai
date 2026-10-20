"""Small actual one-hidden-layer neural regressor trained on synthetic sensations."""
import numpy as np


def features(temp, rh, speed):
    return np.asarray([(temp-28)/6, (rh-55)/30, speed/1.5], dtype=float)


class ComfortANN:
    def __init__(self, seed=1701):
        rng = np.random.default_rng(seed)
        x = rng.uniform(-1, 1, (2400, 3))
        # Synthetic supervision, generated independently from the fuzzy controller.
        temp, rh, speed = 28+x[:,0]*6, 55+x[:,1]*30, (x[:,2]+1)*.75
        x[:,2] = speed/1.5
        relief = np.where(temp > 25, 1.8*np.sqrt(np.maximum(0, speed-.1)), 0)
        y = np.clip((temp-relief+.025*np.maximum(0, rh-55)-28)/1.8, -3, 3)[:, None]
        y += rng.normal(0, .08, y.shape)
        # First 2000 train, last 400 held out; evaluation room trajectories never used here.
        xt, yt = x[:2000], y[:2000]
        self.w1 = rng.normal(0, .4, (3, 12)); self.b1 = np.zeros((1, 12))
        self.w2 = rng.normal(0, .2, (12, 1)); self.b2 = np.zeros((1, 1))
        for _ in range(700):
            h = np.tanh(xt @ self.w1 + self.b1)
            prediction = h @ self.w2 + self.b2
            dy = 2*(prediction-yt)/len(xt)
            dh = (dy @ self.w2.T)*(1-h*h)
            self.w1 -= .06*(xt.T @ dh); self.b1 -= .06*dh.sum(axis=0, keepdims=True)
            self.w2 -= .06*(h.T @ dy); self.b2 -= .06*dy.sum(axis=0, keepdims=True)
        pred = self.predict_features(x[2000:])
        self.validation = {"data": "synthetic iid holdout, not human votes", "train_n": 2000, "test_n": 400,
                           "mae_tsv": float(np.mean(abs(pred-y[2000:]))), "seed": seed}

    def predict_features(self, x):
        return np.clip(np.tanh(x @ self.w1 + self.b1) @ self.w2 + self.b2, -3, 3)

    def predict(self, c, room, action):
        speed = room.fan_speed_ms[action.fan] + .1*action.window*c.wind_ms
        return float(self.predict_features(features(c.indoor_c, c.rh, speed)).item())
