#!/usr/bin/env python3
import json
from pathlib import Path
import argparse
from typing import Any, Dict, List

NA_TOKENS = {"NA", "N/A", "N A", "NONE", "NULL"}  # case-insensitive

def is_valid_animation(value: Any) -> bool:
    """
    Accepts any non-empty, non-whitespace string that isn't an NA-like token.
    """
    if value is None:
        return False
    s = str(value).strip()
    if s == "":
        return False
    if s.upper() in NA_TOKENS:
        return False
    return True

def filter_dataset(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Keep only items with a valid 'Animation name'.
    """
    filtered = []
    for ex in items:
        anim = ex.get("Animation name")
        if is_valid_animation(anim):
            # Optionally store the trimmed version back (harmless):
            ex["Animation name"] = str(anim).strip()
            filtered.append(ex)
    return filtered

def main():
    parser = argparse.ArgumentParser(description="Downsize exercise dataset by filtering invalid 'Animation name' entries.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("dataset_7.json"),
        help="Path to the input JSON file (default: dataset_7.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to the output JSON file (default: <input.stem>.filtered.json)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Pretty-print JSON with this indent (default: 2). Use 0 or negative for compact.",
    )
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output or input_path.with_name(f"{input_path.stem}.filtered.json")

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Expected the input JSON to be a list of exercise objects.")

    original_count = len(data)
    filtered_data = filter_dataset(data)
    kept_count = len(filtered_data)
    removed_count = original_count - kept_count

    # Write output
    if args.indent and args.indent > 0:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=args.indent)
    else:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(filtered_data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Input:    {input_path}")
    print(f"Output:   {output_path}")
    print(f"Original: {original_count} items")
    print(f"Kept:     {kept_count} items")
    print(f"Removed:  {removed_count} items")

if __name__ == "__main__":
    main()
