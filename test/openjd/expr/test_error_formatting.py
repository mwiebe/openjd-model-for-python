# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for error message formatting with caret pointers."""

import pytest

from openjd.expr import evaluate_expression, SymbolTable, ExprValue, ExprType
from openjd.expr import PathFormat
from openjd.expr import ExpressionError, ExpressionTypeError


class TestErrorCaretPointers:
    """Test that error messages include expression with caret pointing to error location."""

    def test_type_error_in_middle(self):
        """Error in middle of expression points to correct subexpression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 + int('bad') + 2", values=SymbolTable())
        expected = [
            "Cannot convert 'bad' to int\n",
            "  1 + int('bad') + 2\n",
            "      ^~~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_type_error_at_end(self):
        """Error at end of expression points to correct subexpression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 + 2 + int('bad')", values=SymbolTable())
        expected = [
            "Cannot convert 'bad' to int\n",
            "  1 + 2 + int('bad')\n",
            "          ^~~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_type_error_at_start(self):
        """Error at start of expression points to correct subexpression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("int('bad') + 1 + 2", values=SymbolTable())
        expected = [
            "Cannot convert 'bad' to int\n",
            "  int('bad') + 1 + 2\n",
            "  ^~~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_operator_error_friendly_name(self):
        """Operator errors use friendly names like '+' instead of '__add__'."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("'hello' + 5", values=SymbolTable())
        expected = [
            "Cannot use '+' operator with string and int\n",
            "  'hello' + 5\n",
            "  ~~~~~~~~^~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_operator_error_in_middle(self):
        """Operator error in middle points to the operator subexpression."""
        symtab = SymbolTable(
            {
                "Param": SymbolTable(
                    {
                        "A": ExprValue(5),
                        "B": ExprValue("hello"),
                    }
                )
            }
        )
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 + (Param.A + Param.B) + 2", values=symtab)
        expected = [
            "Cannot use '+' operator with int and string\n",
            "  1 + (Param.A + Param.B) + 2\n",
            "       ~~~~~~~~^~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_division_by_zero_in_middle(self):
        """Division by zero in middle points to the division."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("10 + 5 / 0 + 2", values=SymbolTable())
        expected = [
            "Division by zero\n",
            "  10 + 5 / 0 + 2\n",
            "       ~~^~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_index_out_of_bounds_shows_length(self):
        """Index error shows list length and points to subscript."""
        symtab = SymbolTable(
            {
                "Param": SymbolTable(
                    {
                        "List": ExprValue([1, 2, 3]),
                    }
                )
            }
        )
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("Param.List[10] + 1", values=symtab)
        expected = [
            "Index 10 out of bounds for list of length 3\n",
            "  Param.List[10] + 1\n",
            "  ~~~~~~~~~~^~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unknown_property_friendly_name(self):
        """Unknown property uses friendly name instead of __property_X__."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("path('/a/b').unknown", values=SymbolTable())
        expected = [
            "Cannot access attribute 'unknown' on path\n",
            "  path('/a/b').unknown\n",
            "  ~~~~~~~~~~~~~^~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unknown_property_in_chain(self):
        """Unknown property in chain points at the unknown attribute."""
        symtab = SymbolTable(
            {
                "Param": SymbolTable(
                    {
                        "X": ExprValue(
                            "/test/file.exr", type=ExprType("path"), path_format=PathFormat.POSIX
                        )
                    }
                )
            }
        )
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("Param.X.name.unknown", values=symtab, path_format=PathFormat.POSIX)
        expected = [
            "Cannot access attribute 'unknown' on string\n",
            "  Param.X.name.unknown\n",
            "  ~~~~~~~~~~~~~^~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_min_empty_list_error(self):
        """Function error in middle points to the function call."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 + min([]) + 2", values=SymbolTable())
        expected = [
            "min() requires a non-empty list\n",
            "  1 + min([]) + 2\n",
            "      ^~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_split_empty_separator(self):
        """Method error points to the method name."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("10 + 'x'.split('') + 5", values=SymbolTable())
        expected = [
            "split failed: empty separator\n",
            "  10 + 'x'.split('') + 5\n",
            "       ~~~~^~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_deeply_nested_error(self):
        """Error in deeply nested expression points to innermost error."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 + (2 + (3 + int('x')))", values=SymbolTable())
        expected = [
            "Cannot convert 'x' to int\n",
            "  1 + (2 + (3 + int('x')))\n",
            "                ^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_error_in_function_argument(self):
        """Error in function argument points to the argument."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("min(1, int('x'), 3)", values=SymbolTable())
        expected = [
            "Cannot convert 'x' to int\n",
            "  min(1, int('x'), 3)\n",
            "         ^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_error_in_condition(self):
        """Error in conditional expression points to the condition."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 if int('x') else 2", values=SymbolTable())
        expected = [
            "Cannot convert 'x' to int\n",
            "  1 if int('x') else 2\n",
            "       ^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_error_in_comprehension_body(self):
        """Error in list comprehension body points to the error."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("[x + int('y') for x in [1,2,3]]", values=SymbolTable())
        expected = [
            "Cannot convert 'y' to int\n",
            "  [x + int('y') for x in [1,2,3]]\n",
            "       ^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_error_in_comprehension_filter(self):
        """Error in list comprehension filter points to the error."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("[x for x in [1,2,3] if int('bad')]", values=SymbolTable())
        expected = [
            "Cannot convert 'bad' to int\n",
            "  [x for x in [1,2,3] if int('bad')]\n",
            "                         ^~~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_chained_method_error(self):
        """Error in chained method call points to the method name."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("'a'.upper() + 'b'.split('')[0]", values=SymbolTable())
        expected = [
            "split failed: empty separator\n",
            "  'a'.upper() + 'b'.split('')[0]\n",
            "                ~~~~^~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_undefined_variable(self):
        """Undefined variable error points to the attribute name."""
        symtab = SymbolTable(
            {
                "Param": SymbolTable(
                    {
                        "InputFile": ExprValue(
                            "/test/file.exr", type=ExprType("path"), path_format=PathFormat.POSIX
                        ),
                    }
                )
            }
        )
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("Param.InputFiel + 1", values=symtab)
        expected = [
            "Undefined variable: 'Param.InputFiel'. Did you mean: Param.InputFile\n",
            "  Param.InputFiel + 1\n",
            "  ~~~~~~^~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_float_literal_infinity(self):
        """Float literal that overflows to infinity points to the literal."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1e3000")
        expected = [
            "Float operation produced infinity\n",
            "  1e3000\n",
            "  ^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_float_literal_infinity_in_expression(self):
        """Float literal overflow in a larger expression points to the literal."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1e3000 + 1")
        expected = [
            "Float operation produced infinity\n",
            "  1e3000 + 1\n",
            "  ^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)


class TestErrorCaretWithWhitespace:
    """Test that leading whitespace is handled correctly."""

    def test_leading_whitespace_stripped(self):
        """Leading whitespace is stripped from expression in error."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("   int('bad')", values=SymbolTable())
        # Should show stripped expression, not original with leading spaces
        expected = [
            "Cannot convert 'bad' to int\n",
            "  int('bad')\n",
            "  ^~~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_leading_whitespace_error_in_middle(self):
        """Leading whitespace stripped, caret still points correctly."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("   1 + int('bad') + 2", values=SymbolTable())
        expected = [
            "Cannot convert 'bad' to int\n",
            "  1 + int('bad') + 2\n",
            "      ^~~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)


class TestSyntaxErrorCarets:
    """Test that syntax errors include caret pointers."""

    def test_unclosed_paren(self):
        """Unclosed parenthesis shows caret spanning the expression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("(1 + 2", values=SymbolTable())
        expected = [
            "Syntax error: unexpected EOF while parsing\n",
            "  (1 + 2\n",
            "  ^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unclosed_bracket(self):
        """Unclosed bracket shows caret spanning the expression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("[1, 2, 3", values=SymbolTable())
        expected = [
            "Syntax error: unexpected EOF while parsing\n",
            "  [1, 2, 3\n",
            "  ^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unclosed_string(self):
        """Unclosed string shows caret spanning the string."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("'unclosed", values=SymbolTable())
        expected = [
            "Syntax error: missing closing quote in string literal\n",
            "  'unclosed\n",
            "  ^~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)


class TestMultiLineExpressions:
    """Tests for error formatting in multi-line expressions."""

    def test_error_in_parentheses_multiline(self):
        """Error on second line of parenthesized expression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("(\n  1 + 'x'\n)", values=SymbolTable())
        expected = [
            "Cannot use '+' operator with int and string\n",
            "    1 + 'x'\n",
            "    ~~~^~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_error_in_list_multiline(self):
        """Error on third line of list expression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("[\n  1,\n  2 + 'x',\n  3\n]", values=SymbolTable())
        expected = [
            "Cannot use '+' operator with int and string\n",
            "    2 + 'x',\n",
            "    ~~~^~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_error_on_first_line_multiline(self):
        """Error on first line when expression continues."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 + 'x' + (\n2)", values=SymbolTable())
        expected = [
            "Cannot use '+' operator with int and string\n",
            "  1 + 'x' + (\n",
            "  ~~~^~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_deeply_nested_multiline(self):
        """Error in deeply nested multi-line expression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("(\n  [\n    1 + 'x'\n  ]\n)", values=SymbolTable())
        expected = [
            "Cannot use '+' operator with int and string\n",
            "      1 + 'x'\n",
            "      ~~~^~~~",
        ]
        assert str(exc_info.value) == "".join(expected)


class TestImplicitLineContinuation:
    """Tests for multi-line expressions without explicit continuation."""

    def test_multiline_addition(self):
        """Multi-line addition works without backslash or parens."""
        result = evaluate_expression("1 +\n2", values=SymbolTable())
        assert result.item() == 3

    def test_multiline_comparison(self):
        """Multi-line comparison works."""
        result = evaluate_expression("1 <\n2", values=SymbolTable())
        assert result.item() is True

    def test_multiline_error_shows_correct_line(self):
        """Error in multi-line expression shows the correct line."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 +\n'x'", values=SymbolTable())
        expected = [
            "Cannot use '+' operator with int and string\n",
            "  1 +\n",
            "  ~~^",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_multiline_three_lines(self):
        """Three-line expression works."""
        result = evaluate_expression("1 +\n2 +\n3", values=SymbolTable())
        assert result.item() == 6


class TestImprovedErrorMessages:
    """Tests for improved error messages with helpful suggestions."""

    def test_wrong_arg_count_zero(self):
        """Error when calling function with zero args shows expected count."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("len()")
        expected = [
            "len() takes 1 argument(s), but 0 were given\n",
            "  len()\n",
            "  ^~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_wrong_arg_count_too_many(self):
        """Error when calling function with too many args shows expected count."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("len(1, 2)")
        expected = [
            "len() takes 1 argument(s), but 2 were given\n",
            "  len(1, 2)\n",
            "  ^~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_wrong_arg_count_multiple_arities(self):
        """Error shows all valid arities when function has multiple signatures."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("min()")
        expected = [
            "min() takes 1, 2, 3 arguments, but 0 were given\n",
            "  min()\n",
            "  ^~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_method_on_wrong_type(self):
        """Error when calling method on wrong type shows available types."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('path("/a/b").startswith("/a")')
        expected = [
            "startswith() is not available for path. Available for: string\n",
            '  path("/a/b").startswith("/a")\n',
            "  ~~~~~~~~~~~~~^~~~~~~~~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_method_on_wrong_type_upper(self):
        """Error when calling upper() on wrong type shows available types."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("(5).upper()")
        expected = [
            "upper() is not available for int. Available for: string\n",
            "  (5).upper()\n",
            "  ~~~^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_property_on_wrong_type(self):
        """Error when accessing property on wrong type shows available types."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("True.stem")
        expected = [
            "'stem' property is not available for bool. Available for: path\n",
            "  True.stem\n",
            "  ~~~~~^~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_property_on_wrong_type_parent(self):
        """Error when accessing parent property on wrong type."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('"hello".parent')
        expected = [
            "'parent' property is not available for string. Available for: path\n",
            '  "hello".parent\n',
            "  ~~~~~~~~^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_attribute_without_call(self):
        """Error when accessing method as property suggests adding parentheses."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('"hello".upper')
        expected = [
            "'upper' is a method, not a property. Did you mean upper()?\n",
            '  "hello".upper\n',
            "  ~~~~~~~~^~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_attribute_without_call_split(self):
        """Error when accessing split as property suggests adding parentheses."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('"a,b,c".split')
        expected = [
            "'split' is a method, not a property. Did you mean split()?\n",
            '  "a,b,c".split\n',
            "  ~~~~~~~~^~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_property_called_as_method(self):
        """Error when calling property as method suggests removing parentheses."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('path("/a/b").stem()')
        expected = [
            "'stem' is a property, not a method. Use .stem instead of .stem()\n",
            '  path("/a/b").stem()\n',
            "  ~~~~~~~~~~~~~^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)
