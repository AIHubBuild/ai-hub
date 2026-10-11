"""Document service error hierarchy.

Domain services and routers map these onto HTTP responses with the
standard envelope (`docs/07_API_Design.md` §10).
"""


class DocumentError(ValueError):
    """Base class for document-handling failures."""


class InvalidFileTypeError(DocumentError):
    """Uploaded file has an unsupported extension."""


class UnreadableDocumentError(DocumentError):
    """File could not be parsed or decoded."""


class EmptyDocumentError(DocumentError):
    """File parsed successfully but contains no readable text."""
