"""
Request and Response Schemas for Posts endpoints.
"""
from pydantic import BaseModel, Field


class CreatePostRequest(BaseModel):
    """Request body for POST /posts."""

    route_id: str = Field(..., alias="routeId")
    user_id: str = Field(..., alias="userId")
    expire_at: str = Field(..., alias="expireAt")

    class Config:
        populate_by_name = True  # Allow both camelCase and snake_case


class CreatePostResponse(BaseModel):
    """Response body for POST /posts (201)."""

    id: str
    user_id: str = Field(..., alias="userId")
    created_at: str = Field(..., alias="createdAt")

    class Config:
        populate_by_name = True


class PostResponse(BaseModel):
    """A full Publicación object, as returned by GET /posts and GET /posts/{id}."""

    id: str
    route_id: str = Field(..., alias="routeId")
    user_id: str = Field(..., alias="userId")
    expire_at: str = Field(..., alias="expireAt")
    created_at: str = Field(..., alias="createdAt")

    class Config:
        populate_by_name = True


class CountPostsResponse(BaseModel):
    """Response body for GET /posts/count."""

    count: int


class MessageResponse(BaseModel):
    """Response body for endpoints that only confirm the operation."""

    msg: str
