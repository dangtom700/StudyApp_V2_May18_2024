import os
import json

def scan_json_folder(folder_path):
    bad_files = []
    empty_files = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)

                try:
                    # Check if file is empty
                    if os.path.getsize(path) == 0:
                        empty_files.append(path)
                        continue

                    # Try parsing JSON
                    with open(path, "r", encoding="utf-8") as f:
                        json.load(f)

                except json.JSONDecodeError as e:
                    bad_files.append((path, str(e)))
                except Exception as e:
                    bad_files.append((path, f"Other error: {e}"))

    # Report results
    print("\n=== EMPTY FILES ===")
    for f in empty_files:
        print(f)

    print("\n=== MALFORMED JSON FILES ===")
    for f, err in bad_files:
        print(f"\n{f}")
        print(f"  -> {err}")

    print("\n=== SUMMARY ===")
    print(f"Empty files: {len(empty_files)}")
    print(f"Malformed files: {len(bad_files)}")


# Usage
scan_json_folder("data\\token_json")