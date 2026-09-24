from pydantic import BaseModel


class UpdatedUserData(BaseModel):
    """User record returned by the Users service status update.

    ``PATCH /users/{id}`` answers the updated user in addition to the
    confirmation message, so the callback can build the result email from
    the data the platform persists (the data ownership rule is preserved:
    the callback never reads the users database). Every field is optional
    because the payload of the status update is the only source of this
    data and the callback degrades gracefully when a field is absent.
    """

    id: str | None = None
    username: str | None = None
    email: str | None = None
    dni: str | None = None
    fullName: str | None = None
    phoneNumber: str | None = None
    status: str | None = None
    ruv: str | None = None
    updatedAt: str | None = None
