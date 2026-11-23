"""Compare the copied runtime, frozen training vectors, reference scores and HTTP."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import warnings

import joblib
import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors, rdFingerprintGenerator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feature_api.native_model import NativePredictor, SOURCE_BUNDLE_SHA256, digest  # noqa: E402


FEATURES_SHA256 = "81531d2ba87102b56b610b9ec2c084ca147b8e5d218a5b87a21f8387a81c33a5"
SPLITS_SHA256 = "ae2ce0dda7ffeed2c397d4b631e1e3de39485aedf648b3365bd16272bdf7a4c4"
RECORDS_SHA256 = "e62cbe41c117c8ffb72e88e4b67bd5831ec6d5f47d7ffdb40f40c352836f9671"


def preparation_module():
    spec = importlib.util.spec_from_file_location("prepare_local_models", Path(__file__).with_name("prepare-local-models.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare(actual, expected, description):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise AssertionError(f"{description}: shapes/finite scores differ")
    error = float(np.max(np.abs(actual - expected)))
    disagreements = int(np.count_nonzero((actual >= 0.5) != (expected >= 0.5)))
    if error > 1e-12 or disagreements:
        raise AssertionError(f"{description}: max_abs_error={error}, threshold_disagreements={disagreements}")
    return {"score_count": int(actual.size), "max_abs_error": error,
            "threshold_disagreements": disagreements, "exactly_equal": bool(np.array_equal(actual, expected))}


def http_prediction(base_url, smiles, manifest):
    request = Request(base_url.rstrip("/") + "/predict", method="POST",
                      headers={"Content-Type": "application/json"},
                      data=json.dumps({"smiles": smiles, "feature_schema_id": manifest["feature_schema_id"],
                                       "bundle_id": manifest["bundle_id"]}).encode())
    with urlopen(request, timeout=60) as response:
        result = json.load(response)
    if result.get("status") != "ok" or result.get("input_dimensions") != 2056 or result.get("label_count") != 109:
        raise AssertionError("HTTP status, feature count, or label count differs")
    for key in ("model_id", "bundle_id", "feature_schema_id", "runtime", "primary_threshold"):
        if result.get(key) != manifest[key]:
            raise AssertionError(f"HTTP contract differs: {key}")
    scores = result.get("scores", [])
    if [item.get("label") for item in scores] != manifest["labels"]:
        raise AssertionError("HTTP label count/order differs")
    return result, np.asarray([item["score"] for item in scores])


def verify(args):
    prepare = preparation_module()
    run = (args.source_run or prepare.source_run(ROOT)).resolve()
    source_manifest = prepare.original_manifest(run)
    predictor = NativePredictor(args.manifest, args.models)
    manifest = predictor.manifest
    if manifest != source_manifest:
        raise AssertionError("The copied manifest differs from the validated frozen source")
    base = run.parents[1]
    features_path = args.features or base / "data/builds/perfume-m2048-d8-v7/features.npz"
    splits_path = args.splits or base / "data/builds/perfume-five-grouped-v2/splits.json"
    records_path = args.records or splits_path.parent / "records.csv"
    for path, expected in ((features_path, FEATURES_SHA256), (splits_path, SPLITS_SHA256), (records_path, RECORDS_SHA256)):
        if digest(path) != expected:
            raise AssertionError(f"Frozen input checksum differs: {path}")
    indices = json.loads(splits_path.read_text(encoding="utf-8"))["train"][:32]
    with np.load(features_path, allow_pickle=False) as frozen:
        matrix = np.concatenate((frozen["morgan"][indices], frozen["descriptors"][indices]), axis=1).astype(np.float32)
    with records_path.open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    smiles = [records[index]["smiles"] for index in indices]
    reference_path = args.reference or ROOT / ".local-run/python-reference.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if (reference["model_id"] != manifest["model_id"]
            or reference["source_bundle_sha256"] != SOURCE_BUNDLE_SHA256
            or reference["feature_schema_id"] != manifest["feature_schema_id"]):
        raise AssertionError("Stored Python reference belongs to another source model")

    if args.application_root:
        sys.path.insert(0, str(args.application_root.resolve()))
    from feature_api.app import calculate
    from fastapi import HTTPException
    spec = manifest["feature_spec"]
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=spec["radius"], fpSize=spec["n_bits"], includeChirality=spec["include_chirality"])
    def independent_features(value):
        mol = Chem.MolFromSmiles(value)
        mol = Chem.MolFromSmiles(Chem.MolToSmiles(mol, isomericSmiles=True))
        return np.concatenate((generator.GetFingerprintAsNumPy(mol),
                               [getattr(Descriptors, key)(mol) for key in spec["descriptors"]])).astype(np.float32)
    calculated = np.asarray([independent_features(value) for value in smiles], dtype=np.float32)
    if calculated.shape != (32, 2056) or not np.array_equal(calculated, matrix):
        raise AssertionError("Recomputed RDKit features differ from the 32 frozen train vectors")
    http_indices = []
    guard_exclusions = []
    for index, value in enumerate(smiles):
        try:
            application_vector = np.asarray(calculate(value)["fingerprint"], dtype=np.float32)
        except HTTPException as cause:
            if not isinstance(cause.detail, dict) or cause.detail.get("code") != "UNSUPPORTED_COMPOUND":
                raise
            guard_exclusions.append({"frozen_row": indices[index], "smiles": value,
                                     "code": cause.detail["code"], "message": cause.detail["message"]})
            continue
        if not np.array_equal(application_vector, matrix[index]):
            raise AssertionError(f"Application features differ at frozen row {indices[index]}")
        http_indices.append(index)
    molecule_features = []
    molecule_checks = []
    for item in reference["molecules"]:
        payload = calculate(item["input_smiles"])
        vector = np.asarray(payload["fingerprint"], dtype=np.float32)
        feature_hash = hashlib.sha256(vector.tobytes()).hexdigest()
        if feature_hash != item["feature_vector_sha256"]:
            raise AssertionError(f"Reference feature checksum differs: {item['name']}")
        molecule_features.append(vector)
        smiles.append(item["input_smiles"])
        http_indices.append(len(smiles) - 1)
        molecule_checks.append({"name": item["name"], "input_smiles": item["input_smiles"],
                                "canonical_smiles": payload["smiles"], "feature_vector_sha256": feature_hash})
    matrix = np.concatenate((matrix, np.asarray(molecule_features)), axis=0)
    packaged_scores = predictor.predict_features(matrix)
    original_scores = []
    hash_mapping = []
    for label, entry in zip(manifest["labels"], manifest["models"]):
        path = run / "lgbm_D" / entry["filename"]
        model = joblib.load(path)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="X does not have valid feature names", category=UserWarning)
            original_scores.append(model.predict_proba(matrix, num_threads=1)[:, 1])
        hash_mapping.append({"label": label, "filename": entry["filename"],
                             "source_sha256": digest(path),
                             "copied_sha256": digest(predictor.model_dir / entry["filename"])})
    original_scores = np.column_stack(original_scores)
    direct_comparison = compare(packaged_scores, original_scores, "Copied vs frozen native models")
    for index, item in enumerate(reference["molecules"]):
        by_label = {row["label"]: row["score"] for row in item["labels"]}
        expected = [by_label[label] for label in manifest["labels"]]
        molecule_checks[index].update(compare(packaged_scores[32 + index], expected, item["name"]))
        molecule_checks[index]["positive_count"] = int(np.count_nonzero(packaged_scores[32 + index] >= 0.5))
        molecule_checks[index]["scores"] = [
            {"label": label, "score": float(score), "predicted": bool(score >= 0.5)}
            for label, score in zip(manifest["labels"], packaged_scores[32 + index])
        ]
    http_check = None
    if args.api_url:
        http_scores = []
        for index in http_indices:
            value = smiles[index]
            _, values = http_prediction(args.api_url, value, manifest)
            http_scores.append(values)
        http_check = compare(http_scores, original_scores[http_indices], "HTTP vs frozen native models")
        http_check["request_count"] = len(http_indices)
        http_check["api_url"] = args.api_url
    converter_modules = [name for name in sys.modules if name.split(".")[0] in
                         {"onnx", "onnxruntime", "onnxmltools", "skl2onnx"}]
    if converter_modules:
        raise AssertionError(f"Unexpected conversion runtime imports: {converter_modules}")
    return {
        "status": "ok", "time_jakarta": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "scope": "Read-only model/feature consistency; no fitting or new quality evaluation",
        "runtime": "lightgbm", "model_id": manifest["model_id"], "bundle_id": manifest["bundle_id"],
        "source_bundle_sha256": SOURCE_BUNDLE_SHA256, "feature_schema_id": manifest["feature_schema_id"],
        "source_run": str(run), "package_model_dir": str(predictor.model_dir),
        "source_and_copy_are_distinct": predictor.model_dir != (run / "lgbm_D").resolve(),
        "model_count": len(manifest["models"]), "feature_dimensions": 2056,
        "model_conversion_runtime_loaded": False,
        "frozen_train_rows": indices, "frozen_feature_vectors_equal": True,
        "application_feature_vectors_equal": True, "application_eligible_count": len(http_indices),
        "application_guard_exclusions": guard_exclusions,
        "frozen_features_sha256": digest(features_path), "frozen_splits_sha256": digest(splits_path),
        "frozen_records_sha256": digest(records_path), "matrix_shape": list(matrix.shape),
        "copied_vs_original": direct_comparison, "reference_molecules": molecule_checks,
        "http_vs_original": http_check, "original_model_hashes": hash_mapping,
        "environment": manifest["environment"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--models", type=Path)
    parser.add_argument("--application-root", type=Path, help="Optional app root when running this verifier from a staging copy.")
    parser.add_argument("--features", type=Path)
    parser.add_argument("--splits", type=Path)
    parser.add_argument("--records", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--api-url")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output),
                      "copied_vs_original": result["copied_vs_original"],
                      "http_vs_original": result["http_vs_original"]}, indent=2))


if __name__ == "__main__":
    main()
