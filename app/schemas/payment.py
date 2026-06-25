import re

from pydantic import BaseModel, field_validator


class MockCardIn(BaseModel):
    card_number: str
    cardholder_name: str = "CARDHOLDER"
    expiry_month: int = 12
    expiry_year: int = 2030
    cvv: str = "000"

    @field_validator("card_number")
    @classmethod
    def validate_card(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 13 or len(digits) > 19:
            raise ValueError("Номер карты должен содержать от 13 до 19 цифр")
        return digits


class PurchaseWithPromo(MockCardIn):
    promo_code: str | None = None
