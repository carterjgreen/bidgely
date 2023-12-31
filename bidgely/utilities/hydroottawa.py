import base64
import json
import logging
import re
from collections import OrderedDict

import aiohttp
import boto3
from py3rijndael import RijndaelCbc, ZeroPadding

from bidgely.exceptions import InvalidAuth

from .aws_srp import AWSSRP
from .base import UtilityBase

logger = logging.getLogger(__name__)


def create_bidgely_payload(
    account_id: str, access_token: str, refresh_token: str
) -> OrderedDict[str, str]:
    return OrderedDict(
        {
            "accountId": account_id,
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "language": "en",
            "requestType": "",
            "identityType": "cognito",
            "impersonator": "",
        },
    )


def create_bidgely_token(payload: OrderedDict[str, str]) -> str:
    cipher = RijndaelCbc(
        key="tG@$=gQGyu_Lcqvt/4Vb6y4sWV6j-VmC",
        iv="%rAn_BLzP+JwAAGGXe5PQ(ZrBgtpfUzq",
        padding=ZeroPadding(32),
        block_size=32,
    )
    text = json.dumps(payload, separators=(",", ":")).encode()
    result = cipher.encrypt(text.ljust(32, b"\x1b"))
    return base64.b64encode(result).decode()


class HydroOttawa(UtilityBase):
    "Hydro Ottawa."

    @staticmethod
    def name() -> str:
        """Distinct recognizable name of the utility."""
        return "Hydro Ottawa"

    @staticmethod
    def timezone() -> str:
        """Return the timezone."""
        return "America/Toronto"

    @staticmethod
    async def async_login(
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        account_id: str,
    ) -> tuple[str, str]:
        "Returns user-id and token for Bidgely."
        client = await session.loop.run_in_executor(
            None,
            boto3.client,
            "cognito-idp",
            "ca-central-1",
        )
        aws = AWSSRP(
            username=username,
            password=password,
            pool_id="ca-central-1_VYnwOhMBK",
            client_id="7scfcis6ecucktmp4aqi1jk6cb",
            client=client,
            loop=session.loop,
        )
        tokens = await aws.authenticate_user()
        auth_result = tokens["AuthenticationResult"]

        payload = create_bidgely_payload(
            account_id,
            auth_result["AccessToken"],
            auth_result["RefreshToken"],
        )
        bidgely_token = create_bidgely_token(payload)

        body = {"sessionToken": bidgely_token}

        async with session.post(
            "https://usage.hydroottawa.com/api/v1/sso/dashboard",
            data=body,
            allow_redirects=False,
        ) as resp:
            if resp.status == 302:
                bidgely_url = resp.headers["Location"]
                r = re.search("uuid=(.*)&token=(.*)&sso-token", bidgely_url)
                if r is not None:
                    user_id = r.group(1)
                    bearer_token = r.group(2)
                    logger.debug(f"Successful token retrieved for user-id: {user_id}")
                else:
                    logger.debug(f"Bidgely login failed for {username}")
                    raise InvalidAuth  # InvalidAuth
            else:
                logger.debug(f"Bidgely login failed for {username}")
                raise InvalidAuth  # InvalidAuth()

        return (user_id, bearer_token)
