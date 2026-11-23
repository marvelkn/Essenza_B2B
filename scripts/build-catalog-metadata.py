"""Build local catalog display metadata from the frozen v7 dataset sources."""

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "src/assets/catalog"
SOURCE_REVISION = "8054ea98ed675005ec10e67359902f500e4911b0"
CAS_PATTERN = re.compile(r"[1-9][0-9]{1,6}-[0-9]{2}-[0-9]")
CAS_TABLES = {
    "leffingwell": ("leffingwell/stimuli.csv", "cas"),
    "arctander": ("arctander_1960/stimuli.csv", "CAS"),
}
DISPLAY_NAMES = {13: ("Stilbene", "C(=Cc1ccccc1)c1ccccc1")}


def verify_hash(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"Checksum mismatch: {path}")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_cas(value):
    if CAS_PATTERN.fullmatch(value) is None:
        return False
    digits = value.replace("-", "")
    checksum = sum(index * int(digit) for index, digit in enumerate(digits[-2::-1], 1))
    return checksum % 10 == int(digits[-1])


def read_stimulus_cas(path, column):
    records = defaultdict(set)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            value = row[column].strip()
            if valid_cas(value):
                records[row["Stimulus"].strip().removesuffix(".0")].add(value)
    return records


def unique_structure_cas(provenance, stimulus_cas, ambiguous):
    structures_by_cas = defaultdict(set)
    for row in provenance:
        source = row["source"]
        stimulus = str(row["stimulus"]).strip().removesuffix(".0")
        if source == "goodscents" and valid_cas(stimulus):
            structures_by_cas[stimulus].add(row["smiles"])
        for value in stimulus_cas.get(source, {}).get(stimulus, ()):
            structures_by_cas[value].add(row["smiles"])

    # A CAS checksum checks syntax. The frozen audit and source mappings check conflicts.
    cas_by_structure = defaultdict(set)
    for value, structures in structures_by_cas.items():
        if value not in ambiguous and len(structures) == 1:
            cas_by_structure[next(iter(structures))].add(value)
    return {smiles: next(iter(values)) for smiles, values in cas_by_structure.items() if len(values) == 1}


def build(backend_root, catalog_path):
    dataset = backend_root / "data/builds/perfume-five-grouped-v2"
    manifest = read_json(dataset / "dataset_manifest.json")
    catalog = read_json(catalog_path)
    if manifest["source_revision"] != SOURCE_REVISION or catalog["source_revision"] != SOURCE_REVISION:
        raise ValueError("Unexpected source revision")
    if catalog["source_records_sha256"] != manifest["files"]["records.csv"]:
        raise ValueError("Catalog and frozen data disagree")
    for filename in ("audit.json", "provenance.json", "records.csv", "sources.json"):
        verify_hash(dataset / filename, manifest["files"][filename])

    # Keep the ID-based sidecar tied to the exact original catalog structures.
    with (dataset / "records.csv").open(encoding="utf-8", newline="") as stream:
        frozen_structures = {int(row["source_row"]): row["smiles"] for row in csv.DictReader(stream)}
    compounds = {entry["id"]: entry for entry in catalog["compounds"]}
    catalog_structures = {item_id: entry["smiles"] for item_id, entry in compounds.items()}
    if len(compounds) != len(catalog["compounds"]) or catalog_structures != frozen_structures:
        raise ValueError("Catalog IDs or structures differ from the frozen data")

    sources = read_json(dataset / "sources.json")
    snapshots = backend_root / "data/snapshots/perfume-five-v1" / SOURCE_REVISION
    stimulus_cas = {}
    for source, (relative, column) in CAS_TABLES.items():
        path = snapshots / relative
        verify_hash(path, sources[relative]["sha256"])
        stimulus_cas[source] = read_stimulus_cas(path, column)

    ambiguous = set(read_json(dataset / "audit.json")["ambiguous_cas"])
    provenance = read_json(dataset / "provenance.json")
    cas_by_structure = unique_structure_cas(provenance, stimulus_cas, ambiguous)
    metadata = {}
    for item_id, entry in sorted(compounds.items()):
        cas = cas_by_structure.get(entry["smiles"])
        if cas:
            metadata[str(item_id)] = {"cas": cas}

    # Promote only an existing alias of the exact curated structure.
    for item_id, (display_name, smiles) in DISPLAY_NAMES.items():
        entry = compounds[item_id]
        aliases = {alias.casefold() for alias in entry["aliases"]}
        if entry["smiles"] != smiles or display_name.casefold() not in aliases:
            raise ValueError(f"Curated display name no longer matches catalog entry {item_id}")
        metadata.setdefault(str(item_id), {})["displayName"] = display_name
    return dict(sorted(metadata.items(), key=lambda item: int(item[0])))


def write_metadata(path, metadata):
    lines = [f"  {json.dumps(item_id)}: {json.dumps(item, ensure_ascii=False)}" for item_id, item in metadata.items()]
    path.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-root", required=True, type=Path)
    parser.add_argument("--catalog", type=Path, default=CATALOG_DIR / "compounds.json")
    parser.add_argument("--output", type=Path, default=CATALOG_DIR / "compound-metadata.json")
    args = parser.parse_args()
    metadata = build(args.backend_root, args.catalog)
    write_metadata(args.output, metadata)
    count = sum("cas" in item for item in metadata.values())
    print(f"Wrote {len(metadata)} metadata entries ({count} with CAS) to {args.output}")
