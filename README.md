# `static-import-analysis`

Static import analysis for Python projects: extract functions, classes, and imports by walking a project's AST.

## Features

- Find all modules in a Python source tree.
- Enumerate functions and classes (with parameter names) in every module.
- Discover all imports and `from ... import ...` statements, including their relative/absolute resolutions.
- Robust: does not import or execute code; works with broken modules (reported, but skipped).
- Correctly understands packages and `__init__.py`.

## Install

```sh
pip install static-import-analysis
```

## Usage

Python API example:

```python
from static_import_analysis import static_import_analysis

(
    module_name_to_absolute_python_file_path_dict,
    module_name_to_module_dict,
    module_name_to_function_name_to_parameter_name_list_dict,
    module_name_to_class_name_to_method_name_to_parameter_name_list_dict,
    module_name_to_import_tuple_set_dict,
    module_name_to_import_from_tuple_set_dict
) = static_import_analysis('/path/to/your/python/project')
```

- `module_name_to_absolute_python_file_path_dict` – maps each module's importable name to its `.py` file
- `module_name_to_module_dict` - module name -> ast.Module instance
- `module_name_to_function_name_to_parameter_name_list_dict` – module name -> function name -> parameter names
- `module_name_to_class_name_to_method_name_to_parameter_name_list_dict` – module name -> class name -> method name -> parameter names
- `module_name_to_import_tuple_set_dict` – module name -> set of (imported_module, alias) for all `import ...` statements
- `module_name_to_import_from_tuple_set_dict` – module name -> set of (imported_module, imported_name, alias) for all `from ... import ...` statements

## Example

Suppose directory structure:

```
project_root/
  - __init__.py
  - foo.py
  - bar/
    - __init__.py
    - baz.py
```

Result:

- `static_import_analysis('project_root')` will parse all these as modules `__init__`, `foo`, `bar`, `bar.baz` with correct import/parameter relationships.

## Contributing

Contributions are welcome! Please submit pull requests or open issues on the GitHub repository.

## License

This project is licensed under the [MIT License](LICENSE).