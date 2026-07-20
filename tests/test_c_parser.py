from autoflc.c_parser import extract_functions_from_c


def _extract(code: str):
    return extract_functions_from_c(code.encode("utf-8"))


def test_plain_function():
    funcs = _extract(
        """
        int add(int a, int b)
        {
            return a + b;
        }
        """
    )
    assert len(funcs) == 1
    assert funcs[0]["name"] == "add"
    assert funcs[0]["line_count"] > 0


def test_pointer_return_function():
    funcs = _extract(
        """
        int *get_ptr(int x)
        {
            static int value;
            value = x;
            return &value;
        }
        """
    )
    assert len(funcs) == 1
    assert funcs[0]["name"] == "get_ptr"


def test_parenthesized_declarator():
    funcs = _extract(
        """
        void (CS_AppMain)(void)
        {
            return;
        }
        """
    )
    assert len(funcs) == 1
    assert funcs[0]["name"] == "CS_AppMain"


def test_multiple_functions_in_one_file():
    funcs = _extract(
        """
        int first(void)
        {
            return 1;
        }

        int second(void)
        {
            return 2;
        }
        """
    )
    assert [f["name"] for f in funcs] == ["first", "second"]


def test_no_functions_returns_empty_list():
    funcs = _extract("int global_var = 42;\n")
    assert funcs == []


def test_invalid_input_does_not_raise():
    assert extract_functions_from_c(None) == []
