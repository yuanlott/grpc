import argparse
import importlib
import inspect
import os
import sys
import streamlit as st
from google.protobuf.descriptor import Descriptor, FieldDescriptor
from typing import Dict


GITHUB_URL = "https://github.com/yuanlott/grpc"

# A mapping from protobuf field type integer values to their corresponding
# string names. Created by inverting the FieldDescriptor.TYPE_* constants.
# No official constant table is exported by the protobuf package for numeric
# type IDs, so here we generate it dynamically from the library itself.
# Expected contents: {
# 1: "DOUBLE", 2: "FLOAT", 3: "INT64", 4: "UINT64", 5: "INT32", 6: "FIXED64",
# 7: "FIXED32", 8: "BOOL", 9: "STRING", 11: "MESSAGE", 12: "BYTES",
# 13: "UINT32", 14: "ENUM", 15: "SFIXED32", 16: "SFIXED64", 17: "SINT32",
# 18: "SINT64",
# }
TYPE_NAMES: Dict[int, str] = {
    v: k.replace("TYPE_", "")
    for k, v in FieldDescriptor.__dict__.items()
    if k.startswith("TYPE_")
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Interactive viewer for gRPC .proto hierarchies."
    )
    parser.add_argument(
        "--load_path",
        "-p",
        help="Path to directory containing _pb2.py files (will added to runtime sys.path).",
        required=False,
    )
    parser.add_argument(
        "--proto_module",
        "-m",
        help="Python module name of the _pb2 file to load, e.g. myproject.datamanager.users_pb2.",
        required=True,
    )
    args = parser.parse_args()

    # Validate --load_path
    if args.load_path:
        abs_path = os.path.abspath(args.load_path)
        if not os.path.isdir(abs_path):
            raise ValueError(f"--load_path '{args.load_path}' is not a valid directory")
        sys.path.insert(0, abs_path)

    # Validate --module import
    spec = importlib.util.find_spec(args.proto_module)
    if spec is None:
        raise ValueError(
            f"Cannot import module '{args.proto_module}'. "
            f"Ensure it exists and check --load_path"
        )

    return args


@st.cache_resource
def load_proto_module(module_name: str, search_path: str = None):
    """Import a compiled _pb2 module dynamically, optionally from a custom path."""
    if search_path and search_path not in sys.path:
        sys.path.insert(0, os.path.abspath(search_path))
    return importlib.import_module(module_name)


def list_message_types(module):
    """Return all top-level message types from a _pb2 module."""
    messages = {}
    for _, obj in inspect.getmembers(module):
        if isinstance(obj, Descriptor):
            messages[obj.full_name] = obj
    return messages


def show_message(desc: Descriptor, depth=0, shown=None):
    """Recursively show fields of a protobuf message descriptor, including oneof hierarchies."""
    if shown is None:
        shown = set()

    if desc.full_name in shown:
        st.write(f"{'  ' * depth}↪ {desc.full_name} (recursive)")
        return

    shown.add(desc.full_name)

    # Map of oneof_name → fields
    oneof_fields = {}
    for field in desc.fields:
        if field.containing_oneof:
            oneof_name = field.containing_oneof.name
            oneof_fields.setdefault(oneof_name, []).append(field)

    # Regular (non-oneof) fields
    regular_fields = [f for f in desc.fields if not f.containing_oneof]

    with st.expander(f"{desc.full_name}", expanded=(depth == 0)):
        # Regular fields
        for field in regular_fields:
            # Detect map fields (they are synthetic message types with 'key' and 'value')
            is_map = (
                field.type == FieldDescriptor.TYPE_MESSAGE
                and field.message_type
                and field.message_type.GetOptions().map_entry
            )

            # Resolve readable type name
            if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type:
                if is_map:
                    key_type = TYPE_NAMES.get(
                        field.message_type.fields_by_name["key"].type, "UNKNOWN"
                    )
                    value_field = field.message_type.fields_by_name["value"]
                    if (
                        value_field.type == FieldDescriptor.TYPE_MESSAGE
                        and value_field.message_type
                    ):
                        value_type = value_field.message_type.full_name
                    else:
                        value_type = TYPE_NAMES.get(value_field.type, "UNKNOWN")
                    type_name = f"map<{key_type}, {value_type}>"
                else:
                    type_name = field.message_type.full_name
            elif field.type == FieldDescriptor.TYPE_ENUM and field.enum_type:
                type_name = field.enum_type.full_name
            else:
                type_name = getattr(field, "type_name", None) or TYPE_NAMES.get(
                    field.type, str(field.type)
                )

            # Field label
            label = f"- {field.name}: {type_name}"
            if field.is_repeated and not is_map:
                label += " [repeated]"

            # Render message field recursively
            if (
                field.type == FieldDescriptor.TYPE_MESSAGE
                and not is_map
                and field.message_type
            ):
                st.markdown(f"{' ' * depth * 2}{label}")
                show_message(field.message_type, depth + 1, shown)
            else:
                st.markdown(f"{' ' * depth * 2}{label}")

        # Oneof groups
        for oneof_name, fields in oneof_fields.items():
            st.markdown(f"{' ' * depth * 2}- **{oneof_name}:** _(oneof)_")
            nb_indent = "\u00a0" * ((depth + 1) * 2)  # non-breaking spaces
            with st.expander(f"{nb_indent}(oneof options)", expanded=False):
                for field in fields:
                    is_map = (
                        field.type == FieldDescriptor.TYPE_MESSAGE
                        and field.message_type
                        and field.message_type.GetOptions().map_entry
                    )

                    if (
                        field.type == FieldDescriptor.TYPE_MESSAGE
                        and field.message_type
                    ):
                        if is_map:
                            key_type = TYPE_NAMES.get(
                                field.message_type.fields_by_name["key"].type, "UNKNOWN"
                            )
                            value_field = field.message_type.fields_by_name["value"]
                            if (
                                value_field.type == FieldDescriptor.TYPE_MESSAGE
                                and value_field.message_type
                            ):
                                value_type = value_field.message_type.full_name
                            else:
                                value_type = TYPE_NAMES.get(value_field.type, "UNKNOWN")
                            type_name = f"map<{key_type}, {value_type}>"
                        else:
                            type_name = field.message_type.full_name
                    elif field.type == FieldDescriptor.TYPE_ENUM and field.enum_type:
                        type_name = field.enum_type.full_name
                    else:
                        type_name = getattr(field, "type_name", None) or TYPE_NAMES.get(
                            field.type, str(field.type)
                        )

                    label = f"- {field.name}: {type_name}"

                    if field.is_repeated and not is_map:
                        label += " [repeated]"

                    if (
                        field.type == FieldDescriptor.TYPE_MESSAGE
                        and not is_map
                        and field.message_type
                    ):
                        st.markdown(f"{' ' * (depth + 1) * 2}{label}")
                        show_message(field.message_type, depth + 2, shown)
                    else:
                        st.markdown(f"{' ' * (depth + 1) * 2}{label}")


def main():
    args = parse_args()
    st.set_page_config(
        page_title="Proto Explorer",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        /* Reduce space between expander rows */
        .block-container {
            padding-top: 2.5rem;
        }

        /* Reduce space inside expanders */
        div.streamlit-expanderHeader {
            padding-top: 0.15rem;
            padding-bottom: 0.15rem;
        }

        /* Reduce spacing between Markdown list rows */
        .block-container li {
            margin-bottom: 0.1rem;
        }

        .block-container p {
            margin-bottom: 0.1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Header layout
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.title("🧭 Proto Explorer")
        st.caption("Interactive Protobuf Explorer for compiled *_pb2.py modules")

    with col2:
        st.markdown(
            f"""
            <a href="{GITHUB_URL}" target="_blank">
                <img src="https://img.shields.io/badge/GitHub-Repo-black?style=for-the-badge&logo=github" />
            </a>
            """,
            unsafe_allow_html=True,
        )

    with st.sidebar:
        st.markdown("### Proto Explorer")
        st.markdown("Navigate gRPC message hierarchies.")
        st.markdown("---")

    module_name = args.proto_module
    custom_path = args.load_path

    try:
        module = load_proto_module(module_name, search_path=custom_path)
    except ModuleNotFoundError as e:
        st.error(f"Could not import `{module_name}`. Check the path.\n\n{e}")
        return

    messages = list_message_types(module)
    if not messages:
        st.warning("No message types found in this module.")
        return

    selected = st.sidebar.selectbox("Select a message type", sorted(messages.keys()))
    show_message(messages[selected])


if __name__ == "__main__":
    main()
