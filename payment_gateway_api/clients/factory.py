import httpx

from payment_gateway_api.clients.bank_client import AcquiringBankClient
from payment_gateway_api.clients.mock_bank_client import UnavailableBankClient
from payment_gateway_api.config import BankConfig


def build_bank_client(config: BankConfig, http_client: httpx.AsyncClient):
    if config.mock_unavailable:
        return UnavailableBankClient(config.bank_id)

    return AcquiringBankClient(
        bank_id=config.bank_id,
        http_client=http_client,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
    )


def build_bank_clients(configs: list[BankConfig], http_client: httpx.AsyncClient):
    return [build_bank_client(config, http_client) for config in configs]
