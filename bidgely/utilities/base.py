from typing import Any, Optional

import aiohttp


# https://www.bidgely.com/customers/
class UtilityBase:
    "Base Class for a Bidgely customer"

    subclasses: list[type["UtilityBase"]] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Keep track of all subclass implementations."""
        super().__init_subclass__(**kwargs)
        cls.subclasses.append(cls)

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
        optional_account_id: Optional[str],
    ) -> Optional[str]:
        """Login to the utility website.

        Return the Opower access token or None

        :raises InvalidAuth: if login information is incorrect
        """
        raise NotImplementedError
