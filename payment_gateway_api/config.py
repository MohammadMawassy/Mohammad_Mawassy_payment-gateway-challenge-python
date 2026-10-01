"""Environment-driven application configuration."""
from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BankConfig(BaseModel):
    bank_id: str
    base_url: str = "http://localhost:8080"
    timeout_seconds: float = 4.0
    mock_unavailable: bool = False


class RoutingConfig(BaseModel):
    """Simple deterministic bank distribution.

    A stable hash of the card number selects one configured bank. This keeps
    the same card consistently mapped to the same bank without using currency
    as a routing criterion.
    """

    # Banks are configured by ID so another adapter can be added without
    # changing the payment service or API flow.
    bank_ids: list[str] = Field(default_factory=lambda: ["primary", "mock", "simulated"])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PGW_", extra="ignore")

    # The factory, protocol, and router form a small adapter/strategy design:
    # adding a bank is configuration when it follows the shared bank contract.
    banks: list[BankConfig] = Field(
        default_factory=lambda: [
            BankConfig(bank_id="primary", base_url="http://localhost:8080"),
            BankConfig(bank_id="mock", mock_unavailable=True),
            BankConfig(bank_id="simulated", mock_unavailable=True),
        ]
    )
    routing: RoutingConfig = Field(default_factory=RoutingConfig)


@lru_cache
def get_settings() -> Settings:
    return Settings()
