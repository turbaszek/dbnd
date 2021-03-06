import attr


@attr.s(slots=True)
class TargetMeta(object):
    value_preview = attr.ib()  # type: str
    data_dimensions = attr.ib()  # type: List[int]
    data_schema = attr.ib()  # type: str
    data_hash = attr.ib()  # type: str
