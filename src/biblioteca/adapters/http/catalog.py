from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator

from biblioteca.adapters.http.dependencies import get_uow
from biblioteca.adapters.http.schemas import BookResponse, CategoryResponse
from biblioteca.adapters.http.security import roles
from biblioteca.application.catalog import (
    AssignCategories,
    CreateBook,
    CreateCategory,
    ListCategories,
    UpdateBook,
)
from biblioteca.application.search import SearchBooksByCategory
from biblioteca.domain.entities import RoleName
from biblioteca.domain.ports import UnitOfWork

router = APIRouter(tags=["catalog"])


class CategoryRequest(BaseModel):
    name: str = Field(min_length=1)


class BookRequest(BaseModel):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    isbn: str = Field(min_length=1)
    total_copies: int = Field(ge=1)
    category_ids: list[UUID] = []


class UpdateBookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1)
    author: str | None = Field(default=None, min_length=1)
    isbn: str | None = Field(default=None, min_length=1)
    total_copies: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _not_empty(self) -> "UpdateBookRequest":
        values = (self.title, self.author, self.isbn, self.total_copies)
        if all(value is None for value in values):
            raise ValueError("Indica al menos un dato que modificar")
        return self


class AssignCategoriesRequest(BaseModel):
    category_ids: list[UUID] = Field(min_length=1)


@router.post("/categories", status_code=201, response_model=CategoryResponse)
@roles(RoleName.LIBRARIAN)
def create_category(body: CategoryRequest, uow: UnitOfWork = Depends(get_uow)):
    return CategoryResponse.of(CreateCategory(uow).execute(body.name))


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(uow: UnitOfWork = Depends(get_uow)):
    return [CategoryResponse.of(c) for c in ListCategories(uow).execute()]


@router.get("/books", response_model=list[BookResponse])
def search_books(category_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    return [BookResponse.of(b) for b in SearchBooksByCategory(uow).execute(category_id)]


@router.post("/books", status_code=201, response_model=BookResponse)
@roles(RoleName.LIBRARIAN)
def create_book(body: BookRequest, uow: UnitOfWork = Depends(get_uow)):
    book = CreateBook(uow).execute(
        body.title, body.author, body.isbn, body.total_copies, body.category_ids
    )
    return BookResponse.of(book)


@router.patch("/books/{book_id}", response_model=BookResponse)
@roles(RoleName.ADMIN, RoleName.LIBRARIAN)
def update_book(book_id: UUID, body: UpdateBookRequest, uow: UnitOfWork = Depends(get_uow)):
    book = UpdateBook(uow).execute(book_id, body.title, body.author, body.isbn, body.total_copies)
    return BookResponse.of(book)


@router.post("/books/{book_id}/categories", response_model=BookResponse)
@roles(RoleName.LIBRARIAN)
def assign_categories(
    book_id: UUID, body: AssignCategoriesRequest, uow: UnitOfWork = Depends(get_uow)
):
    return BookResponse.of(AssignCategories(uow).execute(book_id, body.category_ids))
