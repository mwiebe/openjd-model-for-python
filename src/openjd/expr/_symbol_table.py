# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Symbol table for expression evaluation (RFC 0005)."""

from __future__ import annotations

from typing import Any, Optional, Union

from ._value import ExprValue
from ._types import ExprType

SymbolTableEntry = Union["SymbolTable", ExprValue]


class SymbolTable:
    """Maps names to either child tables or values for expression evaluation.

    Supports dotted key paths for convenient construction and access:
        SymbolTable({"Param.Frame": 42, "Param.Name": "test"})

    Automatically converts Python values to ExprValue:
        - bool, int, float, str, None, list
    """

    __slots__ = ("_table",)

    def __init__(self, source: Optional[Union[SymbolTable, dict[str, Any]]] = None):
        self._table: dict[str, SymbolTableEntry] = {}
        if source is not None:
            if isinstance(source, SymbolTable):
                self._table.update(source._table)
            elif isinstance(source, dict):
                for k, v in source.items():
                    self._set_path(k, v)

    def _set_path(self, key: str, value: Any) -> None:
        """Set a value at a dotted path, creating intermediate SymbolTables as needed."""
        parts = key.split(".")
        if len(parts) == 1:
            self._table[key] = self._convert_value(value)
        else:
            # Navigate/create intermediate tables
            current = self
            for part in parts[:-1]:
                if part not in current._table:
                    current._table[part] = SymbolTable()
                entry = current._table[part]
                if not isinstance(entry, SymbolTable):
                    raise ValueError(f"Cannot set '{key}': '{part}' is not a table")
                current = entry
            current._table[parts[-1]] = self._convert_value(value)

    def _convert_value(self, value: Any) -> SymbolTableEntry:
        """Convert a value to a SymbolTableEntry.

        ExprType values are automatically wrapped as ExprValue.unresolved(T),
        enabling convenient construction of symbol tables for type checking.
        """
        if isinstance(value, (SymbolTable, ExprValue)):
            return value
        if isinstance(value, ExprType):
            return ExprValue.unresolved(value)
        if isinstance(value, dict):
            return SymbolTable(value)
        return ExprValue(value)

    def _walk_path(self, key: str) -> Optional[SymbolTableEntry]:
        """Walk a dotted path and return the entry, or None if not found."""
        parts = key.split(".")
        current: SymbolTableEntry = self
        for part in parts:
            if not isinstance(current, SymbolTable):
                return None
            entry = current._table.get(part)
            if entry is None:
                return None
            current = entry
        return current

    def __contains__(self, name: str) -> bool:
        if "." in name:
            return self._walk_path(name) is not None
        return name in self._table

    def __getitem__(self, name: str) -> SymbolTableEntry:
        if "." in name:
            result = self._walk_path(name)
            if result is None:
                raise KeyError(name)
            return result
        return self._table[name]

    def __setitem__(self, name: str, value: Any) -> None:
        self._set_path(name, value)

    def get(self, name: str) -> Optional[SymbolTableEntry]:
        if "." in name:
            return self._walk_path(name)
        return self._table.get(name)

    def __repr__(self) -> str:
        return f"SymbolTable({self._table})"

    @property
    def keys(self) -> set[str]:
        """Return the set of top-level keys in this symbol table."""
        return set(self._table.keys())
