# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from ._format_string import FormatString, FormatStringError


def escape_format_string(value: str) -> str:
    """Escape a string so it can be used as a literal value in a format string field.

    Replaces ``{{`` with ``{{ "{{" }}`` and ``}}`` with ``{{ "}" + "}" }}`` so
    that the format string parser treats them as literal text rather than
    expression delimiters. Requires the EXPR extension to be enabled.

    Note: ``}}`` cannot be placed inside a string literal within ``{{ }}``
    because the format string parser finds the ``}}`` closing delimiter before
    the expression parser sees the string content. The concatenation form
    ``"}" + "}"`` avoids this.
    """
    result: list[str] = []
    i = 0
    while i < len(value):
        if value[i : i + 2] == "{{":
            result.append('{{ "{{" }}')
            i += 2
        elif value[i : i + 2] == "}}":
            result.append('{{ "}" + "}" }}')
            i += 2
        else:
            result.append(value[i])
            i += 1
    return "".join(result)


__all__ = ["FormatString", "FormatStringError", "escape_format_string"]
