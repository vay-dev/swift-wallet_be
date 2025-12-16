"""
Utility functions for formatting error responses
"""


def format_validation_errors(serializer_errors):
    """
    Convert Django serializer errors into a user-friendly message

    Args:
        serializer_errors: Dict of field errors from serializer

    Returns:
        String with clear error message
    """
    error_messages = []

    for field, errors in serializer_errors.items():
        if field == 'non_field_errors':
            # General errors not tied to specific field
            for error in errors:
                error_messages.append(str(error))
        else:
            # Field-specific errors
            field_name = field.replace('_', ' ').title()
            for error in errors:
                error_messages.append(f"{field_name}: {error}")

    # Return first error or generic message
    if error_messages:
        return error_messages[0]
    return 'Please check your input and try again'
