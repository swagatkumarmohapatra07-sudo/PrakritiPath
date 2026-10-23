"""Species classifier registry and inference.

The registry loads torch checkpoints produced by ``scripts/train_classifier.py``.
PyTorch is imported lazily so the web app (and most tests) can run without the
~2 GB AI dependency. When no checkpoint exists, the API returns an explicit
"model unavailable" response instead of a fabricated prediction.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from ..config import settings

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
IMAGE_SIZE = 224

DEFAULT_LIMITATIONS = [
    "Trained on a small demonstration dataset; it does not cover all Odisha flora or avifauna.",
    "Confidence is the model's softmax score, not the probability that the label is correct.",
    "Look-alike species, juveniles, hybrids and damaged specimens are common failure cases.",
    "Photos taken from far away, at night, or with strong backlighting are unreliable.",
    "A prediction is a screening aid and must be reviewed by a qualified person before it is treated as a biodiversity record.",
]


@dataclass
class LoadedModel:
    category: str
    version: str
    class_names: list[str]
    model: Any
    temperature: float = 1.0
    threshold: float = 0.55
    metrics: dict[str, Any] = field(default_factory=dict)
    trained_at: str | None = None
    dataset: dict[str, Any] | None = None
    architecture: str = "mobilenet_v3_small"


class ModelNotAvailable(Exception):
    def __init__(self, category: str, reason: str) -> None:
        super().__init__(reason)
        self.category = category
        self.reason = reason


class PredictorRegistry:
    """Thread-safe, lazily loaded registry for one model per category."""

    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = model_dir or settings.model_dir
        self._models: dict[str, LoadedModel | None] = {}
        self._errors: dict[str, str] = {}
        self._lock = threading.RLock()
        self._torch_missing = False

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def _artifact_paths(self, category: str) -> tuple[Path, Path]:
        base = self.model_dir / category
        return base / "model.pt", base / "model_card.json"

    def _load(self, category: str) -> LoadedModel:
        model_path, card_path = self._artifact_paths(category)
        if not model_path.exists():
            raise ModelNotAvailable(
                category,
                (
                    f"No trained {category} model is installed at "
                    f"'{model_path.relative_to(settings.model_dir.parent)}'. "
                    "Train one with scripts/train_classifier.py (see docs/MODEL_TRAINING.md). "
                    "The rest of BioTrace works without it."
                ),
            )

        try:
            import torch
            import torch.nn as nn
            from torchvision import models, transforms
        except ImportError as exc:  # pragma: no cover - environment dependent
            self._torch_missing = True
            raise ModelNotAvailable(
                category,
                "PyTorch is not installed. Run: pip install torch torchvision "
                "--index-url https://download.pytorch.org/whl/cpu",
            ) from exc

        card: dict[str, Any] = {}
        if card_path.exists():
            card = json.loads(card_path.read_text(encoding="utf-8"))
        class_names: list[str] = card.get("class_names", [])
        architecture = card.get("architecture", "mobilenet_v3_small")

        checkpoint = torch.load(str(model_path), map_location="cpu", weights_only=False)
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
            class_names = checkpoint.get("class_names", class_names)
            architecture = checkpoint.get("architecture", architecture)
            extra = checkpoint.get("metadata", {})
        else:  # raw state dict
            state_dict = checkpoint
            extra = {}

        if not class_names:
            raise ModelNotAvailable(
                category,
                "Model file found but its class-name mapping is missing. "
                "Retrain with scripts/train_classifier.py.",
            )

        if architecture.startswith("mobilenet_v3_small"):
            net = models.mobilenet_v3_small(weights=None)
            in_features = net.classifier[-1].in_features
            net.classifier[-1] = nn.Linear(in_features, len(class_names))
        elif architecture.startswith("mobilenet_v3_large"):
            net = models.mobilenet_v3_large(weights=None)
            in_features = net.classifier[-1].in_features
            net.classifier[-1] = nn.Linear(in_features, len(class_names))
        else:
            raise ModelNotAvailable(category, f"Unsupported architecture '{architecture}'.")

        net.load_state_dict(state_dict)
        net.eval()

        loaded = LoadedModel(
            category=category,
            version=card.get("version")
            or extra.get("version")
            or f"{category}-model-{datetime.now(timezone.utc):%Y%m%d}",
            class_names=class_names,
            model=net,
            temperature=float(card.get("temperature", extra.get("temperature", 1.0)) or 1.0),
            threshold=float(
                card.get("abstention_threshold", extra.get("abstention_threshold", settings.min_confidence))
            ),
            metrics=card.get("test_metrics", extra.get("test_metrics", {})),
            trained_at=card.get("trained_at") or extra.get("trained_at"),
            dataset=card.get("dataset"),
            architecture=architecture,
        )

        self._transforms = transforms.Compose(
            [
                transforms.Resize(256),
                transforms.CenterCrop(IMAGE_SIZE),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )
        return loaded

    def get(self, category: str) -> LoadedModel:
        if category not in {"plant", "bird"}:
            raise ModelNotAvailable(category, f"Unknown category '{category}'.")
        with self._lock:
            if category in self._models:
                loaded = self._models[category]
                if loaded is None:
                    raise ModelNotAvailable(category, self._errors.get(category, "unavailable"))
                return loaded
            try:
                loaded = self._load(category)
                self._models[category] = loaded
                self._errors.pop(category, None)
                return loaded
            except ModelNotAvailable as exc:
                self._models[category] = None
                self._errors[category] = exc.reason
                raise

    def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for category in ("plant", "bird"):
            model_path, _ = self._artifact_paths(category)
            entry: dict[str, Any] = {
                "installed": model_path.exists(),
                "path": str(model_path.relative_to(settings.model_dir.parent)),
            }
            try:
                loaded = self.get(category)
                entry.update(
                    {
                        "available": True,
                        "version": loaded.version,
                        "classes": len(loaded.class_names),
                        "threshold": loaded.threshold,
                        "trained_at": loaded.trained_at,
                        "test_metrics": loaded.metrics,
                    }
                )
            except ModelNotAvailable as exc:
                entry.update({"available": False, "reason": exc.reason})
            out[category] = entry
        out["torch_installed"] = not self._torch_missing
        return out

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #
    def predict(self, image: Image.Image, category: str, top_k: int = 3) -> dict[str, Any]:
        loaded = self.get(category)
        import torch

        tensor = self._transforms(image).unsqueeze(0)
        with self._lock, torch.inference_mode():
            logits = loaded.model(tensor)
            if loaded.temperature and loaded.temperature > 0:
                logits = logits / loaded.temperature
            probabilities = torch.softmax(logits, dim=1)[0]

        k = min(top_k, len(loaded.class_names))
        scores, indices = torch.topk(probabilities, k)
        predictions = [
            {
                "label": loaded.class_names[int(index)],
                "confidence": round(float(score), 4),
            }
            for score, index in zip(scores.tolist(), indices.tolist())
        ]
        top = predictions[0]
        margin = (
            round(predictions[0]["confidence"] - predictions[1]["confidence"], 4)
            if len(predictions) > 1
            else None
        )
        return {
            "model_version": loaded.version,
            "predictions": predictions,
            "confidence": top["confidence"],
            "margin": margin,
            "threshold": loaded.threshold,
            "temperature": loaded.temperature,
            "limitations": DEFAULT_LIMITATIONS,
            "metrics": loaded.metrics,
            "model_card": {
                "version": loaded.version,
                "architecture": loaded.architecture,
                "classes": loaded.class_names,
                "trained_at": loaded.trained_at,
                "dataset": loaded.dataset,
                "test_metrics": loaded.metrics,
                "temperature": loaded.temperature,
                "threshold": loaded.threshold,
            },
            "class_names": loaded.class_names,
        }


registry = PredictorRegistry()
