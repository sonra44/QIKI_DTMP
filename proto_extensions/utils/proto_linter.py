import os
from pathlib import Path

PROTO_DIR = Path("protos")
LINT_ERRORS = []

def check_oneof_usage(proto_file):
    with open(proto_file, "r") as f:
        content = f.read()
        if "scalar_data" in content and "oneof" not in content:
            LINT_ERRORS.append(f"[WARN] {proto_file}: scalar_data found without oneof")

def check_enum_typing(proto_file):
    with open(proto_file, "r") as f:
        content = f.read()
        if 'status_code' in content and 'enum' not in content:
            LINT_ERRORS.append(f"[WARN] {proto_file}: status_code not declared as enum")

def lint_all():
    print(" Linting .proto files...")
    for proto_file in PROTO_DIR.glob("*.proto"):
        check_oneof_usage(proto_file)
        check_enum_typing(proto_file)

    if not LINT_ERRORS:
        print("✅ No issues found.")
    else:
        for err in LINT_ERRORS:
            print(err)
        print(f"\n❌ {len(LINT_ERRORS)} issues found.")

if __name__ == "__main__":
    lint_all()
