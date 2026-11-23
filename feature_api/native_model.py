"""Load the frozen LightGBM package once and preserve its original scores."""

import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import re
from threading import Lock
import warnings

import joblib
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "src/assets/metadata/v7_model_manifest.json"
MODEL_DIR = ROOT / "feature_api/models/v7"
MODEL_ID = "perfume-five-grouped-v7-m2048-d8/lgbm_D"
SOURCE_BUNDLE_SHA256 = "e29f8216b0b4ed0dcdbd0f28bac28a485ec0ceebbf81619f8609f5ee637898a9"
RUNTIME_PACKAGES = ("numpy", "pandas", "scikit-learn", "rdkit", "lightgbm", "joblib")
DESCRIPTORS = (
    "MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA",
    "NumRotatableBonds", "HeavyAtomCount", "RingCount",
)


class NativeModelError(RuntimeError):
    """The local package is incomplete or incompatible; do not serve a result."""


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def json_digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def package_id(manifest):
    return json_digest({
        "runtime": "lightgbm", "model_format": "joblib",
        "feature_schema_id": manifest["feature_schema_id"], "models": manifest["models"],
    })


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise NativeModelError("Manifest model lokal bukan objek JSON.")
    spec = manifest.get("feature_spec", {})
    labels = manifest.get("labels", [])
    entries = manifest.get("models", [])
    if (
        manifest.get("version") != 2
        or manifest.get("runtime") != "lightgbm"
        or manifest.get("model_format") != "joblib"
        or manifest.get("model_id") != MODEL_ID
        or manifest.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256
        or manifest.get("primary_threshold") != 0.5
        or not isinstance(spec, dict)
        or spec.get("n_bits") != 2048 or spec.get("radius") != 2
        or spec.get("include_chirality") is not False
        or spec.get("descriptors") != list(DESCRIPTORS)
        or spec.get("dimensions") != {"input": 2056}
        or spec.get("dtype") != "float32" or spec.get("fragment_policy") != "single"
        or spec.get("rdkit_version") != "2026.03.4"
        or not isinstance(labels, list) or len(labels) != 109
        or any(not isinstance(label, str) or not label for label in labels)
        or len(set(labels)) != 109
        or not isinstance(entries, list) or len(entries) != 109
    ):
        raise NativeModelError("Paket bukan model final v7 LightGBM D 109 label/2.056 fitur.")
    if manifest.get("feature_schema_id") != json_digest(spec):
        raise NativeModelError("Checksum skema fitur lokal berbeda.")
    for index, (label, entry) in enumerate(zip(labels, entries)):
        if (
            not isinstance(entry, dict) or entry.get("label") != label
            or entry.get("filename") != f"label_{index:03d}.joblib"
            or not isinstance(entry.get("sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])
        ):
            raise NativeModelError("Urutan label, nama berkas, atau checksum model tidak valid.")
    if manifest.get("bundle_id") != package_id(manifest):
        raise NativeModelError("Checksum manifest paket lokal berbeda.")
    environment = manifest.get("environment", {})
    if not isinstance(environment, dict) or set(environment) != set(RUNTIME_PACKAGES):
        raise NativeModelError("Daftar versi runtime model tidak lengkap.")
    return manifest


def read_manifest(path=MANIFEST_PATH):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as cause:
        raise NativeModelError("Manifest model belum tersedia. Jalankan scripts/prepare-local-models.py.") from cause
    return validate_manifest(value)


def verify_package(manifest_path=MANIFEST_PATH, model_dir=MODEL_DIR):
    manifest = read_manifest(manifest_path)
    directory = Path(model_dir).resolve()
    for entry in manifest["models"]:
        path = directory / entry["filename"]
        try:
            if path.resolve().parent != directory or digest(path) != entry["sha256"]:
                raise NativeModelError(f"Checksum model berbeda: {entry['filename']}.")
        except OSError as cause:
            raise NativeModelError(
                f"Model {entry['filename']} belum tersedia. Jalankan scripts/prepare-local-models.py."
            ) from cause
    return manifest


class NativePredictor:
    def __init__(self, manifest_path=None, model_dir=None):
        self.model_dir = Path(model_dir or MODEL_DIR).resolve()
        self.manifest = verify_package(manifest_path or MANIFEST_PATH, self.model_dir)
        for package, expected in self.manifest["environment"].items():
            try:
                installed = version(package)
            except PackageNotFoundError as cause:
                raise NativeModelError(f"Runtime memerlukan {package}=={expected}; pasang requirements API.") from cause
            if installed != expected:
                raise NativeModelError(f"Runtime memerlukan {package}=={expected}; terpasang {installed}.")
        self.labels = tuple(self.manifest["labels"])
        self._lock = Lock()
        models = []
        for entry in self.manifest["models"]:
            # Deserialize only the project's checksum-verified local artifacts.
            model = joblib.load(self.model_dir / entry["filename"])
            if (
                type(model).__module__ != "lightgbm.sklearn"
                or type(model).__name__ != "LGBMClassifier"
                or model.n_features_in_ != 2056 or list(model.classes_) != [0, 1]
            ):
                raise NativeModelError(f"Kelas atau jumlah fitur model berbeda: {entry['label']}.")
            models.append(model)
        self._models = tuple(models)

    def predict_features(self, matrix):
        values = np.asarray(matrix, dtype=np.float32)
        if (values.ndim != 2 or values.shape[0] == 0 or values.shape[1] != 2056
                or not np.isfinite(values).all()
                or not np.isin(values[:, :2048], [0, 1]).all()):
            raise ValueError("Expected finite float32 rows with 2.048 binary bits + 8 descriptors.")
        with self._lock, warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="X does not have valid feature names", category=UserWarning)
            # Each label is independent; one CPU thread avoids oversubscription.
            scores = np.column_stack([
                model.predict_proba(values, num_threads=1)[:, 1] for model in self._models
            ])
        if scores.shape != (len(values), 109) or not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
            raise NativeModelError("Model menghasilkan skor yang tidak valid; hasil parsial dibatalkan.")
        return scores

    def predict(self, vector):
        values = np.asarray(vector, dtype=np.float32)
        if values.shape != (2056,):
            raise ValueError("Expected one molecular vector with 2.056 features.")
        scores = self.predict_features(values.reshape(1, -1))[0]
        return [{"label": label, "score": float(score)} for label, score in zip(self.labels, scores)]
