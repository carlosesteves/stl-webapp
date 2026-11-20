from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(default="")
    published: Mapped[bool] = mapped_column(default=False)
