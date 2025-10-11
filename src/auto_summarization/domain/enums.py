import enum


class EnumMeta(enum.EnumMeta):
    def __iter__(cls):
        return (member.value for member in super().__iter__())

    def __getattribute__(cls, name):
        attr = super().__getattribute__(name)
        if isinstance(attr, enum.Enum):
            return attr.value
        return attr


class Enum(enum.Enum, metaclass=EnumMeta):
    pass


class AnalysisModelType(Enum):
    UNIVERSAL = "UNIVERSAL"
    PRETRAINED = "PRETRAINED"


class StatusType(Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
