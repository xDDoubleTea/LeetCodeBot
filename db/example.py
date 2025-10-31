from db.base import Base


class User(Base):
    __tablename__ = "users"
    id: int
    name: str

    def __repr__(self) -> str:
        return f"User(id={self.id}, name={self.name})"
