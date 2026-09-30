from dataclasses import dataclass, field


@dataclass
class AppError(Exception):
    code: str
    message: str
    status_code: int = 400
    details: list[dict] = field(default_factory=list)
