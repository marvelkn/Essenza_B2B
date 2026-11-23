"""Copy the checksum-verified final model; never train or reserialize it."""

import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feature_api.native_model import (  # noqa: E402
    MODEL_ID, SOURCE_BUNDLE_SHA256, RUNTIME_PACKAGES, digest, json_digest,
    package_id, validate_manifest, verify_package,
)


def source_run(project_root=ROOT):
    backend = Path(project_root).resolve().parent / "Perfume-MultiLabel-Classifier"
    run_id = "perfume-five-grouped-v7-m2048-d8"
    candidates = (
        backend / "runs" / run_id,
        backend / ".local-tools/campus-transfer-full-20260909/perfume-campus-grouped-v7-m2048-d8"
        / "perfume-campus-grouped-v7-m2048-d8/runs" / run_id,
    )
    for path in candidates:
        if (path / "complete.json").is_file():
            return path
    raise FileNotFoundError("Run final v7 belum ditemukan. Isi --source-run dengan folder run penelitian asli.")


def original_manifest(run):
    run = Path(run).resolve()
    bundle_path = run / "inference_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    completion = json.loads((run / "completion_manifest.json").read_text(encoding="utf-8"))["files"]
    if digest(bundle_path) != SOURCE_BUNDLE_SHA256 or completion.get("inference_bundle.json") != SOURCE_BUNDLE_SHA256:
        raise ValueError("Checksum sumber bundle final v7 berbeda; paket tidak dibuat.")
    if (
        bundle.get("protocol") != "perfume-five-grouped-v7-m2048-d8"
        or bundle.get("selected_candidate") != "lgbm_D" or bundle.get("algorithm") != "lgbm"
        or bundle.get("models_directory") != "lgbm_D" or bundle.get("primary_threshold") != 0.5
    ):
        raise ValueError("Sumber bukan kandidat final v7 LightGBM D.")
    entries = []
    labels = bundle["labels"]
    if not isinstance(labels, list) or len(labels) != 109 or len(set(labels)) != 109:
        raise ValueError("Registry label sumber bukan 109 label unik.")
    for index, label in enumerate(labels):
        original = bundle["models"][label]
        filename = original["file"]
        if filename != f"label_{index:03d}.joblib":
            raise ValueError(f"Nama model sumber tidak sesuai urutan: {label}")
        source = run / "lgbm_D" / filename
        expected = original["sha256"]
        if digest(source) != expected or completion.get(f"lgbm_D/{filename}") != expected:
            raise ValueError(f"Checksum sumber model berbeda: {label}")
        entries.append({"label": label, "filename": filename, "sha256": expected})
    manifest = {
        "version": 2, "model_id": MODEL_ID, "runtime": "lightgbm", "model_format": "joblib",
        "source_bundle_sha256": SOURCE_BUNDLE_SHA256,
        "feature_schema_id": json_digest(bundle["feature_spec"]),
        "feature_spec": bundle["feature_spec"], "labels": labels,
        "primary_threshold": 0.5, "models": entries,
        "environment": {name: bundle["environment"][name] for name in RUNTIME_PACKAGES},
    }
    manifest["bundle_id"] = package_id(manifest)
    return validate_manifest(manifest)


def prepare(run, project_root=ROOT):
    run = Path(run).resolve()
    project_root = Path(project_root).resolve()
    manifest = original_manifest(run)
    directory = project_root / "feature_api/models/v7"
    manifest_path = project_root / "src/assets/metadata/v7_model_manifest.json"
    # Verify all existing targets before copying any missing file.
    for entry in manifest["models"]:
        target = directory / entry["filename"]
        if target.exists() and digest(target) != entry["sha256"]:
            raise ValueError(f"Paket tujuan berbeda: {target}. Simpan/periksa paket tersebut sebelum menggantinya.")
    directory.mkdir(parents=True, exist_ok=True)
    copied = 0
    for entry in manifest["models"]:
        target = directory / entry["filename"]
        if target.exists():
            continue
        temporary = directory / f".{entry['filename']}.{uuid.uuid4().hex}.tmp"
        try:
            shutil.copyfile(run / "lgbm_D" / entry["filename"], temporary)
            if digest(temporary) != entry["sha256"]:
                raise ValueError(f"Checksum salinan model berbeda: {entry['label']}")
            temporary.replace(target)
            copied += 1
        finally:
            temporary.unlink(missing_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if not manifest_path.exists() or manifest_path.read_text(encoding="utf-8") != content:
        temporary = manifest_path.with_name(f".{manifest_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(manifest_path)
        finally:
            temporary.unlink(missing_ok=True)
    verify_package(manifest_path, directory)
    return {"status": "ok", "runtime": "lightgbm", "model_count": 109,
            "copied_models": copied, "bundle_id": manifest["bundle_id"],
            "source_bundle_sha256": SOURCE_BUNDLE_SHA256,
            "model_bytes": sum((directory / item["filename"]).stat().st_size for item in manifest["models"]),
            "manifest": str(manifest_path), "models": str(directory)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--verify-only", action="store_true", help="Check the copied package without its research source.")
    args = parser.parse_args()
    if args.verify_only:
        manifest = verify_package(args.project_root / "src/assets/metadata/v7_model_manifest.json",
                                  args.project_root / "feature_api/models/v7")
        result = {"status": "ok", "runtime": manifest["runtime"], "model_count": len(manifest["models"]),
                  "bundle_id": manifest["bundle_id"], "all_model_hashes_match": True}
    else:
        result = prepare(args.source_run or source_run(args.project_root), args.project_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
