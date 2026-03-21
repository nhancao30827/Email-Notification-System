import enum


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    sending = "sending"
    sent = "sent"
    cancelled = "cancelled"


class RecipientStatus(str, enum.Enum):
    active = "active"
    unsubscribed = "unsubscribed"
    bounced = "bounced"


class DeliveryStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    opened = "opened"
    clicked = "clicked"
    bounced = "bounced"
    failed = "failed"
