def clean_null_values(obj, protected_fields=None):
    """
    Recursively remove null values from dictionaries and lists.

    Args:
        obj: The object to clean (dict, list, or other)
        protected_fields: Set of field names to keep even if null (e.g., {'assetMainType'})

    Returns:
        Cleaned object with null values removed (except protected fields)
    """
    if protected_fields is None:
        protected_fields = {'assetMainType'}

    if isinstance(obj, dict):
        return {
            key: clean_null_values(value, protected_fields)
            for key, value in obj.items()
            if value is not None or key in protected_fields
        }
    elif isinstance(obj, list):
        return [clean_null_values(item, protected_fields) for item in obj if item is not None]
    else:
        return obj