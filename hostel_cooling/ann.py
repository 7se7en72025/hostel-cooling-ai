"""Small actual one-hidden-layer neural regressor trained on synthetic sensations."""

import numpy as np
import json
from pathlib import Path


def features(temp, rh, speed):
    return np.asarray([(temp - 28) / 6, (rh - 55) / 30, speed / 1.5], dtype=float)


class ComfortANN:
    def __init__(self, seed=1701):
        rng = np.random.default_rng(seed)
        x = rng.uniform(-1, 1, (2400, 3))
        # Synthetic supervision, generated independently from the fuzzy controller.
        temp, rh, speed = 28 + x[:, 0] * 6, 55 + x[:, 1] * 30, (x[:, 2] + 1) * 0.75
        x[:, 2] = speed / 1.5
        relief = np.where(temp > 25, 1.8 * np.sqrt(np.maximum(0, speed - 0.1)), 0)
        y = np.clip((temp - relief + 0.025 * np.maximum(0, rh - 55) - 28) / 1.8, -3, 3)[
            :, None
        ]
        y += rng.normal(0, 0.08, y.shape)
        self.training_data = np.column_stack((x, y))
        # First 2000 train, last 400 held out; evaluation room trajectories never used here.
        xt, yt = x[:2000], y[:2000]
        self.w1 = rng.normal(0, 0.4, (3, 12))
        self.b1 = np.zeros((1, 12))
        self.w2 = rng.normal(0, 0.2, (12, 1))
        self.b2 = np.zeros((1, 1))
        self.loss_history = []
        for epoch in range(700):
            h = np.tanh(xt @ self.w1 + self.b1)
            prediction = h @ self.w2 + self.b2
            if epoch % 10 == 0:
                self.loss_history.append(
                    {"epoch": epoch, "mse": float(np.mean((prediction - yt) ** 2))}
                )
            dy = 2 * (prediction - yt) / len(xt)
            dh = (dy @ self.w2.T) * (1 - h * h)
            self.w1 -= 0.06 * (xt.T @ dh)
            self.b1 -= 0.06 * dh.sum(axis=0, keepdims=True)
            self.w2 -= 0.06 * (h.T @ dy)
            self.b2 -= 0.06 * dy.sum(axis=0, keepdims=True)
        pred = self.predict_features(x[2000:])
        self.validation = {
            "data": "synthetic iid holdout, not human votes",
            "train_n": 2000,
            "test_n": 400,
            "mae_tsv": float(np.mean(abs(pred - y[2000:]))),
            "seed": seed,
        }

    def predict_features(self, x):
        return np.clip(np.tanh(x @ self.w1 + self.b1) @ self.w2 + self.b2, -3, 3)

    def predict(self, c, room, action):
        speed = room.fan_speed_ms[action.fan] + 0.1 * action.window * c.wind_ms
        return float(self.predict_features(features(c.indoor_c, c.rh, speed)).item())

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            w1=self.w1,
            b1=self.b1,
            w2=self.w2,
            b2=self.b2,
            metadata=json.dumps(self.validation),
        )

    @classmethod
    def load(cls, path):
        model = cls.__new__(cls)
        with np.load(path, allow_pickle=False) as data:
            for key in ("w1", "b1", "w2", "b2"):
                setattr(model, key, data[key])
            model.validation = json.loads(str(data["metadata"]))
        return model
