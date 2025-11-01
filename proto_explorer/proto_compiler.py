"""
Module to compile .proto file into Python _pb2 modules
"""
import os
import sys
import tempfile
from pathlib import Path
from grpc_tools import protoc

from .proto_finder import find_proto_root

def compile_proto(proto_file: str | Path, out_dir: str | Path | None = None) -> Path:
    """
    Compile a given .proto file (and its imports) into Python _pb2 modules
    using grpc_tools.protoc.

    Args:
        proto_file: Path to the .proto source file.
        out_dir: Optional output directory for generated _pb2 files.
                 If not specified, a temporary directory will be created.

    Returns:
        Path to the output directory containing generated _pb2 files.

    Raises:
        RuntimeError if protoc fails.
    """
    proto_file = Path(proto_file).resolve()
    if not proto_file.exists():
        raise FileNotFoundError(f"Proto file not found: {proto_file}")

    # Step 1. Find the proto root
    proto_root = find_proto_root(proto_file)
    print(f"📂 Detected proto root: {proto_root}")

    # Step 2. Build include paths
    include_paths = [proto_root]

    # Optionally include googleapis-common-protos, if available
    try:
        import google
        # Handle namespace package
        if hasattr(google, "__path__"):
            gapi_root = Path(list(google.__path__)[0]).parent
            include_paths.append(gapi_root)
        elif hasattr(google, "__file__"):
            gapi_root = Path(google.__file__).parent.parent
            include_paths.append(gapi_root)
    except ImportError:
        pass

    # Step 3. Determine output directory
    if out_dir is None:
        tmpdir = Path(tempfile.mkdtemp(prefix="protoexplorer_gen_"))
        output_dir = tmpdir
        is_temp = True
    else:
        output_dir = Path(out_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        is_temp = False

    # Step 4. Construct protoc args
    cmd = [
        "grpc_tools.protoc",
        f"--proto_path={proto_root}",
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        str(proto_file),
    ]
    for inc in include_paths[1:]:
        cmd.insert(1, f"--proto_path={inc}")

    print(f"Compiling proto: {proto_file.name}")
    print(f"Protoc cmd: {cmd}")
    print("  Include paths:")
    for inc in include_paths:
        print(f"    - {inc}")
    print(f"  Output dir: {output_dir}")

    # Step 5. Run protoc
    result = protoc.main(cmd)

    if result != 0:
        raise RuntimeError(f"Failed to compile {proto_file.name} (exit code {result})")

    print(f"Compilation succeeded. Output dir: {output_dir}")
    return output_dir
