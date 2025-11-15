# Copyright (c) 2025 Jifeng Wu
# Licensed under the MIT License. See LICENSE file in the project root for full license information.
import ast
import codecs
import logging
import os
import sys
from collections import OrderedDict
from typing import Iterator, Optional, Tuple, Dict, List, Set


def yield_module_names_and_absolute_python_file_paths(
        project_path,  # type: str
):
    # type: (...) -> Iterator[Tuple[str, str]]
    """
    Yields (module_name, absolute_python_file_path) for each .py source file in the project,
    using Python import dotted-naming conventions for packages (__init__.py).

    Skips hidden files/folders.

    Args:
        project_path: Root directory to scan.

    Yields:
        (module_name, absolute_python_file_path) tuples.
    """
    for root, directories, files in os.walk(project_path):
        # Skip hidden directories
        directories[:] = [d for d in directories if not d.startswith('.')]

        # Skip hidden files
        files[:] = [f for f in files if not f.startswith('.')]

        relpath = os.path.relpath(root, project_path)

        python_file_names = []
        python_file_paths = []

        for file in files:
            file_name, file_ext = os.path.splitext(file)
            if file_ext == '.py':
                python_file_names.append(file_name)
                python_file_paths.append(os.path.join(root, file))

        # Directly handle all python files in `os.path.curdir` (e.g., '.')
        if relpath == os.path.curdir:
            for python_file_name, python_file_path in zip(python_file_names, python_file_paths):
                yield python_file_name, python_file_path
        # In other directories,
        # if there is a python file named `__init__` within the directory
        # handle the directory itself (pointing to the python file named `__init__`)
        # and python files within it (excluding the python file named `__init__`)
        # if there is not
        # we directly handle all python files
        else:
            relpath_components = relpath.split(os.path.sep)

            if '__init__' in python_file_names:
                index_of_init = python_file_names.index('__init__')
                module_name = '.'.join(relpath_components)
                yield module_name, python_file_paths[index_of_init]

                for python_file_name, python_file_path in zip(python_file_names, python_file_paths):
                    if python_file_name != '__init__':
                        module_name_components = []
                        module_name_components.extend(relpath_components)
                        module_name_components.append(python_file_name)
                        module_name = '.'.join(module_name_components)
                        yield module_name, python_file_path
            else:
                for python_file_name, python_file_path in zip(python_file_names, python_file_paths):
                    module_name_components = []
                    module_name_components.extend(relpath_components)
                    module_name_components.append(python_file_name)
                    module_name = '.'.join(module_name_components)
                    yield module_name, python_file_path


def get_import_tuple(
        ast_import,  # type: ast.Import
):
    # type: (...) -> Iterator[Tuple[str, str]]
    for ast_alias in ast_import.names:
        module_name = ast_alias.name
        module_name_alias = ast_alias.asname
        if module_name_alias is None:
            module_name_alias = module_name
        yield module_name, module_name_alias


def get_raw_import_from_tuples(
        ast_import_from,  # type: ast.ImportFrom
):
    # type: (...) -> Iterator[Tuple[Optional[str], int, str, str]]
    module_name = ast_import_from.module
    module_level = ast_import_from.level

    if module_name is None and not module_level:
        logging.error('Failed to get raw import from tuples from %s', ast.dump(ast_import_from))
        return

    for ast_alias in ast_import_from.names:
        imported_name = ast_alias.name
        imported_name_alias = ast_alias.asname
        if imported_name_alias is None:
            imported_name_alias = imported_name
        yield module_name, module_level, imported_name, imported_name_alias


def get_import_tuples_and_raw_import_from_tuples(
        module,  # type: ast.Module
):
    # type: (...) -> Tuple[Set[Tuple[str, str]], Set[Tuple[Optional[str], int, str, str]]]
    imports = set()
    raw_import_froms = set()

    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for (module_name, module_name_alias) in get_import_tuple(node):
                imports.add((module_name, module_name_alias))
        elif isinstance(node, ast.ImportFrom):
            for (raw_module_name, module_level, imported_name, imported_name_alias) in get_raw_import_from_tuples(node):
                raw_import_froms.add((raw_module_name, module_level, imported_name, imported_name_alias))

    return imports, raw_import_froms


def get_import_tuples_and_import_from_tuples(
        module_name,  # type: str
        module,  # type: ast.Module
        is_package=False,  # type: bool
):
    # type: (...) -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str, str]]]
    """
    Returns a tuple of (import_tuples, import_from_tuples).
    """
    module_name_components = module_name.split('.')

    imports, raw_import_froms = get_import_tuples_and_raw_import_from_tuples(module)

    import_froms = set()
    for raw_module_name, module_level, imported_name, imported_name_alias in raw_import_froms:
        if module_level:
            if is_package:
                module_name = '.'.join(
                    # drop `module_level - 1` components from the back of `module_name_components`
                    # this is because `module_level` is relative to `__init__.py` within the package
                    # not the package itself
                    module_name_components[:(len(module_name_components) - (module_level - 1))]
                )
            else:
                module_name = '.'.join(
                    # drop `module_level` components from the back of `module_name_components`
                    module_name_components[:(len(module_name_components) - module_level)]
                )

            if raw_module_name is not None:
                module_name += '.' + raw_module_name
        else:
            module_name = raw_module_name

        import_froms.add((module_name, imported_name, imported_name_alias))

    return imports, import_froms


if sys.version_info < (3, 5):
    def is_function_def(function_def):
        return isinstance(function_def, ast.FunctionDef)
else:
    def is_function_def(function_def):
        return isinstance(function_def, (ast.FunctionDef, ast.AsyncFunctionDef))

if sys.version_info < (3,):
    # arguments = (expr* args, identifier? vararg, identifier? kwarg, expr* defaults)
    def yield_parameter_names(function_def):
        arguments = function_def.args

        for arg in arguments.args:
            if isinstance(arg, ast.Name):
                yield arg.id

        if arguments.vararg is not None:
            yield arguments.vararg

        if arguments.kwarg is not None:
            yield arguments.kwarg

elif sys.version_info < (3, 4):
    # arguments = (arg* args, identifier? vararg, expr? varargannotation, arg* kwonlyargs, identifier? kwarg, expr? kwargannotation, expr* defaults, expr* kw_defaults)
    def yield_parameter_names(function_def):
        arguments = function_def.args

        for arg in arguments.args:
            yield arg.arg

        if arguments.vararg is not None:
            yield arguments.vararg

        for kwonlyarg in arguments.kwonlyargs:
            yield kwonlyarg.arg

        if arguments.kwarg is not None:
            yield arguments.kwarg

elif sys.version_info < (3, 8):
    # arguments = (arg* args, arg? vararg, arg* kwonlyargs, expr* kw_defaults, arg? kwarg, expr* defaults)
    def yield_parameter_names(function_def):
        arguments = function_def.args

        for arg in arguments.args:
            yield arg.arg

        if arguments.vararg is not None:
            yield arguments.vararg.arg

        for kwonlyarg in arguments.kwonlyargs:
            yield kwonlyarg.arg

        if arguments.kwarg is not None:
            yield arguments.kwarg.arg

else:
    # arguments = (arg* posonlyargs, arg* args, arg? vararg, arg* kwonlyargs, expr* kw_defaults, arg? kwarg, expr* defaults)
    def yield_parameter_names(function_def):
        arguments = function_def.args

        for posonlyarg in arguments.posonlyargs:
            yield posonlyarg.arg

        for arg in arguments.args:
            yield arg.arg

        if arguments.vararg is not None:
            yield arguments.vararg.arg

        for kwonlyarg in arguments.kwonlyargs:
            yield kwonlyarg.arg

        if arguments.kwarg is not None:
            yield arguments.kwarg.arg


def analyze_top_level_functions_and_classes(
        module,  # type: ast.Module
):
    # type: (...) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, List[str]]]]
    function_name_to_parameter_name_list_dict = {}
    class_name_to_method_name_to_parameter_name_list_dict = {}

    for node in module.body:
        if is_function_def(node):
            function_name = node.name
            parameter_name_list = list(yield_parameter_names(node))
            function_name_to_parameter_name_list_dict[function_name] = parameter_name_list
        elif isinstance(node, ast.ClassDef):
            class_name = node.name
            method_name_to_parameter_name_list_dict = {}

            for child_node in node.body:
                if is_function_def(child_node):
                    method_name = child_node.name
                    parameter_name_list = list(yield_parameter_names(child_node))
                    method_name_to_parameter_name_list_dict[method_name] = parameter_name_list

            class_name_to_method_name_to_parameter_name_list_dict[class_name] = method_name_to_parameter_name_list_dict

    return function_name_to_parameter_name_list_dict, class_name_to_method_name_to_parameter_name_list_dict


def static_import_analysis(
        python_project_root_directory_path,  # type: str
        module_prefix='',  # type: str
):
    # type: (...) -> Tuple[Dict[str, str], Dict[str, ast.Module], Dict[str, Dict[str, List[str]]], Dict[str, Dict[str, Dict[str, List[str]]]], Dict[str, Set[Tuple[str, str]]], Dict[str, Set[Tuple[str, str, str]]]]
    """
    Analyze a Python project (recursively) for modules, functions, classes and imports.

    Args:
        python_project_root_directory_path: Root directory for the Python project.
        module_prefix: Optional, restrict analysis to modules starting with this prefix.

    Returns:
        Tuple of:
          - module_name_to_absolute_python_file_path_dict
          - module_name_to_module_dict
          - module_name_to_function_name_to_parameter_name_list_dict
          - module_name_to_class_name_to_method_name_to_parameter_name_list_dict
          - module_name_to_import_tuple_set_dict
          - module_name_to_import_from_tuple_set_dict

        All dicts use the same module_name keys and can be correlated.
    """
    module_name_to_absolute_python_file_path_dict = OrderedDict()
    for module_name, file_path in yield_module_names_and_absolute_python_file_paths(python_project_root_directory_path):
        if module_name.startswith(module_prefix):
            module_name_to_absolute_python_file_path_dict[module_name] = file_path

    module_name_to_module_dict = OrderedDict()
    invalid_module_name_set = set()
    for module_name, file_path in module_name_to_absolute_python_file_path_dict.items():
        try:
            with codecs.open(file_path, 'r', encoding='utf-8') as f:
                contents = f.read()
            module = ast.parse(contents, file_path)
        except Exception:
            logging.exception('Failed to parse module `%s`', module_name)
            invalid_module_name_set.add(module_name)
            continue

        module_name_to_module_dict[module_name] = module

    for invalid_module_name in invalid_module_name_set:
        del module_name_to_absolute_python_file_path_dict[invalid_module_name]

    module_name_to_function_name_to_parameter_name_list_dict = OrderedDict()
    module_name_to_class_name_to_method_name_to_parameter_name_list_dict = OrderedDict()
    module_name_to_import_tuple_set_dict = OrderedDict()
    module_name_to_import_from_tuple_set_dict = OrderedDict()

    for module_name in module_name_to_absolute_python_file_path_dict:
        absolute_python_file_path = module_name_to_absolute_python_file_path_dict[module_name]
        module = module_name_to_module_dict[module_name]

        func_dict, class_dict = analyze_top_level_functions_and_classes(module)
        module_name_to_function_name_to_parameter_name_list_dict[module_name] = func_dict
        module_name_to_class_name_to_method_name_to_parameter_name_list_dict[module_name] = class_dict

        is_package = absolute_python_file_path.endswith('__init__.py')
        import_tuple_set, import_from_tuple_set = get_import_tuples_and_import_from_tuples(
            module_name,
            module,
            is_package
        )
        module_name_to_import_tuple_set_dict[module_name] = import_tuple_set
        module_name_to_import_from_tuple_set_dict[module_name] = import_from_tuple_set

    return (
        module_name_to_absolute_python_file_path_dict,
        module_name_to_module_dict,
        module_name_to_function_name_to_parameter_name_list_dict,
        module_name_to_class_name_to_method_name_to_parameter_name_list_dict,
        module_name_to_import_tuple_set_dict,
        module_name_to_import_from_tuple_set_dict
    )
