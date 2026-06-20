import enum


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class TaskType(str, enum.Enum):
    image = "image"
    video = "video"


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class AccountStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    cooldown = "cooldown"
    invalid = "invalid"


class AccountType(str, enum.Enum):
    normal = "normal"
    pro = "pro"
    ula = "ula"


class ApiKeyStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
