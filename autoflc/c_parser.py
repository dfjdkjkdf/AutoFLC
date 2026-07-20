from tree_sitter_languages import get_language, get_parser


def get_func_name_from_node(node, code_bytes):
    try:
        curr = node.child_by_field_name("declarator")
        while curr:
            if curr.type == "identifier":
                return code_bytes[curr.start_byte : curr.end_byte].decode("utf-8", errors="ignore")
            if curr.type == "pointer_declarator":
                curr = curr.child_by_field_name("declarator")
                continue
            if curr.type == "function_declarator":
                curr = curr.child_by_field_name("declarator")
                continue
            if curr.type == "parenthesized_declarator":
                # tree-sitter's C grammar doesn't expose a "declarator" field
                # for the wrapped declarator here (unlike pointer_declarator /
                # function_declarator) - it's just the sole named child, e.g.
                # for `void (CS_AppMain)(void)` used to dodge macro expansion.
                named_children = curr.named_children
                curr = named_children[0] if named_children else None
                continue
            break
        return None
    except Exception:
        return None


def extract_functions_from_c(code_bytes, logger=None):
    try:
        language = get_language("c")
        parser = get_parser("c")
        tree = parser.parse(code_bytes)
        root_node = tree.root_node
        functions = []
        query = language.query("(function_definition) @func_def")
        captures = query.captures(root_node)
        for node, tag in captures:
            if tag == "func_def":
                func_name = get_func_name_from_node(node, code_bytes)
                if func_name:
                    func_code = code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
                    line_count = len(func_code.split("\n"))
                    functions.append({"name": func_name, "code": func_code, "line_count": line_count})
        return functions
    except Exception as e:
        if logger:
            logger.error(f"Tree-sitter parse error: {str(e)}")
        return []
