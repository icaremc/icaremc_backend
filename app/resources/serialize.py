from app.api.v1.schemas import RowOut
from app.persistence.sqlalchemy.serialize import row_dict


def to_row(obj: object | None) -> RowOut | None:
    if obj is None:
        return None
    data = row_dict(obj) if hasattr(obj, "__table__") else obj
    return RowOut.model_validate(data)


def require_row(obj: object) -> RowOut:
    row = to_row(obj)
    if row is None:
        raise RuntimeError("expected row")
    return row


def to_rows(rows: list[object]) -> list[RowOut]:
    return [require_row(r) for r in rows]
