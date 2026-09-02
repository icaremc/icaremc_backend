def row_dict(obj) -> dict:
    # ponytail: skip expired server_default/onupdate cols — getattr would MissingGreenlet under async
    data = obj.__dict__
    return {c.name: data[c.key] for c in obj.__table__.columns if c.key in data}
