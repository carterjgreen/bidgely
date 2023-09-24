import aiohttp
from pydantic import BaseModel


# https://www.bidgely.com/customers/
class UtilityBase(BaseModel):
    "Base Class for a Bidgely customer."

    @staticmethod
    def name() -> str:
        """Distinct recognizable name of the utility."""
        raise NotImplementedError

    @staticmethod
    def timezone() -> str:
        """Return the timezone."""
        raise NotImplementedError

    @staticmethod
    async def async_login(
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        account_id: str,
    ) -> tuple[str, str]:
        """Login to the utility website.

        Return the Opower access token or None

        :raises InvalidAuth: if login information is incorrect
        """
        raise NotImplementedError
