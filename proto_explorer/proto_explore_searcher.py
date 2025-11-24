"""
Proto Explorer (with search)
"""
import argparse
import importlib
import inspect
import os
import re
from re import Pattern
import sys
from typing import Dict
import streamlit as st
from google.protobuf.descriptor import Descriptor, FieldDescriptor

GITHUB_URL = "https://github.com/yuanlott/grpc"

TYPE_NAMES: Dict[int, str] = {
    v: k.replace("TYPE_", "")
    for k, v in FieldDescriptor.__dict__.items()
    if k.startswith("TYPE_")
}


def validate_proto_module(module_name: str) -> bool:
    """
    Verify that the compiled proto module exists
    """
    try:
        __import__(module_name)
        return True
    except ModuleNotFoundError as e:
        missing = e.name
        raise ImportError(
            f"Failed to import '{module_name}'. Missing: '{missing}'."
        ) from e


def parse_args():
    """
    Parse command line arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--load_path", "-p")
    parser.add_argument("--proto_module", "-m", required=True)
    args = parser.parse_args()
    if args.load_path:
        abs_path = os.path.abspath(args.load_path)
        if not os.path.isdir(abs_path):
            raise ValueError(f"Invalid load_path: {args.load_path}")
        sys.path.insert(0, abs_path)
    importlib.util.find_spec(args.proto_module)
    validate_proto_module(args.proto_module)
    return args

@st.cache_resource
def load_proto_module(module_name: str, search_path: str | None):
    """
    Import compiled proto module
    """
    if search_path and search_path not in sys.path:
        sys.path.insert(0, os.path.abspath(search_path))
    return importlib.import_module(module_name)


def list_message_types(module):
    messages = {}
    for _, obj in inspect.getmembers(module):
        if isinstance(obj, Descriptor):
            messages[obj.full_name] = obj
    return messages


def descriptor_matches(desc, regex, seen=None):
    if not regex:
        return False
    if seen is None:
        seen = set()
    if desc.full_name in seen:
        return False
    seen.add(desc.full_name)
    if regex.search(desc.full_name):
        return True
    for f in desc.fields:
        if regex.search(f.name):
            return True
        if f.type == FieldDescriptor.TYPE_MESSAGE and f.message_type:
            if regex.search(f.message_type.full_name):
                return True
            if descriptor_matches(f.message_type, regex, seen):
                return True
        if f.type == FieldDescriptor.TYPE_ENUM and f.enum_type:
            if regex.search(f.enum_type.full_name):
                return True
    return False


def show_message(
        desc,
        depth: int = 0,
        shown: set[str] | None = None,
        regex: Pattern | None = None,
        filter_mode: bool = False
):
    if shown is None:
        shown = set()
    if desc.full_name in shown:
        return
    shown.add(desc.full_name)

    match_here = regex.search(desc.full_name) if regex else False

    # expander TITLE → must be plain
    header_plain = desc.full_name
    # expander BODY → can contain HTML highlighting
    header_display = desc.full_name
    if match_here:
        header_display = regex.sub(
            lambda m: f"<mark>{m.group()}</mark>", header_display
        )

    expand = bool(depth == 0 or (regex and descriptor_matches(desc, regex)))

    with st.expander(header_plain, expanded=expand):
        # Show highlighted header inside if matched
        if regex:
            st.markdown(f"**{header_display}**", unsafe_allow_html=True)
        else:
            st.markdown(f"**{header_plain}**")

        for field in desc.fields:
            is_map = (
                field.type == FieldDescriptor.TYPE_MESSAGE
                and field.message_type
                and field.message_type.GetOptions().map_entry
            )
            if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type:
                if is_map:
                    key_type = TYPE_NAMES.get(field.message_type.fields_by_name["key"].type, "UNKNOWN")
                    v = field.message_type.fields_by_name["value"]
                    if v.type == FieldDescriptor.TYPE_MESSAGE and v.message_type:
                        val = v.message_type.full_name
                    else:
                        val = TYPE_NAMES.get(v.type, "UNKNOWN")
                    type_name = f"map<{key_type},{val}>"
                else:
                    type_name = field.message_type.full_name
            elif field.type == FieldDescriptor.TYPE_ENUM and field.enum_type:
                type_name = field.enum_type.full_name
            else:
                type_name = TYPE_NAMES.get(field.type, str(field.type))

            label = f"- {field.name}: {type_name}"
            match_field = regex.search(label) if regex else False

            if (
                field.type == FieldDescriptor.TYPE_MESSAGE and
                field.message_type is not None
            ):
                if (
                    regex
                    and not match_field
                    and not descriptor_matches(field.message_type, regex)
                ):
                    if filter_mode:
                        continue

            if match_field:
                label = regex.sub(lambda m: f"<mark>{m.group()}</mark>", label)

            st.markdown(" " * depth * 2 + label, unsafe_allow_html=True)

            if field.type == FieldDescriptor.TYPE_MESSAGE and not is_map:
                show_message(
                    field.message_type, depth+1, shown, regex, filter_mode
                )


def main():
    args = parse_args()
    st.set_page_config(page_title="Proto Explorer", layout="wide")

    st.title("🧭 Proto Explorer")

    module = load_proto_module(args.proto_module, search_path=args.load_path)
    messages = list_message_types(module)
    if not messages:
        st.warning("No messages found.")
        return

    selected = st.sidebar.selectbox("Select message", sorted(messages.keys()))
    search_str = st.sidebar.text_input("Regex Search")
    filter_mode = st.sidebar.checkbox("Show only matching branches")

    try:
        regex = re.compile(search_str) if search_str else None
    except re.error:
        st.sidebar.error("Invalid regex")
        regex = None

    show_message(messages[selected], regex=regex, filter_mode=filter_mode)


if __name__ == "__main__":
    main()
