"""Train a plant or bird image classifier that BioTrace can load.

Produces exactly the artifacts ``backend/app/services/predictor.py`` expects:

    <output>/model.pt          torch checkpoint (state_dict + class names + metadata)
    <output>/model_card.json   version, threshold, metrics, dataset description

The dataset directory must contain one sub-directory per class, named with the
scientific name used in ``backend/app/data/species_seed.json``:

    datasets/plants/
        Azadirachta indica/
        Bauhinia variegata/

Usage (from the project root):

    python -m backend.scripts.train_classifier \
        --category plant --data datasets/plants --epochs 8 --output models/plant

PyTorch is imported lazily so ``--help`` works without the ~2 GB dependency.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SPECIES_FILE = PROJECT_ROOT / "backend" / "app" / "data" / "species_seed.json"
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
IMAGE_SIZE = 224


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a MobileNetV3 classifier and write BioTrace model artifacts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--category", required=True, choices=["plant", "bird"])
    parser.add_argument("--data", required=True, type=Path, help="ImageFolder root.")
    parser.add_argument("--output", type=Path, help="Defaults to models/<category>.")
    parser.add_argument("--arch", default="mobilenet_v3_small",
                        choices=["mobilenet_v3_small", "mobilenet_v3_large"])
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-workers", type=int, default=0,
                        help="Keep 0 on Windows.")
    parser.add_argument("--max-error", type=float, default=0.10,
                        help="Target error rate when choosing the abstention threshold.")
    parser.add_argument("--version", default=None,
                        help="Defaults to demo-<arch>-v1.")
    return parser.parse_args(argv)


def _macro_f1(y_true: list[int], y_pred: list[int], num_classes: int) -> float:
    """Macro F1 without a scikit-learn dependency."""
    scores = []
    for label in range(num_classes):
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        if tp == 0 and fp == 0 and fn == 0:
            continue
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _choose_threshold(
    confidences: list[float], correct: list[bool], max_error: float
) -> tuple[float, float, float]:
    """Pick the lowest threshold whose accepted answers stay under ``max_error``.

    Returns ``(threshold, coverage, error_rate)`` at that threshold. If no
    threshold is safe, the highest one is returned with its measured error.
    """
    best = (0.95, 0.0, 0.0)
    for step in range(30, 96, 5):
        threshold = step / 100
        accepted = [c for c, ok in zip(confidences, correct) if c >= threshold]
        if not accepted:
            continue
        errors = sum(1 for c, ok in zip(confidences, correct) if c >= threshold and not ok)
        error_rate = errors / len(accepted)
        if error_rate <= max_error:
            best = (threshold, len(accepted) / len(confidences), error_rate)
            break
        best = (threshold, len(accepted) / len(confidences), error_rate)
    return best


def _warn_unknown_classes(class_names: list[str], category: str) -> None:
    try:
        records = json.loads(SPECIES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    known = {
        record["scientific_name"].strip().lower()
        for record in records
        if record.get("category") == category
    }
    unknown = [name for name in class_names if name.strip().lower() not in known]
    if unknown:
        print(
            "WARNING: these classes are not in species_seed.json and will show "
            f"without catalogue metadata: {', '.join(unknown)}",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, Subset
        from torchvision import datasets, models, transforms
    except ImportError:
        print(
            "PyTorch is not installed. Run:\n"
            "  pip install torch torchvision --index-url "
            "https://download.pytorch.org/whl/cpu",
            file=sys.stderr,
        )
        return 2

    data_dir: Path = args.data
    if not data_dir.is_dir():
        print(f"Dataset directory not found: {data_dir}", file=sys.stderr)
        return 2

    output: Path = args.output or PROJECT_ROOT / "models" / args.category
    output.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(args.seed)
    random.seed(args.seed)

    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.65, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.15),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    eval_transform = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )

    base = datasets.ImageFolder(str(data_dir))
    class_names = list(base.classes)
    if len(class_names) < 2:
        print("Need at least two class sub-directories to train.", file=sys.stderr)
        return 2
    _warn_unknown_classes(class_names, args.category)

    # One deterministic split, shared by the two transform views.
    indices = list(range(len(base)))
    random.Random(args.seed).shuffle(indices)
    val_size = max(1, int(len(indices) * args.val_split))
    val_indices, train_indices = indices[:val_size], indices[val_size:]

    train_set = Subset(datasets.ImageFolder(str(data_dir), transform=train_transform), train_indices)
    val_set = Subset(datasets.ImageFolder(str(data_dir), transform=eval_transform), val_indices)

    # Class weights keep an imbalanced demo dataset from collapsing to one label.
    train_labels = [base.targets[i] for i in train_indices]
    counts = torch.bincount(torch.tensor(train_labels), minlength=len(class_names)).float()
    weights = (counts.sum() / (counts.clamp(min=1) * len(class_names))).tolist()

    train_loader = DataLoader(
        train_set, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers
    )
    val_loader = DataLoader(
        val_set, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers
    )

    if args.arch == "mobilenet_v3_large":
        net = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.DEFAULT)
    else:
        net = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    in_features = net.classifier[-1].in_features
    net.classifier[-1] = nn.Linear(in_features, len(class_names))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net.to(device)

    criterion = nn.CrossEntropyLoss(weight=torch.tensor(weights, device=device))
    optimizer = torch.optim.AdamW(
        [p for p in net.parameters() if p.requires_grad], lr=args.lr, weight_decay=1e-4
    )

    def run_epoch(loader, training: bool) -> tuple[float, float, list[int], list[int], list[float]]:
        net.train(training)
        total_loss, correct, seen = 0.0, 0, 0
        y_true, y_pred, top_conf = [], [], []
        with torch.set_grad_enabled(training):
            for images, targets in loader:
                images, targets = images.to(device), targets.to(device)
                logits = net(images)
                loss = criterion(logits, targets)
                if training:
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()
                probs = torch.softmax(logits, dim=1)
                confidence, predicted = probs.max(dim=1)
                total_loss += float(loss) * len(targets)
                correct += int((predicted == targets).sum())
                seen += len(targets)
                y_true.extend(targets.tolist())
                y_pred.extend(predicted.tolist())
                top_conf.extend(confidence.tolist())
        return (total_loss / max(1, seen), correct / max(1, seen), y_true, y_pred, top_conf)

    best_accuracy = -1.0
    best_state = None
    for epoch in range(1, args.epochs + 1):
        # Warm up the new head with the backbone frozen, then fine-tune.
        if epoch == 2:
            for param in net.parameters():
                param.requires_grad = True
            optimizer = torch.optim.AdamW(net.parameters(), lr=args.lr / 5, weight_decay=1e-4)

        train_loss, train_acc, _, _, _ = run_epoch(train_loader, training=True)
        val_loss, val_acc, y_true, y_pred, conf = run_epoch(val_loader, training=False)
        macro = _macro_f1(y_true, y_pred, len(class_names))
        print(
            f"epoch {epoch}/{args.epochs}  train_loss={train_loss:.4f} "
            f"train_acc={train_acc:.3f}  val_loss={val_loss:.4f} "
            f"val_acc={val_acc:.3f}  macro_f1={macro:.3f}"
        )
        if val_acc > best_accuracy:
            best_accuracy = val_acc
            best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
            best_truth, best_pred, best_conf = y_true, y_pred, conf

    assert best_state is not None
    net.load_state_dict(best_state)

    correct = [t == p for t, p in zip(best_truth, best_pred)]
    threshold, coverage, error_rate = _choose_threshold(best_conf, correct, args.max_error)
    macro_f1 = _macro_f1(best_truth, best_pred, len(class_names))

    version = args.version or f"demo-{args.arch.replace('_', '-')}-v1"
    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    checkpoint = {
        "state_dict": best_state,
        "class_names": class_names,
        "architecture": args.arch,
        "metadata": {
            "version": version,
            "temperature": 1.0,
            "abstention_threshold": threshold,
            "trained_at": trained_at,
            "test_metrics": {
                "accuracy": round(best_accuracy, 4),
                "macro_f1": round(macro_f1, 4),
                "val_size": len(val_indices),
            },
        },
    }
    model_path = output / "model.pt"
    torch.save(checkpoint, model_path)

    card = {
        "version": version,
        "architecture": args.arch,
        "class_names": class_names,
        "temperature": 1.0,
        "abstention_threshold": threshold,
        "trained_at": trained_at,
        "dataset": {
            "name": str(data_dir),
            "images": len(base),
            "classes": len(class_names),
            "val_split": args.val_split,
        },
        "test_metrics": {
            "accuracy": round(best_accuracy, 4),
            "macro_f1": round(macro_f1, 4),
            "val_size": len(val_indices),
        },
        "calibration": {
            "coverage_at_threshold": round(coverage, 4),
            "error_rate_at_threshold": round(error_rate, 4),
            "target_max_error": args.max_error,
        },
        "notes": (
            "Trained by backend/scripts/train_classifier.py on a small dataset. "
            "Use as a screening aid, not as verified identification."
        ),
    }
    (output / "model_card.json").write_text(
        json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"\nWrote {model_path}")
    print(f"Wrote {output / 'model_card.json'}")
    print(
        f"Best val accuracy {best_accuracy:.3f}, macro F1 {macro_f1:.3f}. "
        f"Abstention threshold {threshold:.2f} (coverage {coverage:.0%}, "
        f"accepted error {error_rate:.1%})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
