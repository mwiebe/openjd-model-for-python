# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from contextlib import contextmanager
from typing import Annotated, Any, Union, Dict, Optional, TYPE_CHECKING

from pydantic import ValidationError
from pydantic import TypeAdapter
from pydantic_core import InitErrorDetails

from ...expr import (
    ExpressionError,
    ExprType,
    ExprValue,
    TypeCode,
    FunctionLibrary,
    SymbolTable,
    get_default_library,
)
from ...expr._path_mapping import PathFormat

from .._format_strings import FormatString
from .._types import OpenJDModel, ResolutionScope

if TYPE_CHECKING:
    from ..v2023_09._model import LetBinding

__all__ = ("instantiate_model",)

# Cache for TypeAdapter instances
_type_adapter_cache: Dict[int, TypeAdapter] = {}


def get_type_adapter(field_type: Any) -> TypeAdapter:
    """Get a TypeAdapter for the given field type, using a cache for efficiency.
    Assumes field_type refers to shared type definitions from the model so two field_types
    referring to the same underlying model type will have the same id and share an adapter.

    Args:
        field_type: The type to adapt.

    Returns:
        A TypeAdapter for the given type.
    """
    # Use id as cache key
    type_key = id(field_type)
    if type_key not in _type_adapter_cache:
        _type_adapter_cache[type_key] = TypeAdapter(field_type)
    return _type_adapter_cache[type_key]


def evaluate_let_bindings(
    bindings: list["LetBinding"],
    symtab: SymbolTable,
    library: FunctionLibrary,
    path_format: Optional[PathFormat] = None,
) -> SymbolTable:
    """Evaluate let bindings and return a new symbol table with bound values.

    Args:
        bindings: List of LetBinding objects to evaluate.
        symtab: Current symbol table for expression evaluation.
        library: Function library for expression evaluation.
        path_format: Controls path type behavior during evaluation.

    Returns:
        New SymbolTable with the original symbols plus let-bound values.

    Raises:
        ExpressionError: If evaluation fails, with binding context in the message.
    """
    expr_symtab = SymbolTable(symtab)

    for binding in bindings:
        try:
            value = binding.parsed.evaluate(
                values=expr_symtab,
                library=library,
                path_format=path_format,
            )
        except ExpressionError as e:
            prefix = f"{binding.name} = "
            raise ExpressionError(
                f"Error evaluating let binding '{binding.name}': "
                f"{e.message_with_expr_prefix(prefix)}"
            ) from None
        expr_symtab[binding.name] = value

    return expr_symtab


@contextmanager
def capture_validation_errors(
    *, output_errors: list[InitErrorDetails], loc: tuple[Union[str, int], ...], input: Any
):
    """Context manager to collect validation errors from pydantic into a list.

    Args:
        output_error_list (list[InitErrorDetails]): The list to collect errors into.
        loc (tuple): The location of the input value being validated.
        input (Any): The input value being validated.
    """
    try:
        yield
    except ValidationError as exc:
        # Convert the ErrorDetails to InitErrorDetails by extending the 'loc' and excluding the 'msg'
        for error_details in exc.errors():
            init_error_details: dict[str, Any] = {}
            for err_key, err_value in error_details.items():
                if err_key == "loc":
                    init_error_details["loc"] = (*loc, *err_value)  # type: ignore
                elif err_key != "msg":
                    init_error_details[err_key] = err_value
            output_errors.append(init_error_details)  # type: ignore
    except ValueError as exc:
        output_errors.append(
            InitErrorDetails(
                type="value_error",
                loc=loc,
                ctx={"error": exc},
                input=input,
            )
        )


def instantiate_model(  # noqa: C901
    model: OpenJDModel,
    symtab: SymbolTable,
    library: Optional[FunctionLibrary] = None,
) -> OpenJDModel:
    """This function is for instantiating a Template model into a Job model.

    It does a depth-first traversal through the model, mutating each stage according
    to the instructions given in the model's create-job metadata.

    Args:
        model (OpenJDModel): The model instance to transform.
        symtab (SymbolTable): The symbol table containing fully qualified Job parameter values
            used during the instantiation.
        library (Optional[FunctionLibrary]): Function library for expression evaluation.
            Defaults to get_default_library().

    Raises:
        ValidationError - If there are any validation errors from the target models.

    Returns:
        OpenJDModel: The transformed model.
    """
    if library is None:
        library = get_default_library()

    errors = list[InitErrorDetails]()
    instantiated_fields = dict[str, Any]()

    # Apply pre-transform if defined
    if model._job_creation_metadata.transform is not None:
        model = model._job_creation_metadata.transform(model)

    # Inject Step.Name into the symbol table for StepTemplate models (EXPR only)
    step_name = getattr(model, "name", None)
    if step_name is not None and hasattr(model, "parameterSpace") and "Job.Name" in symtab:
        symtab = SymbolTable(symtab)
        symtab["Step.Name"] = ExprValue(str(step_name), type=ExprType.STRING)

    # Evaluate let bindings if present and not in a host scope (SESSION or TASK).
    # Let bindings in host scopes are deferred to runtime because they can reference
    # symbols (like Task.Param.* or path-mapped Param.* values) not known at job creation time.
    let_bindings = getattr(model, "let", None)
    model_scope = model._template_variable_scope
    is_host_scope = model_scope in (ResolutionScope.SESSION, ResolutionScope.TASK)
    if let_bindings and not is_host_scope:
        with capture_validation_errors(output_errors=errors, loc=("let",), input=let_bindings):
            symtab = evaluate_let_bindings(let_bindings, symtab, library, PathFormat.POSIX)

    # Determine the target model to create as
    target_model = model.__class__
    if model._job_creation_metadata.create_as is not None:
        create_as_metadata = model._job_creation_metadata.create_as
        if create_as_metadata.model is not None:
            target_model = create_as_metadata.model
        elif create_as_metadata.callable is not None:
            target_model = create_as_metadata.callable(model)

    for field_name in model.__class__.model_fields.keys():
        if field_name in model._job_creation_metadata.exclude_fields:
            # The field is marked for being excluded
            continue
        target_field_name = model._job_creation_metadata.rename_fields.get(field_name, field_name)
        target_field_type: Any = target_model.model_fields[target_field_name].annotation
        for metadata in target_model.model_fields[target_field_name].metadata:
            target_field_type = Annotated[target_field_type, metadata]

        if not hasattr(model, field_name):
            # Field has no value. Set to None and move on.
            instantiated_fields[target_field_name] = None
            continue

        field_value = getattr(model, field_name)
        instantiated: Any = None
        with capture_validation_errors(output_errors=errors, loc=(field_name,), input=field_value):
            # Check if this is a range field with special resolution.
            # Currently all fields named "range" need this handling. If in the future
            # we evolve the spec to have a "range" field with different handling,
            # we will have to generalize the code.
            if field_name == "range" and "range" in model._job_creation_metadata.resolve_fields:
                # Get the parameter type from the model's 'type' field
                param_type = getattr(model, "type", None)
                param_type_str = param_type.name if param_type else "STRING"
                instantiated = _resolve_range_field(
                    field_value,
                    symtab,
                    param_type_str,
                    library,
                    PathFormat.POSIX,
                )
            # Instantiate and resolve format string expressions
            elif isinstance(field_value, list):
                needs_resolve = field_name in model._job_creation_metadata.resolve_fields
                if field_name in model._job_creation_metadata.reshape_field_to_dict:
                    key_field = model._job_creation_metadata.reshape_field_to_dict[field_name]
                    instantiated = _instantiate_list_field_as_dict(
                        field_value,
                        symtab,
                        needs_resolve,
                        key_field,
                        library,
                        PathFormat.POSIX,
                    )
                else:
                    instantiated = _instantiate_list_field_as_list(
                        field_value,
                        symtab,
                        needs_resolve,
                        library,
                        PathFormat.POSIX,
                    )
            elif isinstance(field_value, dict):
                needs_resolve = field_name in model._job_creation_metadata.resolve_fields
                instantiated = _instantiate_dict_field(
                    field_value,
                    symtab,
                    needs_resolve,
                    library,
                    PathFormat.POSIX,
                )
            else:
                needs_resolve = field_name in model._job_creation_metadata.resolve_fields
                instantiated = _instantiate_noncollection_value(
                    field_value,
                    symtab,
                    needs_resolve,
                    library,
                    PathFormat.POSIX,
                )

            # Validate as the target field type using cached TypeAdapter
            type_adapter = get_type_adapter(target_field_type)
            instantiated = type_adapter.validate_python(instantiated)
            instantiated_fields[target_field_name] = instantiated

    if not errors:
        if model._job_creation_metadata.adds_fields is not None:
            new_fields = model._job_creation_metadata.adds_fields(model, symtab)
            # Convert ExprValue results to Python values for pydantic validation
            for k, v in new_fields.items():
                if isinstance(v, ExprValue):
                    if v.type.type_code == TypeCode.LIST:
                        new_fields[k] = v.item()
                    else:
                        new_fields[k] = v.to_string()
            instantiated_fields.update(**new_fields)

        with capture_validation_errors(output_errors=errors, loc=(), input=field_value):
            result = target_model(**instantiated_fields)

    if errors:
        raise ValidationError.from_exception_data(
            title=model.__class__.__name__, line_errors=errors
        )

    return result


def _get_range_target_type(param_type_str: str) -> ExprType:
    """Get the target type for range field resolution based on parameter type."""
    if param_type_str == "INT":
        return ExprType(TypeCode.UNION, [ExprType.STRING, ExprType.LIST_INT])
    elif param_type_str == "FLOAT":
        return ExprType.LIST_FLOAT
    elif param_type_str == "STRING":
        return ExprType.LIST_STRING
    elif param_type_str == "PATH":
        return ExprType.LIST_PATH
    elif param_type_str == "CHUNK_INT":
        return ExprType(TypeCode.UNION, [ExprType.STRING, ExprType.RANGE_EXPR])
    else:
        raise ValueError(f"Unknown task parameter type: {param_type_str}")


def _get_range_element_target_type(param_type_str: str) -> ExprType:
    """Get the target type for range list element resolution."""
    if param_type_str == "INT":
        return ExprType(TypeCode.UNION, [ExprType.NULLTYPE, ExprType.INT, ExprType.LIST_INT])
    elif param_type_str == "FLOAT":
        return ExprType(TypeCode.UNION, [ExprType.NULLTYPE, ExprType.FLOAT, ExprType.LIST_FLOAT])
    elif param_type_str == "STRING":
        return ExprType(TypeCode.UNION, [ExprType.NULLTYPE, ExprType.STRING, ExprType.LIST_STRING])
    elif param_type_str == "PATH":
        return ExprType(TypeCode.UNION, [ExprType.NULLTYPE, ExprType.PATH, ExprType.LIST_PATH])
    else:
        raise ValueError(f"Unknown task parameter type: {param_type_str}")


def _resolve_range_field(
    value: Any,
    symtab: SymbolTable,
    param_type_str: str,
    library: FunctionLibrary,
    path_format: Optional[PathFormat] = None,
) -> Any:
    """Resolve a range field with special handling for null skipping and list flattening.

    Args:
        value: The range field value (FormatString, list, or literal)
        symtab: Symbol table for expression evaluation
        param_type_str: The task parameter type ("INT", "FLOAT", "STRING", "PATH")
        library: Function library for expression evaluation

    Returns:
        Either a string (range expression) or a list of values
    """
    if isinstance(value, FormatString):
        target_type = _get_range_target_type(param_type_str)
        result = value.resolve(
            symtab=symtab,
            library=library,
            target_type=target_type,
            path_format=path_format,
        )

        if result.type.type_code == TypeCode.LIST:
            return [
                v.item() if v.type.type_code in (TypeCode.INT, TypeCode.FLOAT) else v.to_string()
                for v in result.to_expr_value_list()
            ]
        else:
            return result.to_string()

    elif isinstance(value, list):
        # List of values - evaluate each with null skipping and list flattening
        target_type = _get_range_element_target_type(param_type_str)
        result_list: list[Any] = []

        for item in value:
            if isinstance(item, FormatString):
                item_result = item.resolve(
                    symtab=symtab,
                    library=library,
                    target_type=target_type,
                    path_format=path_format,
                )

                if item_result.is_null:
                    continue
                elif item_result.type.type_code == TypeCode.LIST:
                    result_list.extend(
                        (
                            v.item()
                            if v.type.type_code in (TypeCode.INT, TypeCode.FLOAT)
                            else v.to_string()
                        )
                        for v in item_result.to_expr_value_list()
                    )
                else:
                    if item_result.type.type_code in (TypeCode.INT, TypeCode.FLOAT):
                        result_list.append(item_result.item())
                    else:
                        result_list.append(item_result.to_string())
            else:
                # Non-format-string literal - keep as-is
                result_list.append(item)

        return result_list

    else:
        # Literal value - return as-is
        return value


def _instantiate_noncollection_value(
    value: Any,
    symtab: SymbolTable,
    needs_resolve: bool,
    library: FunctionLibrary,
    path_format: Optional[PathFormat] = None,
) -> Any:
    """Instantiate a single value that must not be a collection type (list, dict, etc).

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        needs_resolve (bool): Whether to resolve the value as a format string.
        library (FunctionLibrary): Function library for expression evaluation.
        path_format: Optional path format for path type behavior.
    """
    if isinstance(value, OpenJDModel):
        return instantiate_model(value, symtab, library)
    elif isinstance(value, FormatString) and needs_resolve:
        value = value.resolve(symtab=symtab, library=library, path_format=path_format).to_string()

    return value


def _instantiate_list_field_as_list(  # noqa: C901
    value: list[Any],
    symtab: SymbolTable,
    needs_resolve: bool,
    library: FunctionLibrary,
    path_format: Optional[PathFormat] = None,
) -> list[Any]:
    """As _instantiate_noncollection_value, but where the value is a list.

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        needs_resolve (bool): Whether to resolve the value as a format string.
        library (FunctionLibrary): Function library for expression evaluation.
    """
    errors: list[InitErrorDetails] = []
    result: list[Any] = []
    for idx, item in enumerate(value):
        with capture_validation_errors(output_errors=errors, loc=(idx,), input=value):
            # Raises: ValidationError, FormatStringError
            result.append(
                _instantiate_noncollection_value(
                    item,
                    symtab,
                    needs_resolve,
                    library,
                    path_format,
                )
            )

    if errors:
        raise ValidationError.from_exception_data(
            title="_instantiate_list_field_as_list", line_errors=errors
        )

    return result


def _instantiate_list_field_as_dict(  # noqa: C901
    value: list[Any],
    symtab: SymbolTable,
    needs_resolve: bool,
    key_field: str,
    library: FunctionLibrary,
    path_format: Optional[PathFormat] = None,
) -> dict[str, Any]:
    """As _instantiate_noncollection_value, but where the value is a list.

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        needs_resolve (bool): Whether to resolve the value as a format string.
        key_field (str): The name of the key in each object that defines the output dictionary key.
        library (FunctionLibrary): Function library for expression evaluation.
    """
    errors: list[InitErrorDetails] = []
    result: dict[str, Any] = {}
    for idx, item in enumerate(value):
        key = getattr(item, key_field)
        with capture_validation_errors(output_errors=errors, loc=(idx,), input=value):
            result[key] = _instantiate_noncollection_value(
                item,
                symtab,
                needs_resolve,
                library,
                path_format,
            )

    if errors:
        raise ValidationError.from_exception_data(
            title="_instantiate_list_field_as_dict", line_errors=errors
        )

    return result


def _instantiate_dict_field(
    value: dict[str, Any],
    symtab: SymbolTable,
    needs_resolve: bool,
    library: FunctionLibrary,
    path_format: Optional[PathFormat] = None,
) -> dict[str, Any]:
    """As _instantiate_noncollection_value, but where the value is a dict.

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        needs_resolve (bool): Whether to resolve the value as a format string.
        library (FunctionLibrary): Function library for expression evaluation.
    """
    errors: list[InitErrorDetails] = []
    result: dict[str, Any] = {}
    for key, item in value.items():
        with capture_validation_errors(output_errors=errors, loc=(key,), input=value):
            result[key] = _instantiate_noncollection_value(
                item,
                symtab,
                needs_resolve,
                library,
                path_format,
            )

    if errors:
        raise ValidationError.from_exception_data(
            title="_instantiate_dict_field", line_errors=errors
        )

    return result
