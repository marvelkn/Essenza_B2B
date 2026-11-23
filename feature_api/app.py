"""Local RDKit preprocessing and original LightGBM inference for Essenza."""

import json
import os
import re
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import numpy as np
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors, rdFingerprintGenerator, rdMolDescriptors

from feature_api.native_model import NativePredictor


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path(os.environ.get(
    "ESSENZA_V7_MANIFEST", ROOT / "src/assets/metadata/v7_model_manifest.json"))
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
SPEC = MANIFEST["feature_spec"]
if (MANIFEST["model_id"] != "perfume-five-grouped-v7-m2048-d8/lgbm_D"
        or SPEC["n_bits"] != 2048 or SPEC["dimensions"]["input"] != 2056
        or SPEC["rdkit_version"] != rdBase.rdkitVersion):
    raise RuntimeError("v7 feature service and model bundle disagree")

GENERATOR = rdFingerprintGenerator.GetMorganGenerator(
    radius=SPEC["radius"], fpSize=SPEC["n_bits"],
    includeChirality=SPEC["include_chirality"])
PREDICTOR = None


@asynccontextmanager
async def lifespan(_app):
    global PREDICTOR
    PREDICTOR = NativePredictor(manifest_path=MANIFEST_PATH)
    try:
        yield
    finally:
        PREDICTOR = None


app = FastAPI(title="Essenza Local Prediction API", version="2.0.0", lifespan=lifespan)
ALLOW_PUBCHEM = os.environ.get("ESSENZA_ALLOW_PUBCHEM", "0").strip().lower() in {"1", "true", "yes"}
CATALOG = json.loads((ROOT / "src/assets/catalog/compounds.json").read_text(encoding="utf-8"))["compounds"]
MAX_CANDIDATES = 20
FORMULA_PATTERN = re.compile(r"(?:[A-Z][a-z]?\d*)+")
COMMON_NAMES = {
    "air": ("Air (H2O)", "O", "H2O"),
    "water": ("Water (H2O)", "O", "H2O"),
    "co2": ("Karbon dioksida (CO2)", "O=C=O", "CO2"),
    "carbon dioxide": ("Carbon dioxide (CO2)", "O=C=O", "CO2"),
}
INDONESIAN_NAMES = {
    "vanilin": "Vanillin",
    "etanol": "Ethanol",
    "etil asetat": "Ethyl acetate",
    "asam asetat": "Acetic acid",
}
CATALOG_SMILES = {item["smiles"] for item in CATALOG}


class FeatureRequest(BaseModel):
    smiles: str | None = Field(default=None, max_length=2000)
    compound_name: str | None = Field(default=None, max_length=200)
    feature_schema_id: str


class ResolveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class PredictionRequest(FeatureRequest):
    bundle_id: str


def prediction_supported(mol, canonical):
    # Eligibility is a basic input guard, not proof of model generalization.
    return canonical not in {"O", "O=C=O"} and any(
        atom.GetAtomicNum() == 6 for atom in mol.GetAtoms())


def require_external_lookup():
    if not ALLOW_PUBCHEM:
        raise HTTPException(404, detail={
            "code": "COMPOUND_NOT_IN_LOCAL_CATALOG",
            "message": "Senyawa belum ada di katalog lokal. Pilih dari daftar atau gunakan SMILES yang sudah diketahui. Pencarian internet dinonaktifkan oleh pengelola.",
        })


def candidate(name, smiles, source, cid=None, formula=None):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0 or len(Chem.GetMolFrags(mol)) != 1:
        return None
    canonical = Chem.MolToSmiles(mol, isomericSmiles=True)
    return {
        "name": name, "smiles": canonical,
        "molecular_formula": formula or rdMolDescriptors.CalcMolFormula(mol),
        "cid": str(cid) if cid is not None else None,
        "source": source,
        "in_catalog": source == "catalog" or canonical in CATALOG_SMILES,
        "prediction_supported": prediction_supported(mol, canonical),
    }


@lru_cache(maxsize=32)
def catalog_matches(query, is_formula):
    matches = []
    for item in CATALOG:
        if is_formula:
            mol = Chem.MolFromSmiles(item["smiles"])
            if mol is None or rdMolDescriptors.CalcMolFormula(mol) != query:
                continue
        elif query.casefold() not in (item["name"].casefold(),
                                       *(alias.casefold() for alias in item["aliases"])):
            continue
        resolved = candidate(item["name"], item["smiles"], "catalog", item["cid"])
        if resolved is None:
            continue
        matches.append(resolved)
        if len(matches) > MAX_CANDIDATES:
            break
    return matches


def pubchem_json(url):
    require_external_lookup()
    try:
        response = requests.get(url, timeout=(5, 10))
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(503, detail={"code": "LOOKUP_UNAVAILABLE",
                                         "message": "Pencarian senyawa sedang tidak tersedia. Coba lagi."}) from exc


def pubchem_matches(query, is_formula):
    encoded = quote(query, safe="")
    if is_formula:
        endpoint = f"fastformula/{encoded}/cids/JSON?MaxRecords={MAX_CANDIDATES + 1}"
    else:
        endpoint = f"name/{encoded}/cids/JSON?name_type=complete"
    root = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
    identifiers = pubchem_json(root + endpoint)
    if identifiers is None:
        return []
    try:
        cids = identifiers["IdentifierList"]["CID"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(503, detail={"code": "LOOKUP_UNAVAILABLE",
                                         "message": "Respons pencarian senyawa tidak valid."}) from exc
    if len(cids) > MAX_CANDIDATES:
        raise HTTPException(422, detail={"code": "TOO_MANY_MATCHES",
                                         "message": "Terlalu banyak struktur yang cocok. Masukkan nama yang lebih spesifik."})
    if not cids:
        return []
    properties = pubchem_json(root + f"cid/{','.join(map(str, cids))}/property/SMILES,MolecularFormula,IUPACName,Title/JSON")
    try:
        records = properties["PropertyTable"]["Properties"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(503, detail={"code": "LOOKUP_UNAVAILABLE",
                                         "message": "Detail senyawa tidak tersedia."}) from exc
    matches = []
    seen = set()
    for record in records:
        item = candidate(record.get("Title") or record.get("IUPACName") or query,
                         record.get("SMILES", ""), "pubchem", record.get("CID"),
                         record.get("MolecularFormula"))
        if item and item["smiles"] not in seen:
            matches.append(item)
            seen.add(item["smiles"])
    return matches


@app.post("/resolve")
def resolve(request: ResolveRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(422, detail={"code": "EMPTY_QUERY", "message": "Masukkan nama atau rumus senyawa."})
    common = COMMON_NAMES.get(query.casefold())
    if common:
        matches = [candidate(common[0], common[1], "common_name", formula=common[2])]
    else:
        mapped_name = INDONESIAN_NAMES.get(query.casefold(), query)
        is_formula = bool(FORMULA_PATTERN.fullmatch(mapped_name))
        matches = catalog_matches(mapped_name, is_formula)
        if len(matches) > MAX_CANDIDATES:
            raise HTTPException(422, detail={"code": "TOO_MANY_MATCHES",
                                             "message": "Banyak molekul punya rumus ini. Masukkan nama yang lebih spesifik."})
        if not matches:
            matches = pubchem_matches(mapped_name, is_formula)
    if not matches:
        raise HTTPException(404, detail={"code": "COMPOUND_NOT_FOUND",
                                         "message": "Senyawa tidak ditemukan. Coba nama atau rumus lain."})
    return {"query": query, "candidates": matches}


def lookup_name(name):
    # All input routes use the same resolver and ambiguity policy.
    matches = resolve(ResolveRequest(query=name))["candidates"]
    if len(matches) != 1:
        raise HTTPException(422, detail={"code": "AMBIGUOUS_COMPOUND",
            "message": "Nama atau rumus cocok dengan beberapa struktur. Cari lalu pilih satu struktur terlebih dahulu."})
    item = matches[0]
    return item["smiles"], None, item["source"]


def calculate(smiles):
    mol = Chem.MolFromSmiles(smiles.strip()) if isinstance(smiles, str) else None
    if mol is None or mol.GetNumAtoms() == 0:
        raise HTTPException(422, detail={"code": "INVALID_SMILES", "message": "Struktur SMILES tidak valid."})
    if len(Chem.GetMolFrags(mol)) != 1:
        raise HTTPException(422, detail={"code": "UNSUPPORTED_MIXTURE", "message": "Masukkan satu molekul, bukan campuran."})
    canonical = Chem.MolToSmiles(mol, isomericSmiles=True)
    if not prediction_supported(mol, canonical):
        raise HTTPException(422, detail={"code": "UNSUPPORTED_COMPOUND",
            "message": "Senyawa ini di luar cakupan prediksi aroma bahan parfum. Pilih senyawa lain."})
    mol = Chem.MolFromSmiles(canonical)
    fingerprint = GENERATOR.GetFingerprintAsNumPy(mol).astype(np.float32)
    descriptors = np.asarray([getattr(Descriptors, key)(mol) for key in SPEC["descriptors"]], dtype=np.float32)
    vector = np.concatenate((fingerprint, descriptors))
    if vector.shape != (2056,) or not np.isfinite(vector).all():
        raise HTTPException(422, detail={"code": "INVALID_FEATURES", "message": "Fitur molekul tidak valid."})
    return {
        "status": "ok", "model_id": MANIFEST["model_id"],
        "bundle_id": MANIFEST["bundle_id"], "feature_schema_id": MANIFEST["feature_schema_id"],
        "smiles": canonical, "molecular_formula": rdMolDescriptors.CalcMolFormula(mol),
        "molecular_weight": float(descriptors[0]), "fingerprint": vector.tolist(),
    }


@app.get("/health")
def health():
    ready = PREDICTOR is not None
    return {"status": "ok" if ready else "not_ready", "runtime": "lightgbm", "model_ready": ready,
            "model_id": MANIFEST["model_id"],
            "bundle_id": MANIFEST["bundle_id"], "feature_schema_id": MANIFEST["feature_schema_id"],
            "input_dimensions": SPEC["dimensions"]["input"], "label_count": len(MANIFEST["models"]),
            "primary_threshold": MANIFEST["primary_threshold"],
            "rdkit_version": rdBase.rdkitVersion,
            "capabilities": {"external_lookup": ALLOW_PUBCHEM, "local_catalog": True,
                             "advanced_smiles": True, "local_prediction": ready}}


@app.post("/fingerprint")
def feature(request: FeatureRequest):
    if request.feature_schema_id != MANIFEST["feature_schema_id"]:
        raise HTTPException(409, detail={"code": "FEATURE_SCHEMA_MISMATCH", "message": "Versi API dan model aplikasi berbeda."})
    smiles = (request.smiles or "").strip()
    name = (request.compound_name or "").strip()
    if bool(smiles) == bool(name):
        raise HTTPException(422, detail={"code": "INVALID_INPUT", "message": "Masukkan SMILES atau nama senyawa."})
    iupac = None
    lookup_source = None
    if name:
        smiles, iupac, lookup_source = lookup_name(name)
    result = calculate(smiles)
    return {**result, "compound_name": name or None, "iupac_name": iupac,
            "lookup_source": lookup_source}


@app.post("/predict")
def predict(request: PredictionRequest):
    if request.bundle_id != MANIFEST["bundle_id"]:
        raise HTTPException(409, detail={"code": "MODEL_BUNDLE_MISMATCH",
            "message": "Paket model dan aplikasi berbeda. Perbarui aplikasi dan layanan lokal bersama."})
    if PREDICTOR is None:
        raise HTTPException(503, detail={"code": "MODEL_NOT_READY",
            "message": "Model lokal belum siap. Jalankan ulang layanan analisis pada komputer."})
    result = feature(request)
    vector = np.asarray(result.pop("fingerprint"), dtype=np.float32)
    try:
        scores = PREDICTOR.predict(vector)
    except Exception as cause:
        raise HTTPException(503, detail={"code": "MODEL_ERROR",
            "message": "Model lokal belum berhasil dijalankan. Periksa terminal layanan pada komputer."}) from cause
    return {**result, "runtime": "lightgbm", "scores": scores,
            "input_dimensions": SPEC["dimensions"]["input"],
            "label_count": len(MANIFEST["labels"]),
            "primary_threshold": MANIFEST["primary_threshold"]}
