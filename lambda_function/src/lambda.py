"""
This module contains the handler function and the main function
which contains the logic that initializes the FileProcessor class
in its correct environment.
"""

from typing import Any

from process_artifacts import process_artifacts


def handler(event: dict[str, Any], context: Any) -> dict[str, int | str]:
    """
    Lambda handler that proxies to :func:`process_artifacts.handle_event`.

    Parameters
    ----------
    event : dict[str, Any]
        Event data passed from the Lambda trigger.
    context : Any
        AWS Lambda context object.

    Returns
    -------
    dict[str, int | str]
        HTTP-style response with a ``statusCode`` (200 on success, 500 on
        error) and a serialized ``body`` string.
    """

    return process_artifacts.handle_event(event, context)
