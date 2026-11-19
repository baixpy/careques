"""Custom exceptions. The website catches CareQueueError and shows the message to the user."""


class CareQueueError(Exception):
    """Base class for every error a user can cause."""


class ValidationError(CareQueueError):
    """Form input is missing or in the wrong format."""


class InvalidPatientError(CareQueueError):
    """The patient ID does not exist."""


class InvalidDoctorError(CareQueueError):
    """The doctor ID does not exist."""


class SlotFullError(CareQueueError):
    """The chosen slot is taken, or the doctor has no slots left that day."""


class DoubleBookingError(CareQueueError):
    """The patient already has a clashing appointment."""


class AppointmentNotFoundError(CareQueueError):
    """The appointment ID does not exist or is already cancelled."""


class StorageError(CareQueueError):
    """A data file is unreadable or corrupted."""
