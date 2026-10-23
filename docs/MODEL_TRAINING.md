# Model training

BioTrace ships **without** trained weights. Predictions are an optional extra: when
`models/plant/model.pt` or `models/bird/model.pt` is missing, the API returns
`decision: "unavailable"` and the rest of the app keeps working.

This document describes the exact artifact contract the inference registry expects,
and how to produce a model that satisfies it.

## Artifact contract

`backend/app/services/predictor.py` loads one model per category:

```
models/
  plant/
    model.pt          # torch checkpoint
    model_card.json   # class names + calibration metadata
  bird/
    model.pt
    model_card.json
```

### `model.pt`

Either a raw `state_dict` **or** — preferred — a checkpoint dictionary:

```python
{
    "state_dict": model.state_dict(),
    "class_names": ["Pavo cristatus", "Corvus splendens", ...],
    "architecture": "mobilenet_v3_small",
    "metadata": {
        "version": "demo-mobilenetv3-v1",
        "temperature": 1.2,
        "abstention_threshold": 0.55,
        "trained_at": "2026-01-15T10:00:00+00:00",
        "test_metrics": {"accuracy": 0.71, "macro_f1": 0.68},
    },
}
```

Supported architectures: `mobilenet_v3_small` and `mobilenet_v3_large`. The final
linear layer is replaced with `len(class_names)` outputs before loading the weights.

### `model_card.json`

```json
{
  "version": "demo-mobilenetv3-v1",
  "architecture": "mobilenet_v3_small",
  "class_names": ["Pavo cristatus", "Corvus splendens"],
  "temperature": 1.2,
  "abstention_threshold": 0.55,
  "trained_at": "2026-01-15T10:00:00+00:00",
  "dataset": {
    "name": "your-dataset",
    "images": 1200,
    "licence": "..."
  },
  "test_metrics": {
    "accuracy": 0.71,
    "macro_f1": 0.68
  }
}
```

`class_names` **must** use the exact `scientific_name` strings in
`backend/app/data/species_seed.json`. That is how a predicted label is joined to the
catalogue (common name, conservation status, distribution). Unmatched labels are
still returned, but without catalogue metadata.

## Preprocessing

Inference uses ImageNet-style preprocessing, so training must match it:

```python
transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])
```

## Training

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-ai.txt

python -m backend.scripts.train_classifier \
    --category plant \
    --data datasets/plants \
    --epochs 8 \
    --batch-size 32 \
    --output models/plant
```

The dataset directory must contain one sub-directory per class, named with the
scientific name:

```
datasets/plants/
  Azadirachta indica/
  Bauhinia variegata/
  ...
```

The script is CPU-friendly: it uses `mobilenet_v3_small` by default, freezes the
feature extractor for the first epoch and then fine-tunes. It writes `model.pt` and
`model_card.json` into `--output`, so the app picks the model up on the next restart.

## Abstention threshold

`abstention_threshold` is what turns a confident-looking softmax into an honest
"needs review". Choose it on a **validation** split, not the test split:

1. Sweep thresholds from 0.30 to 0.95.
2. Pick the value that maximises coverage subject to an acceptable error rate on
   accepted predictions.
3. Record it in `model_card.json`; override ad hoc with `BIOTRACE_MIN_CONFIDENCE`.

The API never hides a low score: predictions below the threshold are returned with
`decision: "review"` and an explanation, not silently dropped.

## Verifying installation

```bash
python -m pytest backend/tests/test_biodiversity.py
curl http://127.0.0.1:8000/api/biodiversity/model-status
```

When a model is installed, `model-status` reports `available: true`, the version, the
class count and the recorded metrics. If loading fails, the error message is exposed
in `reason` — BioTrace does not fall back to a fake label.

## Honest metrics

Report what you measured: dataset size, class balance, split strategy and the
confusion matrix. A small demonstration model with ~70% top-1 accuracy is useful as a
screening aid and should be documented as such. Do not describe it as production-grade
identification.
