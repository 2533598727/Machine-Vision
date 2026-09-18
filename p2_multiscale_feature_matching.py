#!/usr/bin/env python3
"""P2: 多尺度与频域预处理下的板书/试卷特征匹配质量评测。

This is the only Python file implementing the P2 experiment.  It supports
the repository's reproducible procedural fixture and a real-photo manifest
with manually annotated point pairs.  The experiment writes row-level CSV,
JSON summaries, and vector figures; no metric is hard-coded in the report.

Example (from the repository root):
    python p2_multiscale_feature_matching.py --generate-synthetic --force
    python p2_multiscale_feature_matching.py --data-root data/p2

Real data manifest requirements are documented in data/p2/README.md.  A
real-photo submission must replace the synthetic fixture and must retain at
least 20 manually verified same-name point pairs per scene/reference pair.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = ROOT / "data" / "p2"
DEFAULT_OUTPUT_ROOT = ROOT / "output" / "p2"
DEFAULT_FIGURE_ROOT = ROOT / "figures" / "p2"

METHODS = ("Sobel", "LoG", "Harris", "Shi-Tomasi", "SIFT")
FILTERS = ("none", "ideal_lowpass", "gaussian_lowpass", "ideal_highpass", "gaussian_highpass")
FILTER_LABELS = {
    "none": "none",
    "ideal_lowpass": "ideal LP",
    "gaussian_lowpass": "Gaussian LP",
    "ideal_highpass": "ideal HP",
    "gaussian_highpass": "Gaussian HP",
}
METHOD_COLORS = {
    "Sobel": "#0072B2",
    "LoG": "#D55E00",
    "Harris": "#009E73",
    "Shi-Tomasi": "#CC79A7",
    "SIFT": "#E69F00",
}
METHOD_MARKERS = {"Sobel": "o", "LoG": "s", "Harris": "^", "Shi-Tomasi": "D", "SIFT": "P"}
METHOD_LINESTYLES = {
    "Sobel": "-",
    "LoG": "--",
    "Harris": ":",
    "Shi-Tomasi": "-.",
    "SIFT": (0, (3, 1, 1, 1)),
}
ABLATION_CONFIGS = {
    "full": {"pyramid_levels": 3, "frequency_filter": "gaussian_lowpass", "nms": True},
    "no_pyramid": {"pyramid_levels": 1, "frequency_filter": "gaussian_lowpass", "nms": True},
    "no_frequency": {"pyramid_levels": 3, "frequency_filter": "none", "nms": True},
    "no_nms": {"pyramid_levels": 3, "frequency_filter": "gaussian_lowpass", "nms": False},
}
ABLATION_LABELS = {
    "full": "full",
    "no_pyramid": "-pyramid",
    "no_frequency": "-frequency",
    "no_nms": "-NMS",
}


@dataclass
class Sample:
    """One scene/reference pair and its point-pair annotation."""

    image_id: str
    reference_path: Path
    scene_path: Path
    annotation_path: Path
    reference_points: np.ndarray
    scene_points: np.ndarray
    homography_scene_to_reference: np.ndarray
    condition: dict[str, Any]
    source_type: str
    annotation_status: str
    annotation_rmse_px: float
    reference_roi: np.ndarray | None = None
    scene_roi: np.ndarray | None = None


@dataclass
class FeatureSet:
    points: np.ndarray
    descriptors: np.ndarray
    scores: np.ndarray
    image_shape: tuple[int, int] | None = None
    roi_polygon: np.ndarray | None = None


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    def clean(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: clean(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(val) for val in item]
        if isinstance(item, float) and not math.isfinite(item):
            return None
        return item
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def finite_mean(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    array = array[np.isfinite(array)]
    return float(array.mean()) if array.size else float("nan")


def finite_std(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    array = array[np.isfinite(array)]
    return float(array.std(ddof=1)) if array.size > 1 else 0.0


def path_from_entry(data_root: Path, value: str | None) -> Path:
    if not value:
        raise ValueError("manifest entry is missing a relative path")
    path = Path(value)
    return path if path.is_absolute() else data_root / path


def locate_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_reference_image(index: int, width: int = 960, height: int = 720,
                         seed: int = 20260917) -> tuple[np.ndarray, list[list[float]]]:
    """Create a controlled board/paper-like reference and 32 anchor points.

    The anchors are placed on drawn corners, line intersections, and shape
    extrema.  They are generated controls for pipeline verification, not
    hand annotations and are labelled as such in the manifest.
    """
    rng = random.Random(seed + index * 37)
    background = (247 - index % 3 * 3, 245 - index % 4 * 2, 238 - index % 5 * 2)
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    margin = 64
    page = (margin, margin, width - margin, height - margin)
    page_color = (255, 253, 247) if index % 2 else (251, 252, 255)
    draw.rounded_rectangle(page, radius=12, fill=page_color, outline=(35, 55, 65), width=4)

    dark = (25, 43, 53)
    accent = [(20, 96, 135), (166, 72, 62), (37, 118, 82), (119, 79, 151)][index % 4]
    font_title = locate_font(26)
    font_small = locate_font(17)
    font_formula = locate_font(22)
    draw.text((92, 86), f"MACHINE VISION / SHEET {index + 1:02d}", fill=dark, font=font_title)
    draw.text((92, 122), "MULTISCALE FEATURE MATCHING", fill=accent, font=font_small)
    draw.line((92, 154, width - 92, 154), fill=accent, width=4)

    # A set of repeated line-and-box structures creates corners at known anchors.
    boxes = [
        (112, 198, 328, 334),
        (390, 198, 570, 334),
        (632, 198, 848, 334),
        (112, 404, 330, 570),
        (388, 404, 566, 570),
        (626, 404, 848, 570),
    ]
    for box_index, box in enumerate(boxes):
        line_color = dark if box_index % 2 else accent
        draw.rectangle(box, outline=line_color, width=4)
        if box_index % 3 == 0:
            draw.line((box[0] + 18, box[1] + 42, box[2] - 18, box[1] + 42), fill=line_color, width=3)
            draw.line((box[0] + 18, box[1] + 84, box[2] - 38, box[1] + 84), fill=line_color, width=3)
        elif box_index % 3 == 1:
            cx = (box[0] + box[2]) // 2
            cy = (box[1] + box[3]) // 2
            draw.ellipse((cx - 42, cy - 42, cx + 42, cy + 42), outline=line_color, width=4)
            draw.line((cx - 64, cy, cx + 64, cy), fill=line_color, width=3)
            draw.line((cx, cy - 64, cx, cy + 64), fill=line_color, width=3)
        else:
            draw.polygon(
                [(box[0] + 24, box[3] - 24), ((box[0] + box[2]) // 2, box[1] + 24), (box[2] - 24, box[3] - 24)],
                outline=line_color,
                fill=None,
                width=4,
            )
            draw.line((box[0] + 24, box[3] - 24, box[2] - 24, box[1] + 24), fill=line_color, width=3)
    # Formula-like strokes and a small checkerboard make scale and blur effects visible.
    draw.text((142, 258), "g(x) = dI/dx", fill=dark, font=font_formula)
    draw.text((418, 256), "x^2 + y^2", fill=dark, font=font_formula)
    draw.text((665, 256), "FFT: H(u,v)", fill=dark, font=font_formula)
    draw.text((142, 468), "S(x,y)", fill=dark, font=font_formula)
    draw.text((416, 468), "f(t) + dt", fill=dark, font=font_formula)
    draw.text((654, 468), "p1 <-> p2", fill=dark, font=font_formula)
    for row in range(4):
        for col in range(4):
            x0 = 715 + col * 24
            y0 = 500 + row * 18
            fill = (40, 55, 65) if (row + col + index) % 2 else (235, 237, 231)
            draw.rectangle((x0, y0, x0 + 24, y0 + 18), fill=fill, outline=dark, width=1)
    for _ in range(8):
        x1 = rng.randint(180, 790)
        y1 = rng.randint(600, 635)
        draw.line((x1, y1, min(width - 100, x1 + rng.randint(24, 80)), y1), fill=accent, width=2)

    points = [
        [64, 64], [896, 64], [896, 656], [64, 656],
        [112, 198], [328, 198], [112, 334], [328, 334],
        [390, 198], [570, 198], [390, 334], [570, 334],
        [632, 198], [848, 198], [632, 334], [848, 334],
        [112, 404], [330, 404], [112, 570], [330, 570],
        [388, 404], [566, 404], [388, 570], [566, 570],
        [626, 404], [848, 404], [626, 570], [848, 570],
        [270, 154], [510, 154], [750, 154], [480, 610],
    ]
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), points


def make_reference_to_scene_homography(index: int, width: int, height: int, seed: int = 20260917) -> np.ndarray:
    rng = np.random.default_rng(seed + 1000 + index * 11)
    scale = [0.96, 1.02, 0.90, 1.06, 0.98, 0.86, 1.04, 0.94, 1.00, 0.92][index % 10]
    center = np.array([width / 2.0, height / 2.0], dtype=np.float32)
    src = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    jitter = rng.normal(0.0, 8.0, size=(4, 2)).astype(np.float32)
    dst = (center + scale * (src - center) + jitter).astype(np.float32)
    return cv2.getPerspectiveTransform(src, dst)


def apply_scene_effects(reference_bgr: np.ndarray, index: int, homography: np.ndarray,
                        seed: int = 20260917) -> tuple[np.ndarray, dict[str, Any]]:
    height, width = reference_bgr.shape[:2]
    warped = cv2.warpPerspective(
        reference_bgr,
        homography,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(232, 231, 224),
    )
    lighting = [
        "neutral",
        "warm_gradient",
        "cool_side_light",
        "low_light_noise",
        "mixed_light",
        "shadow_band",
        "bright_center",
        "warm_side_light",
        "cool_gradient",
        "blurred_neutral",
    ][index % 10]
    blur_sigma = [0.0, 0.5, 0.8, 1.2, 0.4, 1.6, 0.3, 1.0, 0.7, 2.0][index % 10]
    noise_sigma = [1.0, 2.0, 4.0, 8.0, 3.0, 10.0, 1.5, 5.0, 6.0, 12.0][index % 10]
    scale_factor = [0.96, 1.02, 0.90, 1.06, 0.98, 0.86, 1.04, 0.94, 1.00, 0.92][index % 10]
    image = warped.astype(np.float32)
    yy, xx = np.mgrid[0:height, 0:width]
    xnorm = xx.astype(np.float32) / max(width - 1, 1)
    ynorm = yy.astype(np.float32) / max(height - 1, 1)
    if lighting.startswith("warm") or lighting == "mixed_light":
        image[:, :, 2] *= 1.11
        image[:, :, 1] *= 1.03
        image[:, :, 0] *= 0.91
    if lighting.startswith("cool"):
        image[:, :, 0] *= 1.10
        image[:, :, 1] *= 1.03
        image[:, :, 2] *= 0.92
    if lighting in {"warm_gradient", "cool_gradient", "mixed_light"}:
        gradient = 0.78 + 0.42 * (0.55 * xnorm + 0.45 * (1.0 - ynorm))
        image *= gradient[:, :, None]
    elif lighting in {"cool_side_light", "warm_side_light", "shadow_band"}:
        gradient = 0.64 + 0.48 * xnorm
        if lighting == "shadow_band":
            gradient *= 1.0 - 0.28 * np.exp(-((ynorm - 0.45) ** 2) / 0.025)
        image *= gradient[:, :, None]
    elif lighting == "low_light_noise":
        image *= 0.63
    elif lighting == "bright_center":
        radius = np.sqrt((xnorm - 0.5) ** 2 + (ynorm - 0.48) ** 2)
        image *= (1.25 - 0.75 * radius)[:, :, None]
    if blur_sigma > 0:
        ksize = int(max(3, 2 * round(3 * blur_sigma) + 1))
        image = cv2.GaussianBlur(image, (ksize, ksize), blur_sigma)
    rng = np.random.default_rng(seed + 3000 + index * 19)
    image += rng.normal(0.0, noise_sigma, size=image.shape).astype(np.float32)
    image = np.clip(image, 0, 255).astype(np.uint8)
    condition = {
        "lighting": lighting,
        "scale_factor": scale_factor,
        "blur_sigma": blur_sigma,
        "noise_sigma": noise_sigma,
        "source_type": "synthetic_procedural",
    }
    return image, condition


def generate_synthetic_dataset(data_root: Path, count: int = 10, seed: int = 20260917, force: bool = False) -> dict[str, Any]:
    """Generate ten varied reference/scene pairs with 32 known controls each."""
    if count < 10:
        raise ValueError("The P2 dataset must contain at least 10 images.")
    image_dir = data_root / "images"
    annotation_dir = data_root / "annotations"
    if data_root.exists() and not force and (data_root / "manifest.json").exists():
        return read_json(data_root / "manifest.json")
    if (data_root / "manifest.json").exists() and read_json(data_root / "manifest.json").get("dataset_status") != "synthetic_proxy_data":
        raise ValueError("Refusing to overwrite a real-data manifest with synthetic data. Choose another --data-root.")
    image_dir.mkdir(parents=True, exist_ok=True)
    annotation_dir.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    for index in range(count):
        image_id = f"syn_{index + 1:02d}"
        reference, reference_points = make_reference_image(index, seed=seed)
        homography_ref_to_scene = make_reference_to_scene_homography(index, reference.shape[1], reference.shape[0], seed)
        scene, condition = apply_scene_effects(reference, index, homography_ref_to_scene, seed)
        points_array = np.asarray(reference_points, dtype=np.float32).reshape(-1, 1, 2)
        scene_points = cv2.perspectiveTransform(points_array, homography_ref_to_scene).reshape(-1, 2)
        if not np.all((scene_points[:, 0] >= 0) & (scene_points[:, 0] < scene.shape[1]) &
                      (scene_points[:, 1] >= 0) & (scene_points[:, 1] < scene.shape[0])):
            raise ValueError(f"Synthetic homography moved an annotation outside the frame: {image_id}")
        reference_path = image_dir / f"{image_id}_reference.png"
        scene_path = image_dir / f"{image_id}_scene.png"
        annotation_path = annotation_dir / f"{image_id}.json"
        write_image(reference_path, reference)
        write_image(scene_path, scene)
        homography_scene_to_reference = np.linalg.inv(homography_ref_to_scene)
        annotation = {
            "image_id": image_id,
            "annotation_status": "generated_control_points_not_manual",
            "reference_image": str(reference_path.relative_to(data_root).as_posix()),
            "scene_image": str(scene_path.relative_to(data_root).as_posix()),
            "coordinate_convention": "x right, y down, origin at top-left, pixel coordinates in each PNG",
            "homography_scene_to_reference": homography_scene_to_reference.tolist(),
            "points": [],
        }
        annotation["points"] = [
            {
                "id": f"p{point_index + 1:02d}",
                "label": f"anchor_{point_index + 1:02d}",
                "reference": [float(reference_points[point_index][0]), float(reference_points[point_index][1])],
                "scene": [float(scene_points[point_index][0]), float(scene_points[point_index][1])],
            }
            for point_index in range(len(reference_points))
        ]
        json_dump(annotation_path, annotation)
        samples.append({
            "image_id": image_id,
            "reference_image": str(reference_path.relative_to(data_root).as_posix()),
            "scene_image": str(scene_path.relative_to(data_root).as_posix()),
            "annotation": str(annotation_path.relative_to(data_root).as_posix()),
            "condition": condition,
            "source_type": "synthetic_procedural",
        })
    manifest = {
        "dataset_name": "P2 procedural reproducibility fixture",
        "dataset_status": "synthetic_proxy_data",
        "seed": seed,
        "image_count": len(samples),
        "minimum_manual_pairs_per_image": 20,
        "manual_annotation_available": False,
        "replace_with_real_photos_before_submission": True,
        "coordinate_convention": "All points are [x, y] in image pixel coordinates; H maps scene to reference.",
        "samples": samples,
    }
    json_dump(data_root / "manifest.json", manifest)
    return manifest


def load_samples(data_root: Path, require_manual: bool = False) -> list[Sample]:
    manifest_path = data_root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No manifest found at {manifest_path}. Use --generate-synthetic or create a real-data manifest.")
    manifest = read_json(manifest_path)
    samples: list[Sample] = []
    seen_ids: set[str] = set()
    for entry in manifest.get("samples", []):
        image_id = str(entry["image_id"])
        if image_id in seen_ids:
            raise ValueError(f"Duplicate image_id: {image_id}")
        seen_ids.add(image_id)
        annotation_path = path_from_entry(data_root, entry.get("annotation") or entry.get("annotation_path"))
        annotation = read_json(annotation_path)
        status = str(annotation.get("annotation_status", manifest.get("dataset_status", "unknown")))
        source_type = str(entry.get("source_type", "unknown"))
        if require_manual and status != "manual_verified":
            raise ValueError(f"{image_id} is not marked as a manual annotation: {status}")
        if require_manual and source_type != "self_captured":
            raise ValueError(f"{image_id} is not marked as self_captured: {source_type}")
        points = annotation.get("points", [])
        if len(points) < 20:
            raise ValueError(f"{image_id} has {len(points)} point pairs; at least 20 are required.")
        reference_points = np.asarray([point["reference"] for point in points], dtype=np.float32)
        scene_points = np.asarray([point["scene"] for point in points], dtype=np.float32)
        if reference_points.shape != (len(points), 2) or scene_points.shape != (len(points), 2):
            raise ValueError(f"Point pairs must contain [x, y] coordinates: {image_id}")
        if not np.isfinite(reference_points).all() or not np.isfinite(scene_points).all():
            raise ValueError(f"Non-finite coordinates in {image_id}")
        if len({point["id"] for point in points}) != len(points):
            raise ValueError(f"Duplicate point IDs in {image_id}")
        if len(np.unique(reference_points, axis=0)) != len(points) or len(np.unique(scene_points, axis=0)) != len(points):
            raise ValueError(f"Duplicate point coordinates in {image_id}")
        if annotation.get("homography_scene_to_reference") is not None:
            homography = np.asarray(annotation["homography_scene_to_reference"], dtype=np.float64)
        else:
            homography, _ = cv2.findHomography(scene_points, reference_points, method=0)
            if homography is None:
                raise ValueError(f"Could not estimate a homography for {image_id}.")
        if homography.shape != (3, 3) or not np.isfinite(homography).all() or np.linalg.matrix_rank(homography) < 3:
            raise ValueError(f"Invalid or singular homography for {image_id}")
        reference_path = path_from_entry(data_root, entry.get("reference_image") or entry.get("reference_path") or annotation.get("reference_image"))
        scene_path = path_from_entry(data_root, entry.get("scene_image") or entry.get("scene_path") or annotation.get("scene_image"))
        if not reference_path.is_file() or not scene_path.is_file():
            raise FileNotFoundError(f"Missing image pair for {image_id}: {reference_path}, {scene_path}")
        for coordinates, image_path in ((reference_points, reference_path), (scene_points, scene_path)):
            if not points_inside(coordinates, read_gray(image_path).shape).all():
                raise ValueError(f"Annotation lies outside the image: {image_id}, {image_path.name}")
        annotation_rmse = float(np.sqrt(np.mean(np.sum((project_points(scene_points, homography) - reference_points) ** 2, axis=1))))
        samples.append(Sample(
            image_id=image_id,
            reference_path=reference_path,
            scene_path=scene_path,
            annotation_path=annotation_path,
            reference_points=reference_points,
            scene_points=scene_points,
            homography_scene_to_reference=homography,
            condition=dict(entry.get("condition", {})),
            source_type=source_type,
            annotation_status=status,
            annotation_rmse_px=annotation_rmse,
            reference_roi=cv2.convexHull(reference_points).reshape(-1, 2) if manifest.get("evaluation_roi") == "annotation_hull" else None,
            scene_roi=cv2.convexHull(scene_points).reshape(-1, 2) if manifest.get("evaluation_roi") == "annotation_hull" else None,
        ))
    if len(samples) < 10:
        raise ValueError(f"Only {len(samples)} image pairs found; P2 requires at least 10.")
    return samples


def prepare_real_photos(source_root: Path, data_root: Path, landmarks_path: Path) -> None:
    """Import photographs without altering originals or claiming human annotation."""
    specification = read_json(landmarks_path)
    reference_name = specification["reference_file"]
    width, height = specification["working_size"]
    photos = specification["photos"]
    if source_root.resolve() == data_root.resolve():
        raise ValueError("Original and working data directories must be different")
    if (data_root / "manifest.json").exists():
        existing = read_json(data_root / "manifest.json")
        if existing.get("dataset_name") != "P2 user-captured textbook photographs":
            raise ValueError("Refusing to replace a different dataset")
    provenance = {}
    for name in photos:
        path = source_root / name
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            original_width, original_height = image.size
            if abs(original_width / original_height - width / height) > 1e-6:
                raise ValueError(f"Resizing must preserve the aspect ratio: {name}")
            # 仅统一采样尺寸，不作透视拉正；不携带 EXIF/GPS 等元数据。
            working = image.resize((width, height), Image.Resampling.LANCZOS)
            destination = data_root / "images" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            working.save(destination, quality=96, subsampling=0)
        provenance[name] = {"original_filename": name, "original_size": [original_width, original_height],
                            "working_size": [width, height], "original_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "resize_scale": [width / original_width, height / original_height]}
    reference_points = photos[reference_name]["points"]
    entries = []
    for name, photo in photos.items():
        if name == reference_name:
            continue
        image_id = Path(name).stem
        pairs = []
        for index, scene_point in enumerate(photo["points"]):
            point_id = f"p{index + 1:02d}"
            if point_id in photo.get("exclude_points", []):
                continue
            override = photo.get("overrides", {}).get(point_id, {})
            reference_point = override.get("reference", reference_points[index])
            def original_coordinates(point: list[float], filename: str) -> list[float]:
                original_w, original_h = provenance[filename]["original_size"]
                return [round((point[0] + 0.5) * original_w / width - 0.5, 3),
                        round((point[1] + 0.5) * original_h / height - 0.5, 3)]
            pairs.append({"id": point_id, "label": override.get("label", specification["labels"][index]),
                          "reference": reference_point, "scene": scene_point,
                          "reference_original": original_coordinates(reference_point, reference_name), "scene_original": original_coordinates(scene_point, name)})
        annotation_path = f"annotations/{image_id}.json"
        json_dump(data_root / annotation_path, {"image_id": image_id, "annotation_status": specification["annotation_status"],
                  "annotator": specification["annotator"], "human_verified": False,
                  "notes": specification["notes"], "reference_image": f"images/{reference_name}", "scene_image": f"images/{name}",
                  "homography_scene_to_reference": None, "points": pairs})
        entries.append({"image_id": image_id, "reference_image": f"images/{reference_name}", "scene_image": f"images/{name}",
                        "annotation": annotation_path, "source_type": "self_captured", "condition": photo["condition"]})
    json_dump(data_root / "manifest.json", {"dataset_name": "P2 user-captured textbook photographs", "dataset_status": "real_photos_assistant_annotations",
              "image_count": len(photos), "scene_count": len(entries), "reference_file": reference_name, "subject_type": "textbook_page_not_board_or_exam",
              "human_annotation_available": False, "evaluation_roi": "annotation_hull", "coordinate_convention": "[x, y] on 960 x 1280 working images",
              "provenance": provenance, "samples": entries})
    print(f"Prepared {len(photos)} photographs and {len(entries)} annotated scene/reference pairs", flush=True)


def render_annotation_previews(samples: list[Sample], figure_root: Path) -> None:
    """Render every point pair, not just a convenient subset, for visual audit."""
    target = figure_root / "annotations"
    target.mkdir(parents=True, exist_ok=True)
    quality = []
    for sample in samples:
        with Image.open(sample.reference_path) as image:
            reference = image.convert("RGB")
        with Image.open(sample.scene_path) as image:
            scene = image.convert("RGB")
        points = read_json(sample.annotation_path)["points"]
        atlas = Image.new("RGB", (1000, math.ceil(len(points) / 4) * 150), "white")
        draw = ImageDraw.Draw(atlas)
        for index, point in enumerate(points):
            x, y = (index % 4) * 250, (index // 4) * 150
            draw.text((x + 5, y + 3), point["id"] + "  reference | scene", fill="black", font=locate_font(13))
            for offset, photo, coordinates in ((5, reference, point["reference"]), (125, scene, point["scene"])):
                px, py = coordinates
                crop = photo.crop((px - 20, py - 20, px + 20, py + 20)).resize((116, 116), Image.Resampling.NEAREST)
                patch_draw = ImageDraw.Draw(crop)
                patch_draw.ellipse((54, 54, 62, 62), outline="#e00000", width=2)
                atlas.paste(crop, (x + offset, y + 24))
        atlas.save(target / f"{sample.image_id}-point-audit.jpg", quality=95)
        for photo, coordinates, polygon, suffix in ((reference, sample.reference_points, sample.reference_roi, "reference"),
                                                     (scene, sample.scene_points, sample.scene_roi, "scene")):
            overview = photo.copy()
            pen = ImageDraw.Draw(overview)
            if polygon is not None:
                pen.line([tuple(v) for v in polygon] + [tuple(polygon[0])], fill="#00b080", width=2)
            for index, (px, py) in enumerate(coordinates):
                pen.ellipse((px - 3, py - 3, px + 3, py + 3), fill="#dd2020")
                pen.text((px + 4, py - 12), points[index]["id"][1:], font=locate_font(12), fill="#b00000", stroke_width=1, stroke_fill="white")
            overview.save(target / f"{sample.image_id}-{suffix}.jpg", quality=92)
        residuals = np.linalg.norm(project_points(sample.scene_points, sample.homography_scene_to_reference) - sample.reference_points, axis=1)
        held_out = []
        for index in range(len(points)):
            keep = np.arange(len(points)) != index
            homography, _ = cv2.findHomography(sample.scene_points[keep], sample.reference_points[keep], 0)
            error = np.linalg.norm(project_points(sample.scene_points[index:index + 1], homography)[0] - sample.reference_points[index])
            held_out.append(float(error))
        quality.append({"image_id": sample.image_id, "point_pairs": len(points), "annotation_status": sample.annotation_status,
                        "homography_fit_rmse_px": sample.annotation_rmse_px, "fit_max_px": float(residuals.max()),
                        "leave_one_out_median_px": float(np.median(held_out)), "leave_one_out_max_px": max(held_out),
                        "fit_residuals_px": residuals.tolist(), "leave_one_out_errors_px": held_out})
    json_dump(figure_root / "annotation-quality.json", quality)


def round_marker_center(gray: np.ndarray, initial: np.ndarray) -> np.ndarray:
    """Localize a visually identified list dot without choosing its row."""
    patch = cv2.getRectSubPix(gray, (40, 40), tuple(float(v) for v in initial))
    _, binary = cv2.threshold(patch, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        area, perimeter = cv2.contourArea(contour), cv2.arcLength(contour, True)
        if not 3 <= area <= 100 or perimeter == 0:
            continue
        circularity = 4 * np.pi * area / perimeter ** 2
        if circularity < 0.65:
            continue
        moment = cv2.moments(contour)
        point = initial + np.array([moment["m10"] / moment["m00"], moment["m01"] / moment["m00"]]) - 19.5
        distance = np.linalg.norm(point - initial)
        if distance < 10:
            candidates.append((distance + 4 * (1 - circularity), point))
    return min(candidates, key=lambda value: value[0])[1].astype(np.float32) if candidates else initial


def apply_assistant_visual_review(samples: list[Sample], review_path: Path) -> None:
    review = read_json(review_path)
    if review.get("human_verified") is not False or review.get("annotation_status") != "assistant_visual_verified":
        raise ValueError("This operation records assistant review only, never human manual verification")
    if set(review["samples"]) != {sample.image_id for sample in samples}:
        raise ValueError("Review must cover every sample exactly")
    for sample in samples:
        if len(sample.reference_points) != review["samples"][sample.image_id]:
            raise ValueError(f"Point count does not match the visual review: {sample.image_id}")
        annotation = read_json(sample.annotation_path)
        annotation["annotation_status"] = review["annotation_status"]
        annotation["verified_by"] = review["reviewer"]
        annotation["human_verified"] = False
        annotation["notes"] = review["notes"]
        json_dump(sample.annotation_path, annotation)


def refine_annotation_coordinates(samples: list[Sample], data_root: Path) -> None:
    """Assist selected landmarks with local gray-patch registration, not SIFT."""
    manifest = read_json(data_root / "manifest.json")
    if manifest.get("dataset_status") != "real_photos_assistant_annotations":
        raise ValueError("Refinement is restricted to the assistant-annotated photograph dataset")
    for sample in samples:
        annotation = read_json(sample.annotation_path)
        reference = cv2.GaussianBlur(read_gray(sample.reference_path), (3, 3), 0.5)
        scene = read_gray(sample.scene_path)
        scene_points = sample.scene_points.copy()
        for index, point in enumerate(annotation["points"]):
            if point["label"].startswith("objective bullet"):
                scene_points[index] = round_marker_center(scene, scene_points[index])
        fixed_markers = scene_points.copy()
        homography = sample.homography_scene_to_reference.copy()
        scores = []
        for _ in range(2):
            warped = cv2.warpPerspective(scene, homography, (reference.shape[1], reference.shape[0]))
            warped = cv2.GaussianBlur(warped, (3, 3), 0.5)
            updated, scores = [], []
            for index, point in enumerate(sample.reference_points):
                center = (float(point[0]), float(point[1]))
                template = cv2.getRectSubPix(reference, (32, 32), center)
                if annotation["points"][index]["label"].startswith("objective bullet"):
                    # 重复圆点不可依赖模板峰值编号；保留逐张辨认的圆心，防止串行。
                    mapped = fixed_markers[index]
                    projected = project_points(mapped.reshape(1, 2), homography)[0]
                    candidate = cv2.getRectSubPix(warped, (32, 32), tuple(float(v) for v in projected))
                    score = float(cv2.matchTemplate(candidate, template, cv2.TM_CCOEFF_NORMED)[0, 0])
                else:
                    search = cv2.getRectSubPix(warped, (80, 80), center)
                    response = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
                    expected = project_points(scene_points[index:index + 1], homography)[0] - point + 24
                    yy, xx = np.indices(response.shape)
                    prior = np.hypot(xx - expected[0], yy - expected[1])
                    _, _, _, location = cv2.minMaxLoc(response - 0.002 * prior.astype(np.float32))
                    score = float(response[location[1], location[0]])
                    target = point + np.asarray(location, np.float32) - 24
                    mapped = project_points(target.reshape(1, 2), np.linalg.inv(homography))[0]
                updated.append(mapped)
                scores.append(float(score))
            scene_points = np.asarray(updated, np.float32)
            homography, _ = cv2.findHomography(scene_points, sample.reference_points, 0)
        scene_name = sample.scene_path.name
        original_w, original_h = manifest["provenance"][scene_name]["original_size"]
        working_w, working_h = manifest["provenance"][scene_name]["working_size"]
        for point, coordinates, score in zip(annotation["points"], scene_points, scores):
            point.setdefault("initial_scene", point["scene"])
            point["scene"] = [round(float(v), 3) for v in coordinates]
            point["scene_original"] = [round((float(coordinates[0]) + 0.5) * original_w / working_w - 0.5, 3),
                                       round((float(coordinates[1]) + 0.5) * original_h / working_h - 0.5, 3)]
            point["local_patch_ncc"] = score
        annotation["annotation_status"] = "assistant_registration_pending_visual_review"
        annotation["annotation_method"] = "visual landmark selection + local normalized grayscale patch registration"
        annotation["notes"] = "Assistant-selected and numerically refined point pairs; every final pair requires visual review. Not human manual_verified; no evaluated feature detector generated these pairs."
        json_dump(sample.annotation_path, annotation)
        print(f"refined {sample.image_id}: minimum patch NCC={min(scores):.3f}", flush=True)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Unable to read image: {path}")
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(path.suffix, image)
    if not success:
        raise IOError(f"Unable to encode image: {path}")
    encoded.tofile(str(path))


def frequency_preprocess(gray: np.ndarray, mode: str) -> np.ndarray:
    """Apply ideal/Gaussian low-pass or high-pass FFT filtering."""
    if mode == "none":
        return gray.copy()
    if mode not in FILTERS:
        raise ValueError(f"Unknown frequency filter: {mode}")
    image = gray.astype(np.float32) / 255.0
    height, width = image.shape
    spectrum = np.fft.fftshift(np.fft.fft2(image))
    yy, xx = np.ogrid[:height, :width]
    # fftshift 后直流分量位于整数中心，奇数尺寸也必须使用整除。
    distance = np.sqrt((xx - width // 2) ** 2 + (yy - height // 2) ** 2)
    radius = 0.12 * min(height, width)
    if mode in ("ideal_lowpass", "ideal_highpass"):
        lowpass = (distance <= radius).astype(np.float32)
        transfer = lowpass if mode == "ideal_lowpass" else 1.0 - lowpass
    else:
        sigma = 0.10 * min(height, width)
        lowpass = np.exp(-(distance ** 2) / (2.0 * sigma ** 2)).astype(np.float32)
        transfer = lowpass if mode == "gaussian_lowpass" else 1.0 - lowpass
    filtered = np.fft.ifft2(np.fft.ifftshift(spectrum * transfer)).real
    if mode in ("ideal_highpass", "gaussian_highpass"):
        low, high = np.percentile(filtered, [1.0, 99.0])
        if high - low < 1e-8:
            filtered = np.zeros_like(filtered)
        else:
            filtered = (filtered - low) / (high - low)
    else:
        filtered = np.clip(filtered, 0.0, 1.0)
    return np.clip(filtered * 255.0, 0, 255).astype(np.uint8)


def normalise_response(response: np.ndarray) -> np.ndarray:
    response = np.nan_to_num(response.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    response -= float(response.min())
    peak = float(response.max())
    return response / peak if peak > 1e-12 else np.zeros_like(response)


def response_map(gray: np.ndarray, method: str) -> np.ndarray:
    image = gray.astype(np.float32) / 255.0
    if method == "Sobel":
        smooth = cv2.GaussianBlur(image, (3, 3), 0)
        gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
        response = cv2.magnitude(gx, gy)
    elif method == "LoG":
        smooth = cv2.GaussianBlur(image, (0, 0), 1.2)
        response = np.abs(cv2.Laplacian(smooth, cv2.CV_32F, ksize=3))
    elif method == "Harris":
        response = cv2.cornerHarris(image, blockSize=2, ksize=3, k=0.04)
        response = np.maximum(response, 0.0)
    elif method == "Shi-Tomasi":
        response = cv2.cornerMinEigenVal(image, blockSize=3, ksize=3)
    else:
        raise ValueError(f"Response map is not defined for {method}")
    return normalise_response(response)


def response_points(response: np.ndarray, nms: bool, max_candidates: int,
                    roi_mask: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Turn a detector response into points, with an explicit NMS ablation."""
    # 消融只切换 NMS；响应阈值和关键点预算保持一致。
    values = response if roi_mask is None else response[roi_mask > 0]
    threshold = float(np.percentile(values, 99.0)) if values.size else 1.0
    mask = response >= max(threshold, 1e-8)
    if roi_mask is not None:
        mask &= roi_mask > 0
    if nms:
        kernel = np.ones((5, 5), dtype=np.uint8)
        local_maximum = response >= cv2.dilate(response, kernel) - 1e-7
        mask &= local_maximum
    y, x = np.nonzero(mask)
    if len(x) == 0:
        return np.empty((0, 2), dtype=np.float32), np.empty((0,), dtype=np.float32)
    scores = response[y, x]
    order = np.argsort(-scores, kind="stable")
    order = order[:max_candidates]
    return np.column_stack([x[order], y[order]]).astype(np.float32), scores[order].astype(np.float32)


def patch_descriptors(gray: np.ndarray, points: np.ndarray, patch_size: int = 32) -> tuple[np.ndarray, np.ndarray]:
    descriptors: list[np.ndarray] = []
    valid: list[int] = []
    for index, (x, y) in enumerate(points):
        patch = cv2.getRectSubPix(gray, (patch_size, patch_size), (float(x), float(y)))
        if patch is None or patch.shape != (patch_size, patch_size):
            continue
        small = cv2.resize(patch, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
        small -= small.mean()
        norm = float(np.linalg.norm(small))
        if norm < 1e-6:
            continue
        descriptors.append((small / norm).reshape(-1))
        valid.append(index)
    if not descriptors:
        return np.empty((0, 256), dtype=np.float32), np.empty((0,), dtype=np.int32)
    return np.asarray(descriptors, dtype=np.float32), np.asarray(valid, dtype=np.int32)


def spatial_features(gray: np.ndarray, method: str, nms: bool, max_features: int,
                     roi_mask: np.ndarray | None = None) -> FeatureSet:
    if method == "SIFT":
        if not hasattr(cv2, "SIFT_create"):
            raise RuntimeError("This OpenCV build does not provide SIFT_create.")
        detector = cv2.SIFT_create(nfeatures=max_features, contrastThreshold=0.01, edgeThreshold=10, sigma=1.2)
        keypoints, descriptors = detector.detectAndCompute(gray, roi_mask)
        if not keypoints or descriptors is None:
            return FeatureSet(np.empty((0, 2), np.float32), np.empty((0, 128), np.float32), np.empty((0,), np.float32))
        points = np.asarray([keypoint.pt for keypoint in keypoints], dtype=np.float32)
        scores = np.asarray([keypoint.response for keypoint in keypoints], dtype=np.float32)
    else:
        response = response_map(gray, method)
        points, scores = response_points(response, nms=nms, max_candidates=max_features * 3, roi_mask=roi_mask)
        descriptors, valid = patch_descriptors(gray, points)
        points = points[valid]
        scores = scores[valid]
        return FeatureSet(points, descriptors, scores)
    return FeatureSet(points, descriptors.astype(np.float32), scores)


def keep_spatially_separated(features: FeatureSet, max_features: int, min_distance: float = 5.0) -> FeatureSet:
    if not len(features.points):
        return features
    order = np.argsort(-features.scores, kind="stable")
    kept: list[int] = []
    distance_squared = min_distance ** 2
    for index in order:
        point = features.points[index]
        if not kept or np.all(np.sum((point - features.points[kept]) ** 2, axis=1) >= distance_squared):
            kept.append(int(index))
            if len(kept) >= max_features:
                break
    if not kept:
        kept = [int(index) for index in order[:max_features]]
    kept_array = np.asarray(kept, dtype=np.int32)
    return FeatureSet(features.points[kept_array], features.descriptors[kept_array], features.scores[kept_array], features.image_shape, features.roi_polygon)


def extract_features(gray: np.ndarray, method: str, frequency_filter: str, pyramid_levels: int,
                     nms: bool, max_features: int, roi_polygon: np.ndarray | None = None) -> FeatureSet:
    if method not in METHODS:
        raise ValueError(f"Unknown feature method: {method}")
    if not 1 <= pyramid_levels <= 3:
        raise ValueError("pyramid_levels must be 1, 2, or 3")
    all_points: list[np.ndarray] = []
    all_descriptors: list[np.ndarray] = []
    all_scores: list[np.ndarray] = []
    height, width = gray.shape[:2]
    for level in range(pyramid_levels):
        scale = 1.0 / (2 ** level)
        level_size = (max(32, int(round(width * scale))), max(32, int(round(height * scale))))
        level_gray = gray if level == 0 else cv2.resize(gray, level_size, interpolation=cv2.INTER_AREA)
        level_gray = frequency_preprocess(level_gray, frequency_filter)
        roi_mask = None
        if roi_polygon is not None:
            # 仅限制检测候选，不将背景清零，以免制造 FFT/NMS 的人工边界。
            level_polygon = (roi_polygon + 0.5) * np.array([level_gray.shape[1] / width, level_gray.shape[0] / height]) - 0.5
            roi_mask = np.zeros(level_gray.shape, np.uint8)
            cv2.fillPoly(roi_mask, [np.rint(level_polygon).astype(np.int32)], 255)
        level_features = spatial_features(level_gray, method, nms=nms, max_features=max_features, roi_mask=roi_mask)
        if not len(level_features.points):
            continue
        # 按 resize 的像素中心映射回原图，避免粗层的半像素定位偏差。
        level_features.points[:, 0] = (level_features.points[:, 0] + 0.5) * width / level_gray.shape[1] - 0.5
        level_features.points[:, 1] = (level_features.points[:, 1] + 0.5) * height / level_gray.shape[0] - 0.5
        all_points.append(level_features.points)
        all_descriptors.append(level_features.descriptors)
        all_scores.append(level_features.scores / (1.0 + 0.2 * level))
    if not all_points:
        return FeatureSet(np.empty((0, 2), np.float32), np.empty((0, 0), np.float32), np.empty((0,), np.float32), gray.shape, roi_polygon)
    features = FeatureSet(np.vstack(all_points), np.vstack(all_descriptors), np.concatenate(all_scores), gray.shape, roi_polygon)
    if nms:
        return keep_spatially_separated(features, max_features=max_features, min_distance=5.0)
    order = np.argsort(-features.scores, kind="stable")[:max_features]
    return FeatureSet(features.points[order], features.descriptors[order], features.scores[order], gray.shape, roi_polygon)


def project_points(points: np.ndarray, homography: np.ndarray) -> np.ndarray:
    if len(points) == 0:
        return np.empty((0, 2), dtype=np.float32)
    return cv2.perspectiveTransform(points.reshape(-1, 1, 2).astype(np.float32), homography).reshape(-1, 2)


def points_inside(points: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    height, width = shape[:2]
    return (np.isfinite(points).all(axis=1) & (points[:, 0] >= 0) & (points[:, 0] < width) &
            (points[:, 1] >= 0) & (points[:, 1] < height))


def common_visible_features(reference: FeatureSet, scene: FeatureSet, homography: np.ndarray) -> tuple[FeatureSet, FeatureSet]:
    if reference.image_shape is None or scene.image_shape is None:
        return reference, scene
    # 仅在两图共同可见区域计算分母，不能惩罚拍摄裁切造成的不可见点。
    projected_reference = project_points(reference.points, np.linalg.inv(homography))
    projected_scene = project_points(scene.points, homography)
    reference_mask = points_inside(projected_reference, scene.image_shape)
    scene_mask = points_inside(projected_scene, reference.image_shape)
    if scene.roi_polygon is not None:
        reference_mask &= points_in_polygon(projected_reference, scene.roi_polygon)
    if reference.roi_polygon is not None:
        scene_mask &= points_in_polygon(projected_scene, reference.roi_polygon)
    def subset(features: FeatureSet, mask: np.ndarray) -> FeatureSet:
        return FeatureSet(features.points[mask], features.descriptors[mask], features.scores[mask], features.image_shape, features.roi_polygon)
    return subset(reference, reference_mask), subset(scene, scene_mask)


def points_in_polygon(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    contour = np.asarray(polygon, dtype=np.float32)
    return np.asarray([cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0 for x, y in points], dtype=bool)


def greedy_correspondences(reference_points: np.ndarray, scene_points: np.ndarray, homography_scene_to_reference: np.ndarray,
                           tolerance: float) -> list[tuple[int, int, float]]:
    if len(reference_points) == 0 or len(scene_points) == 0:
        return []
    predicted_reference = project_points(scene_points, homography_scene_to_reference)
    distances = np.linalg.norm(predicted_reference[:, None, :] - reference_points[None, :, :], axis=2)
    candidate_pairs = np.argwhere(distances <= tolerance)
    if len(candidate_pairs) == 0:
        return []
    candidate_pairs = sorted(candidate_pairs.tolist(), key=lambda pair: float(distances[pair[0], pair[1]]))
    used_scene: set[int] = set()
    used_reference: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for scene_index, reference_index in candidate_pairs:
        if scene_index in used_scene or reference_index in used_reference:
            continue
        used_scene.add(scene_index)
        used_reference.add(reference_index)
        matches.append((reference_index, scene_index, float(distances[scene_index, reference_index])))
    return matches


def repeatability_metrics(reference_features: FeatureSet, scene_features: FeatureSet, homography: np.ndarray,
                          tolerance: float = 5.0) -> tuple[float, float, int]:
    reference_features, scene_features = common_visible_features(reference_features, scene_features, homography)
    matches = greedy_correspondences(reference_features.points, scene_features.points, homography, tolerance)
    denominator = min(len(reference_features.points), len(scene_features.points))
    repeatability = len(matches) / denominator if denominator else 0.0
    errors = [match[2] for match in matches]
    localization = float(np.median(errors)) if errors else float("nan")
    return repeatability, localization, len(matches)


def ratio_match_pairs(reference_descriptors: np.ndarray, scene_descriptors: np.ndarray,
                      ratio_threshold: float = 0.78) -> list[tuple[int, int, float, float]]:
    if len(reference_descriptors) < 2 or len(scene_descriptors) < 2:
        return []
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    forward = matcher.knnMatch(reference_descriptors.astype(np.float32), scene_descriptors.astype(np.float32), k=2)
    reverse = matcher.knnMatch(scene_descriptors.astype(np.float32), reference_descriptors.astype(np.float32), k=2)
    reverse_map: dict[int, tuple[int, float]] = {}
    for candidates in reverse:
        if len(candidates) < 2:
            continue
        best, second = candidates
        if best.distance < ratio_threshold * second.distance:
            reverse_map[best.queryIdx] = (best.trainIdx, best.distance / max(second.distance, 1e-8))
    pairs: list[tuple[int, int, float, float]] = []
    for candidates in forward:
        if len(candidates) < 2:
            continue
        best, second = candidates
        ratio = best.distance / max(second.distance, 1e-8)
        if best.distance >= ratio_threshold * second.distance:
            continue
        reverse_choice = reverse_map.get(best.trainIdx)
        if reverse_choice is None or reverse_choice[0] != best.queryIdx:
            continue
        pairs.append((best.queryIdx, best.trainIdx, float(best.distance), float(ratio)))
    pairs.sort(key=lambda item: (item[3], item[2]))
    unique_reference: set[int] = set()
    unique_scene: set[int] = set()
    selected: list[tuple[int, int, float, float]] = []
    for pair in pairs:
        if pair[0] in unique_reference or pair[1] in unique_scene:
            continue
        unique_reference.add(pair[0])
        unique_scene.add(pair[1])
        selected.append(pair)
    return selected


def matching_metrics(reference_features: FeatureSet, scene_features: FeatureSet, homography: np.ndarray,
                     tolerance: float = 4.0) -> tuple[float, float, int, int]:
    matches = ratio_match_pairs(reference_features.descriptors, scene_features.descriptors)
    if not matches:
        return float("nan"), float("nan"), 0, 0
    scene_points = scene_features.points[np.asarray([match[1] for match in matches], dtype=np.int32)]
    reference_points = reference_features.points[np.asarray([match[0] for match in matches], dtype=np.int32)]
    predicted_reference = project_points(scene_points, homography)
    errors = np.linalg.norm(predicted_reference - reference_points, axis=1)
    correct = int(np.sum(errors <= tolerance))
    accuracy = correct / len(matches)
    return accuracy, float(np.median(errors)), len(matches), correct


def evaluate_feature_pair(reference_gray: np.ndarray, scene_gray: np.ndarray, method: str,
                          frequency_filter: str, pyramid_levels: int, nms: bool,
                          homography_scene_to_reference: np.ndarray, max_features: int,
                          repeatability_tolerance: float, match_tolerance: float,
                          include_matches: bool = False, reference_roi: np.ndarray | None = None,
                          scene_roi: np.ndarray | None = None) -> tuple[dict[str, Any], list[tuple[int, int, float, float]], FeatureSet, FeatureSet]:
    start = time.perf_counter()
    reference_features = extract_features(reference_gray, method, frequency_filter, pyramid_levels, nms, max_features, reference_roi)
    scene_features = extract_features(scene_gray, method, frequency_filter, pyramid_levels, nms, max_features, scene_roi)
    raw_reference_count, raw_scene_count = len(reference_features.points), len(scene_features.points)
    reference_features, scene_features = common_visible_features(reference_features, scene_features, homography_scene_to_reference)
    repeatability, localization, repeated = repeatability_metrics(
        reference_features, scene_features, homography_scene_to_reference, repeatability_tolerance
    )
    accuracy, match_error, accepted, correct = matching_metrics(
        reference_features, scene_features, homography_scene_to_reference, match_tolerance
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    row = {
        "method": method,
        "frequency_filter": frequency_filter,
        "pyramid_levels": pyramid_levels,
        "nms": bool(nms),
        "repeatability": repeatability,
        "matching_accuracy": accuracy,
        "localization_error_px": localization,
        "matching_error_px": match_error,
        "runtime_ms": elapsed_ms,
        "reference_keypoints": len(reference_features.points),
        "scene_keypoints": len(scene_features.points),
        "raw_reference_keypoints": raw_reference_count,
        "raw_scene_keypoints": raw_scene_count,
        "repeated_points": repeated,
        "accepted_matches": accepted,
        "correct_matches": correct,
    }
    pairs = ratio_match_pairs(reference_features.descriptors, scene_features.descriptors) if include_matches else []
    return row, pairs, reference_features, scene_features


def add_noise(gray: np.ndarray, sigma: float, seed: int) -> np.ndarray:
    if sigma <= 0:
        return gray.copy()
    rng = np.random.default_rng(seed)
    noisy = gray.astype(np.float32) + rng.normal(0.0, sigma, size=gray.shape).astype(np.float32)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def aggregate(rows: list[dict[str, Any]], group_fields: Sequence[str], metric_fields: Sequence[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(row.get(field) for field in group_fields)
        groups.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    def sort_key(item: tuple[tuple[Any, ...], Any]) -> tuple[Any, ...]:
        return tuple((0, float(value)) if isinstance(value, (int, float)) else (1, str(value)) for value in item[0])
    for key, group in sorted(groups.items(), key=sort_key):
        result = {field: value for field, value in zip(group_fields, key)}
        result["count"] = len(group)
        for metric in metric_fields:
            values = [safe_float(row.get(metric), float("nan")) for row in group]
            result[metric] = finite_mean(values)
            result[metric + "_std"] = finite_std(values)
            result[metric + "_valid_count"] = sum(math.isfinite(value) for value in values)
        output.append(result)
    return output


def configure_matplotlib() -> None:
    plt.rcParams.update({
        "font.family": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 9.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.22,
        "grid.linewidth": 0.5,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
    })


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    fig.savefig(path.with_suffix(".svg"))
    fig.savefig(path.with_suffix(".png"), dpi=180)
    plt.close(fig)


def plot_pyramid_curve(rows: list[dict[str, Any]], figure_root: Path) -> None:
    configure_matplotlib()
    fig, axes = plt.subplots(3, 2, figsize=(7.1, 7.4), sharex=True, sharey=True)
    for axis, frequency_filter in zip(axes.flat, FILTERS):
        subset = [row for row in rows if row["frequency_filter"] == frequency_filter]
        for method in METHODS:
            series = [row for row in subset if row["method"] == method]
            grouped = aggregate(series, ["pyramid_levels"], ["repeatability"])
            x = [int(row["pyramid_levels"]) for row in grouped]
            y = [safe_float(row["repeatability"], 0.0) for row in grouped]
            e = [safe_float(row["repeatability_std"], 0.0) for row in grouped]
            axis.errorbar(x, y, yerr=e, color=METHOD_COLORS[method], marker=METHOD_MARKERS[method],
                          linestyle=METHOD_LINESTYLES[method], linewidth=1.25, markersize=4,
                          capsize=2, label=method)
        axis.set_title(FILTER_LABELS[frequency_filter])
        axis.set_xticks([1, 2, 3])
        axis.set_ylim(0, 1.02)
        axis.set_xlabel("pyramid levels")
        axis.set_ylabel("repeatability")
    for axis in list(axes.flat)[len(FILTERS):]:
        axis.set_axis_off()
    handles = [Line2D([0], [0], color=METHOD_COLORS[m], marker=METHOD_MARKERS[m], linestyle=METHOD_LINESTYLES[m],
                       linewidth=1.25, markersize=4, label=m) for m in METHODS]
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.015))
    fig.suptitle("Repeatability versus pyramid depth", y=1.005, fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 0.99))
    save_figure(fig, figure_root / "repeatability_pyramid.pdf")


def plot_condition_curve(rows: list[dict[str, Any]], figure_root: Path, x_field: str,
                          xlabel: str, title: str, filename: str) -> None:
    configure_matplotlib()
    fig, axes = plt.subplots(3, 2, figsize=(7.1, 7.4), sharex=True, sharey=True)
    for axis, frequency_filter in zip(axes.flat, FILTERS):
        subset = [row for row in rows if row["frequency_filter"] == frequency_filter]
        for method in METHODS:
            series = [row for row in subset if row["method"] == method]
            grouped = aggregate(series, [x_field], ["repeatability"])
            x = [float(row[x_field]) for row in grouped]
            y = [safe_float(row["repeatability"], 0.0) for row in grouped]
            e = [safe_float(row["repeatability_std"], 0.0) for row in grouped]
            axis.errorbar(x, y, yerr=e, color=METHOD_COLORS[method], marker=METHOD_MARKERS[method],
                          linestyle=METHOD_LINESTYLES[method], linewidth=1.25, markersize=4,
                          capsize=2, label=method)
        axis.set_title(FILTER_LABELS[frequency_filter])
        axis.set_xlabel(xlabel)
        axis.set_xticks(sorted(set(float(row[x_field]) for row in rows)))
        axis.set_ylabel("repeatability")
        axis.set_ylim(0, 1.02)
    for axis in list(axes.flat)[len(FILTERS):]:
        axis.set_axis_off()
    handles = [Line2D([0], [0], color=METHOD_COLORS[m], marker=METHOD_MARKERS[m], linestyle=METHOD_LINESTYLES[m],
                       linewidth=1.25, markersize=4, label=m) for m in METHODS]
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.015))
    fig.suptitle(title, y=1.005, fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 0.99))
    save_figure(fig, figure_root / filename)


def plot_ablation(rows: list[dict[str, Any]], figure_root: Path) -> None:
    configure_matplotlib()
    metrics = [
        ("repeatability", "repeatability", (0, 1.02)),
        ("matching_accuracy", "matching accuracy", (0, 1.02)),
        ("localization_error_px", "localization error (px)", None),
        ("runtime_ms", "runtime (ms)", None),
    ]
    variant_colors = {"full": "#0072B2", "no_pyramid": "#56B4E9", "no_frequency": "#E69F00", "no_nms": "#999999"}
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.6))
    x = np.arange(len(METHODS))
    width = 0.19
    for axis, (metric, ylabel, ylim) in zip(axes.flat, metrics):
        for offset, variant in enumerate(ABLATION_CONFIGS):
            values = []
            errors = []
            for method in METHODS:
                subset = [row for row in rows if row["method"] == method and row["ablation"] == variant]
                values.append(finite_mean(row.get(metric, float("nan")) for row in subset))
                errors.append(finite_std(row.get(metric, float("nan")) for row in subset))
            values = np.asarray(values, dtype=float)
            errors = np.nan_to_num(np.asarray(errors, dtype=float), nan=0.0)
            axis.bar(x + (offset - 1.5) * width, values, width, yerr=errors, capsize=2,
                     color=variant_colors[variant], edgecolor="#333333", linewidth=0.35,
                     label=ABLATION_LABELS[variant])
        axis.set_xticks(x, METHODS, rotation=22, ha="right")
        axis.set_ylabel(ylabel)
        if ylim:
            axis.set_ylim(*ylim)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, ncol=4, loc="lower center")
    fig.suptitle("Ablation of pyramid, frequency preprocessing, and NMS", y=1.005, fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 0.98))
    save_figure(fig, figure_root / "ablation_metrics.pdf")


def make_contact_sheet(samples: list[Sample], figure_root: Path) -> None:
    thumbs: list[Image.Image] = []
    for sample in samples:
        reference = Image.open(sample.reference_path).convert("RGB")
        scene = Image.open(sample.scene_path).convert("RGB")
        reference.thumbnail((320, 220))
        scene.thumbnail((320, 220))
        tile = Image.new("RGB", (660, 260), "white")
        tile.paste(reference, (5, 25))
        tile.paste(scene, (335, 25))
        draw = ImageDraw.Draw(tile)
        draw.text((8, 5), f"{sample.image_id} reference", fill=(20, 20, 20), font=locate_font(14))
        draw.text((338, 5), f"{sample.image_id} scene", fill=(20, 20, 20), font=locate_font(14))
        thumbs.append(tile)
    columns = 2
    rows = math.ceil(len(thumbs) / columns)
    sheet = Image.new("RGB", (columns * 660, rows * 260), (232, 232, 232))
    for index, tile in enumerate(thumbs):
        sheet.paste(tile, ((index % columns) * 660, (index // columns) * 260))
    figure_root.mkdir(parents=True, exist_ok=True)
    sheet.save(figure_root / "dataset_contact_sheet.png")


def make_match_figure(sample: Sample, method: str, frequency_filter: str, pyramid_levels: int,
                      nms: bool, max_features: int, repeatability_tolerance: float,
                      match_tolerance: float, figure_root: Path) -> dict[str, Any]:
    reference = read_gray(sample.reference_path)
    scene = read_gray(sample.scene_path)
    row, pairs, reference_features, scene_features = evaluate_feature_pair(
        reference, scene, method, frequency_filter, pyramid_levels, nms,
        sample.homography_scene_to_reference, max_features, repeatability_tolerance, match_tolerance,
        include_matches=True,
        reference_roi=sample.reference_roi, scene_roi=sample.scene_roi,
    )
    reference_color = cv2.cvtColor(reference, cv2.COLOR_GRAY2RGB)
    scene_color = cv2.cvtColor(scene, cv2.COLOR_GRAY2RGB)
    height = max(reference_color.shape[0], scene_color.shape[0])
    width = reference_color.shape[1] + scene_color.shape[1]
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    canvas[:reference_color.shape[0], :reference_color.shape[1]] = reference_color
    canvas[:scene_color.shape[0], reference_color.shape[1]:] = scene_color
    line_count = 0
    for ref_index, scene_index, _, _ in pairs[:40]:
        ref_point = tuple(np.rint(reference_features.points[ref_index]).astype(int))
        scene_point = tuple(np.rint(scene_features.points[scene_index]).astype(int) + np.array([reference_color.shape[1], 0]))
        correct = float(np.linalg.norm(project_points(np.asarray([scene_features.points[scene_index]]), sample.homography_scene_to_reference)[0] - reference_features.points[ref_index])) <= match_tolerance
        color = (32, 150, 82) if correct else (208, 68, 55)
        cv2.circle(canvas, ref_point, 4, color, 1, cv2.LINE_AA)
        cv2.circle(canvas, scene_point, 4, color, 1, cv2.LINE_AA)
        cv2.line(canvas, ref_point, scene_point, color, 1, cv2.LINE_AA)
        line_count += 1
    figure_root.mkdir(parents=True, exist_ok=True)
    write_image(figure_root / "sample_matches.png", cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
    return {"sample_id": sample.image_id, "method": method, "frequency_filter": frequency_filter,
            "pyramid_levels": pyramid_levels, "nms": nms, "drawn_matches": line_count, **row}


def run_experiment(samples: list[Sample], output_root: Path, figure_root: Path, max_features: int,
                   repeatability_tolerance: float, match_tolerance: float, noise_levels: list[float],
                   run_noise: bool = True, scale_factors: Sequence[float] = (0.5, 0.75, 1.0, 1.25),
                   seed: int = 20260917) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    figure_root.mkdir(parents=True, exist_ok=True)
    main_rows: list[dict[str, Any]] = []
    total_main = len(samples) * len(METHODS) * len(FILTERS) * 3
    completed = 0
    for sample in samples:
        reference_gray = read_gray(sample.reference_path)
        scene_gray = read_gray(sample.scene_path)
        for frequency_filter in FILTERS:
            for pyramid_levels in (1, 2, 3):
                for method in METHODS:
                    row, _, _, _ = evaluate_feature_pair(
                        reference_gray, scene_gray, method, frequency_filter, pyramid_levels, True,
                        sample.homography_scene_to_reference, max_features, repeatability_tolerance, match_tolerance,
                        reference_roi=sample.reference_roi, scene_roi=sample.scene_roi,
                    )
                    main_rows.append({"scope": "main_grid", "image_id": sample.image_id, **sample.condition, **row})
                    completed += 1
        print(f"main grid: {completed}/{total_main}", flush=True)
    write_rows(output_root / "main_results.csv", main_rows)

    ablation_rows: list[dict[str, Any]] = []
    total_ablation = len(samples) * len(METHODS) * len(ABLATION_CONFIGS)
    completed = 0
    for sample in samples:
        reference_gray = read_gray(sample.reference_path)
        scene_gray = read_gray(sample.scene_path)
        for ablation, config in ABLATION_CONFIGS.items():
            for method in METHODS:
                row, _, _, _ = evaluate_feature_pair(
                    reference_gray, scene_gray, method, config["frequency_filter"], config["pyramid_levels"], config["nms"],
                    sample.homography_scene_to_reference, max_features, repeatability_tolerance, match_tolerance,
                    reference_roi=sample.reference_roi, scene_roi=sample.scene_roi,
                )
                ablation_rows.append({"scope": "ablation", "image_id": sample.image_id, "ablation": ablation,
                                      **sample.condition, **row})
                completed += 1
        print(f"ablation: {completed}/{total_ablation}", flush=True)
    write_rows(output_root / "ablation_results.csv", ablation_rows)

    noise_rows: list[dict[str, Any]] = []
    if run_noise:
        total_noise = len(samples) * len(METHODS) * len(FILTERS) * len(noise_levels)
        completed = 0
        for sample_index, sample in enumerate(samples):
            reference_gray = read_gray(sample.reference_path)
            scene_gray = read_gray(sample.scene_path)
            for frequency_filter in FILTERS:
                for method in METHODS:
                    reference_features = extract_features(reference_gray, method, frequency_filter, 3, True, max_features, sample.reference_roi)
                    for noise_sigma in noise_levels:
                        # 所有方法共用同一样本的噪声实现；sigma 只改变振幅。
                        noisy_scene = add_noise(scene_gray, noise_sigma, seed + 6000 + sample_index * 101)
                        scene_features = extract_features(noisy_scene, method, frequency_filter, 3, True, max_features, sample.scene_roi)
                        visible_reference, visible_scene = common_visible_features(reference_features, scene_features, sample.homography_scene_to_reference)
                        repeatability, localization, repeated = repeatability_metrics(
                            visible_reference, visible_scene, sample.homography_scene_to_reference, repeatability_tolerance
                        )
                        noise_rows.append({
                            "scope": "noise_curve", "image_id": sample.image_id, "method": method,
                            "frequency_filter": frequency_filter, "pyramid_levels": 3, "nms": True,
                            "noise_sigma": noise_sigma, "repeatability": repeatability,
                            "localization_error_px": localization, "repeated_points": repeated,
                            "reference_keypoints": len(visible_reference.points), "scene_keypoints": len(visible_scene.points),
                        })
                        completed += 1
                print(f"noise curve: {completed}/{total_noise}", flush=True)
        write_rows(output_root / "noise_results.csv", noise_rows)
    else:
        write_rows(output_root / "noise_results.csv", [])
        for suffix in (".pdf", ".svg", ".png"):
            (figure_root / ("repeatability_noise" + suffix)).unlink(missing_ok=True)

    image_scale_rows: list[dict[str, Any]] = []
    total_scale = len(samples) * len(METHODS) * len(FILTERS) * len(scale_factors)
    completed = 0
    for sample in samples:
        reference_gray, scene_gray = read_gray(sample.reference_path), read_gray(sample.scene_path)
        height, width = scene_gray.shape
        for frequency_filter in FILTERS:
            for method in METHODS:
                reference_features = extract_features(reference_gray, method, frequency_filter, 3, True, max_features, sample.reference_roi)
                for factor in scale_factors:
                    new_width, new_height = max(32, round(width * factor)), max(32, round(height * factor))
                    interpolation = cv2.INTER_AREA if factor < 1 else cv2.INTER_LINEAR
                    scaled_scene = cv2.resize(scene_gray, (new_width, new_height), interpolation=interpolation)
                    sx, sy = new_width / width, new_height / height
                    # 新坐标 -> 原场景坐标 -> 参考坐标；误差始终以参考像素计。
                    inverse_resize = np.array([[1 / sx, 0, (1 / sx - 1) / 2],
                                               [0, 1 / sy, (1 / sy - 1) / 2], [0, 0, 1]], dtype=np.float64)
                    homography = sample.homography_scene_to_reference @ inverse_resize
                    scaled_roi = None if sample.scene_roi is None else (sample.scene_roi + 0.5) * np.array([sx, sy]) - 0.5
                    scene_features = extract_features(scaled_scene, method, frequency_filter, 3, True, max_features, scaled_roi)
                    visible_reference, visible_scene = common_visible_features(reference_features, scene_features, homography)
                    repeatability, localization, repeated = repeatability_metrics(
                        visible_reference, visible_scene, homography, repeatability_tolerance
                    )
                    image_scale_rows.append({
                        "scope": "scale_curve", "image_id": sample.image_id, "method": method,
                        "frequency_filter": frequency_filter, "pyramid_levels": 3, "nms": True,
                        "image_scale": factor, "repeatability": repeatability,
                        "localization_error_px": localization, "repeated_points": repeated,
                        "reference_keypoints": len(visible_reference.points), "scene_keypoints": len(visible_scene.points),
                    })
                    completed += 1
        print(f"scale curve: {completed}/{total_scale}", flush=True)
    write_rows(output_root / "scale_results.csv", image_scale_rows)

    pyramid_summary = aggregate(main_rows, ["frequency_filter", "method", "pyramid_levels"],
                              ["repeatability", "matching_accuracy", "localization_error_px", "runtime_ms"])
    ablation_summary = aggregate(ablation_rows, ["ablation", "method"],
                                 ["repeatability", "matching_accuracy", "localization_error_px", "runtime_ms", "accepted_matches", "correct_matches", "reference_keypoints", "scene_keypoints"])
    scale_summary = aggregate(image_scale_rows, ["frequency_filter", "method", "image_scale"],
                              ["repeatability", "localization_error_px"])
    noise_summary = aggregate(noise_rows, ["frequency_filter", "method", "noise_sigma"],
                              ["repeatability", "localization_error_px"])
    write_rows(output_root / "scale_summary.csv", scale_summary)
    write_rows(output_root / "pyramid_summary.csv", pyramid_summary)
    write_rows(output_root / "ablation_summary.csv", ablation_summary)
    write_rows(output_root / "noise_summary.csv", noise_summary)

    plot_pyramid_curve(main_rows, figure_root)
    plot_condition_curve(image_scale_rows, figure_root, "image_scale", "scene resize factor",
                         "Repeatability versus image scale", "repeatability_scale.pdf")
    if noise_rows:
        plot_condition_curve(noise_rows, figure_root, "noise_sigma", "added Gaussian noise sigma (DN)",
                             "Repeatability versus additive noise", "repeatability_noise.pdf")
    plot_ablation(ablation_rows, figure_root)
    make_contact_sheet(samples, figure_root)
    if any(sample.reference_roi is not None for sample in samples):
        render_annotation_previews(samples, figure_root)
    match_preview = make_match_figure(
        samples[0], "SIFT", "gaussian_lowpass", 3, True, max_features,
        repeatability_tolerance, match_tolerance, figure_root,
    )

    by_method = aggregate(main_rows, ["method"], ["repeatability", "matching_accuracy", "localization_error_px", "runtime_ms"])
    summary = {
        "dataset": {
            "sample_count": len(samples),
            "source_types": sorted(set(sample.source_type for sample in samples)),
            "annotation_statuses": sorted(set(sample.annotation_status for sample in samples)),
            "manual_annotation_status": "manual_verified" if all(sample.annotation_status == "manual_verified" for sample in samples) else "not_human_manual_verified",
            "evaluation_roi": "annotation_hull" if any(sample.reference_roi is not None for sample in samples) else "full_frame",
            "point_pairs_per_sample": {sample.image_id: int(len(sample.reference_points)) for sample in samples},
            "annotation_rmse_px": {sample.image_id: sample.annotation_rmse_px for sample in samples},
        },
        "metric_definitions": {
            "repeatability": f"distance-ranked unique point pairs within {repeatability_tolerance:g} reference px, divided by min(N_ref, N_scene) in common visible region",
            "matching_accuracy": f"correct mutual ratio-test matches within {match_tolerance:g} reference px divided by accepted matches; undefined if no accepted matches",
            "localization_error_px": "median pixel error of repeatable detected correspondences",
            "runtime_ms": "preprocessing, detection, description, geometric evaluation, and matching per pair; disk I/O excluded; one timing per pair/configuration",
        },
        "parameters": {
            "methods": list(METHODS), "frequency_filters": list(FILTERS), "pyramid_levels": [1, 2, 3],
            "repeatability_tolerance_px": repeatability_tolerance, "match_tolerance_px": match_tolerance,
            "max_features": max_features, "noise_levels_sigma_dn": noise_levels,
            "image_scale_factors": list(scale_factors), "seed": seed,
            "response_percentile": 99.0, "descriptor_ratio_threshold": 0.78,
            "nms_window": [5, 5], "post_nms_distance_px": 5.0,
            "nms_scope_sift": "Only common post-detection spatial NMS is switched; OpenCV SIFT's internal DoG extrema selection remains active.",
        },
        "environment": {
            "python": platform.python_version(), "opencv": cv2.__version__, "numpy": np.__version__,
            "matplotlib": matplotlib.__version__, "pillow": Image.__version__,
            "platform": platform.platform(), "processor": platform.processor(),
            "opencv_threads": cv2.getNumThreads(), "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "input_hashes": {
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "samples": {sample.image_id: {
                "reference_sha256": hashlib.sha256(sample.reference_path.read_bytes()).hexdigest(),
                "scene_sha256": hashlib.sha256(sample.scene_path.read_bytes()).hexdigest(),
                "annotation_sha256": hashlib.sha256(sample.annotation_path.read_bytes()).hexdigest(),
            } for sample in samples},
        },
        "method_summary_main_grid": by_method,
        "method_filter_summary_three_levels": aggregate([row for row in main_rows if row["pyramid_levels"] == 3],
                                                        ["method", "frequency_filter"], ["repeatability", "matching_accuracy", "localization_error_px", "runtime_ms"]),
        "ablation_summary": ablation_summary,
        "match_preview": match_preview,
        "artifacts": {
            "main_results": "main_results.csv", "ablation_results": "ablation_results.csv", "noise_results": "noise_results.csv",
            "scale_summary": "scale_summary.csv", "scale_results": "scale_results.csv", "pyramid_summary": "pyramid_summary.csv",
            "ablation_summary": "ablation_summary.csv", "noise_summary": "noise_summary.csv",
            "figures": ["repeatability_scale.pdf", "repeatability_pyramid.pdf", "ablation_metrics.pdf", "sample_matches.png"] + (["repeatability_noise.pdf"] if noise_rows else []),
        },
    }
    json_dump(output_root / "summary.json", summary)
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print(f"completed: {summary['dataset']['sample_count']} image pairs, "
          f"source={summary['dataset']['source_types']}")
    for row in summary["method_summary_main_grid"]:
        print(f"{row['method']:12s} repeatability={row['repeatability']:.3f} "
              f"match accuracy={row['matching_accuracy']:.3f} error={row['localization_error_px']:.3f} px")


def self_test() -> None:
    # 用已知几何和常量信号验证评测口径，避免只检查函数能否运行。
    for mode in ("ideal_lowpass", "gaussian_lowpass"):
        result = frequency_preprocess(np.full((31, 35), 128, dtype=np.uint8), mode)
        assert np.max(np.abs(result.astype(int) - 128)) <= 1, "FFT low-pass must preserve DC"
    for mode in ("ideal_highpass", "gaussian_highpass"):
        assert not frequency_preprocess(np.full((31, 35), 128, dtype=np.uint8), mode).any(), "FFT high-pass must remove DC"
    features = FeatureSet(np.array([[2, 2], [3, 2], [20, 20]], np.float32),
                          np.eye(3, dtype=np.float32), np.array([3, 2, 1], np.float32), (30, 30))
    separated = keep_spatially_separated(features, max_features=10)
    assert len(separated.points) == 2, "NMS must run even below the budget"
    H = np.array([[1, 0, 10], [0, 1, 0], [0, 0, 1]], dtype=float)
    ref = FeatureSet(np.array([[12, 2], [25, 20], [2, 20]], np.float32),
                     np.eye(3, dtype=np.float32), np.ones(3, np.float32), (30, 30))
    scene = FeatureSet(np.array([[2, 2], [15, 20], [25, 20]], np.float32),
                       np.eye(3, dtype=np.float32), np.ones(3, np.float32), (30, 30))
    rep, error, count = repeatability_metrics(ref, scene, H, 0.1)
    assert rep == 1.0 and error == 0.0 and count == 2, "Only common visibility belongs in the denominator"
    assert len(greedy_correspondences(np.array([[0, 0]], np.float32),
                                     np.array([[0, 0], [0.1, 0]], np.float32), np.eye(3), 1)) == 1
    groups = aggregate([{"x": x, "repeatability": 0.5} for x in [0, 5, 10, 20]], ["x"], ["repeatability"])
    assert [row["x"] for row in groups] == [0, 5, 10, 20], "Noise axes must sort numerically"
    empty = FeatureSet(np.empty((0, 2), np.float32), np.empty((0, 0), np.float32), np.empty(0, np.float32))
    assert math.isnan(matching_metrics(empty, empty, np.eye(3))[0]), "Zero-match precision is undefined"
    image = np.zeros((35, 31), dtype=np.uint8)
    assert np.array_equal(add_noise(image, 5, 7), add_noise(image, 5, 7)), "Noise must be reproducible"
    print("self-test: 7 metric and preprocessing checks passed")
    polygon = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], np.float32)
    assert points_in_polygon(np.array([[1, 1], [20, 20]], np.float32), polygon).tolist() == [True, False]
    response = np.zeros((30, 30), np.float32)
    response[5, 5], response[25, 25] = 0.8, 1.0
    mask = np.zeros((30, 30), np.uint8)
    mask[:10, :10] = 255
    pts, _ = response_points(response, True, 10, mask)
    assert pts.tolist() == [[5.0, 5.0]], "ROI must restrict candidates before the feature budget"
    cropped_ref = FeatureSet(ref.points, ref.descriptors, ref.scores, ref.image_shape, polygon)
    cropped_scene = FeatureSet(scene.points, scene.descriptors, scene.scores, scene.image_shape, polygon)
    _, visible_scene = common_visible_features(cropped_ref, cropped_scene, H)
    assert not len(visible_scene.points), "Common visibility must check the other image's ROI"
    print("self-test: 3 additional ROI checks passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--figure-root", type=Path, default=DEFAULT_FIGURE_ROOT)
    parser.add_argument("--generate-synthetic", action="store_true", help="create the 10-image controlled fixture")
    parser.add_argument("--prepare-photos", type=Path, help="import originals using individually selected landmarks")
    parser.add_argument("--landmarks-file", type=Path, default=ROOT / "data" / "p2-real-landmarks.json")
    parser.add_argument("--render-annotations", action="store_true", help="render every annotated point pair without experiments")
    parser.add_argument("--refine-annotations", action="store_true", help="assist selected landmarks with local grayscale registration")
    parser.add_argument("--apply-visual-review", type=Path, help="record a completed assistant-only review; not human manual verification")
    parser.add_argument("--synthetic-count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument("--force", action="store_true", help="overwrite the existing synthetic fixture")
    parser.add_argument("--require-manual", action="store_true", help="reject procedural or non-manual annotations")
    parser.add_argument("--max-features", type=int, default=220)
    parser.add_argument("--repeatability-tolerance", type=float, default=5.0)
    parser.add_argument("--match-tolerance", type=float, default=4.0)
    parser.add_argument("--noise-levels", type=float, nargs="+", default=[0.0, 5.0, 10.0, 20.0])
    parser.add_argument("--skip-noise", action="store_true")
    parser.add_argument("--scale-factors", type=float, nargs="+", default=[0.5, 0.75, 1.0, 1.25])
    parser.add_argument("--self-test", action="store_true", help="run known-geometry and signal checks")
    parser.add_argument("--validate-only", action="store_true", help="validate data and annotations without experiments")
    parser.add_argument("--generate-only", action="store_true", help="generate fixture without experiments")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cv2.setNumThreads(1)
    cv2.setRNGSeed(args.seed)
    if args.self_test:
        self_test()
        return 0
    if args.max_features < 2 or args.repeatability_tolerance <= 0 or args.match_tolerance <= 0:
        raise ValueError("Feature budget must be at least 2 and pixel tolerances must be positive")
    if any(not math.isfinite(value) or value < 0 for value in args.noise_levels) or any(not math.isfinite(value) or value <= 0 for value in args.scale_factors):
        raise ValueError("Noise sigma must be finite and nonnegative and scale factors must be finite and positive")
    if args.generate_synthetic:
        manifest = generate_synthetic_dataset(args.data_root, args.synthetic_count, args.seed, args.force)
        print(f"dataset: {manifest['dataset_name']} ({manifest['image_count']} samples)", flush=True)
    if args.prepare_photos:
        if args.generate_synthetic:
            raise ValueError("Real-photo import and synthetic generation are mutually exclusive")
        prepare_real_photos(args.prepare_photos, args.data_root, args.landmarks_file)
    if args.generate_only:
        if not args.generate_synthetic and not args.prepare_photos:
            raise ValueError("--generate-only requires --generate-synthetic or --prepare-photos")
        return 0
    samples = load_samples(args.data_root, require_manual=args.require_manual)
    if args.apply_visual_review:
        apply_assistant_visual_review(samples, args.apply_visual_review)
        samples = load_samples(args.data_root)
    if args.refine_annotations:
        refine_annotation_coordinates(samples, args.data_root)
        samples = load_samples(args.data_root)
        render_annotation_previews(samples, args.figure_root)
        return 0
    if args.render_annotations:
        render_annotation_previews(samples, args.figure_root)
        return 0
    if args.validate_only:
        print(json.dumps({"samples": len(samples), "annotations": [{"image_id": sample.image_id,
              "pairs": len(sample.reference_points), "status": sample.annotation_status,
              "rmse_px": sample.annotation_rmse_px} for sample in samples]}, indent=2))
        return 0
    summary = run_experiment(
        samples=samples,
        output_root=args.output_root,
        figure_root=args.figure_root,
        max_features=args.max_features,
        repeatability_tolerance=args.repeatability_tolerance,
        match_tolerance=args.match_tolerance,
        noise_levels=args.noise_levels,
        run_noise=not args.skip_noise,
        scale_factors=args.scale_factors,
        seed=args.seed,
    )
    print_summary(summary)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
