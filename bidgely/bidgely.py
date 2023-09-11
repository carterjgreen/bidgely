import asyncio
import dataclasses
from itertools import chain
import json
import logging
from datetime import date, datetime, timedelta
from enum import Enum

import aiohttp
from aiohttp.client_exceptions import ClientResponseError
from aiohttp.web_exceptions import HTTPServerError

from .exceptions import CannotConnect, InvalidAuth
from .utilities.base import UtilityBase

logger = logging.getLogger(__name__)
DEBUG_LOG_RESPONSE = False


class MeasurementType(Enum):
    """Meter type. Electric or gas."""

    ELECTRIC = "ELECTRIC"
    GAS = "GAS"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value


class UnitOfMeasure(Enum):
    """
    Unit of measure for the associated meter type.
    kWh for electricity or Therm/CCF for gas.
    """

    KWH = "kWh"
    WH = "Wh"
    THERM = "THERM"
    CCF = "CCF"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value


class AggregateType(Enum):
    """How to aggregate historical data."""

    MONTH = "month"
    DAY = "day"
    HOUR = "hour"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value


class MeasurementCategory(Enum):
    """Bidgely's classification of energy usage"""

    ALWAYS_ON = "alwaysOn"
    COOKING = "cooking"
    ENTERTAINMENT = "entertainment"
    LAUNDRY = "laundry"
    LIGHTING = "lighting"
    OTHER = "other"
    REFRIGERATION = "refrigeration"


@dataclasses.dataclass(slots=True)
class Forecast:
    """Forecast data for an account."""

    start_date: date
    end_date: date
    unit_of_measure: UnitOfMeasure
    usage_to_date: float
    cost_to_date: float
    forecasted_usage: float
    forecasted_cost: float
    typical_usage: float
    typical_cost: float

    def __str__(self) -> str:
        s = f"""Forecast:
    Bill Start Date: {self.start_date}
    Bill End Date: {self.end_date}
    Usage to Date: {self.usage_to_date:.2f} {self.unit_of_measure}
    Forecasted Usage: {self.forecasted_usage:.2f} {self.unit_of_measure}
    Typical Usage: {self.typical_usage:.2f} {self.unit_of_measure}
    Cost to Date: ${self.cost_to_date:.2f}
    Forecasted Cost: ${self.forecasted_cost:.2f}
    Typical Cost: ${self.typical_cost:.2f}
            """
        return s


@dataclasses.dataclass(slots=True)
class Itemization:
    """Itemization of energy usage"""

    id: int
    category: MeasurementCategory
    usage: int
    cost: int
    percentage: int
    cost_percentage: int


@dataclasses.dataclass(slots=True)
class CostRead:
    """A read from the meter that has both consumption and cost data."""

    start_time: datetime
    end_time: datetime
    consumption: float
    cost: float
    temperature: int | None
    itemization: list[Itemization] | None

    def __add__(self, other):
        return CostRead(
            start_time=min(self.start_time, other.start_time),
            end_time=max(self.end_time, other.end_time),
            consumption=self.consumption + other.consumption,
            cost=self.cost + other.cost,
            temperature=None,
            itemization=None,
        )

    def __lt__(self, other):
        return self.start_time < other.start_time


def get_supported_utilities() -> list[type["UtilityBase"]]:
    """Return a list of all supported utilities."""
    return [cls for cls in UtilityBase.subclasses]


def _aggregate_to_mode(agg: AggregateType) -> str:
    """Translate aggregate into mode for Bidgely API"""
    match agg:
        case AggregateType.MONTH:
            mode = "year"
        case AggregateType.DAY:
            mode = "month"
        case AggregateType.HOUR:
            mode = "day"
    return mode


def _select_utility(name: str) -> type[UtilityBase]:
    """Return the utility with the given name."""
    for utility in UtilityBase.subclasses:
        if name.lower() in [utility.name().lower(), utility.__name__.lower()]:
            return utility
    raise ValueError(f"Utility {name} not found")


class Bidgely:
    """Class that can get historical and forecasted usage/cost from Bidgely's NA API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        utility: str,
        username: str,
        password: str,
        account_id: str | None,
    ) -> None:
        self.session: aiohttp.ClientSession = session
        self.utility: type[UtilityBase] = _select_utility(utility)
        self.username: str = username
        self.password: str = password
        self.account_id: str | None = account_id
        self.user_id: str | None = None
        self.access_token: str | None = None
        return None

    async def async_login(self) -> None:
        try:
            self.user_id, self.access_token = await self.utility.async_login(
                self.session, self.username, self.password, self.account_id
            )
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise InvalidAuth(err)
            else:
                raise CannotConnect(err)
        return None

    async def async_get_forecast(
        self, measurement: str = "ELECTRIC", home: int = 1
    ) -> Forecast:
        """Get current and forecasted usage and cost for the current monthly bill.

        If you are only an electric customer, bidgely will return electric results
        if you ask for gas forecasts.
        """
        url = (
            "https://naapi-read.bidgely.com"
            "/2.1/users/"
            f"{self.user_id}"
            "/homes/"
            f"{home}/"
            "billprojections"
        )
        if measurement == "ELECTRIC":
            unit = UnitOfMeasure("kWh")
        else:
            unit = UnitOfMeasure("CCF")
        ps = {"measurement-type": measurement, "convert-to-kwh": "true"}
        h = {"authorization": f"Bearer {self.access_token}"}
        async with self.session.get(url, params=ps, headers=h) as resp:
            result = await resp.json()
            if DEBUG_LOG_RESPONSE:
                logger.debug(f"Fetched: {json.dumps(result, indent=2)}")
            if resp.status == 200:
                forecast = Forecast(
                    start_date=date.fromisoformat(result["billStartDateFormatted"]),
                    end_date=date.fromisoformat(result["billEndDateFormatted"]),
                    unit_of_measure=unit,
                    usage_to_date=result["currentConsumption"],
                    cost_to_date=result["currentPrice"],
                    forecasted_usage=result["projectionConsumption"],
                    forecasted_cost=result["projectionPrice"],
                    typical_usage=result["averageBillingConsumption"],
                    typical_cost=result["averageBillingPrice"],
                )
            else:
                logger.debug(f"Have you entered the correct home? home={home}")
                raise HTTPServerError

        return forecast

    async def async_fetch(
        self,
        measurement: str,
        mode: str,
        start: datetime | None = datetime.fromtimestamp(967231641),
        end: datetime | None = datetime.now(),
        skip_itemization: bool | None = True,
    ) -> list[CostRead]:
        url = (
            "https://naapi-read.bidgely.com"
            "/v2.0/dashboard/users/"
            f"{self.user_id}"
            "/usage-chart-data"
        )
        ps = {
            "measurement-type": measurement,
            "date-format": "DATE_TIME",
            "mode": _aggregate_to_mode(mode),
            "start": f"{int(start.timestamp())}",
            "end": f"{int(end.timestamp())}",
            "skip-itemization": str(skip_itemization).lower(),
            "skip-ongoing-cycle": "true" if not skip_itemization else "false",
        }
        h = {"authorization": f"Bearer {self.access_token}"}

        result = []
        try:
            async with self.session.get(url, params=ps, headers=h) as resp:
                reads = await resp.json()
                if DEBUG_LOG_RESPONSE:
                    logger.debug(f"Fetched: {json.dumps(result, indent=2)}")
                logger.debug(f"Successful read from Bidgely for user: {self.user_id}")
                for read in reads["payload"]:
                    if (
                        not skip_itemization
                        and read["itemizationDetailsList"] is not None
                    ):
                        items = []
                        for item in read["itemizationDetailsList"]:
                            items.append(
                                Itemization(
                                    id=item["id"],
                                    category=item["category"],
                                    usage=int(item["usage"]),
                                    cost=int(item["cost"]),
                                    percentage=int(item["percentage"]),
                                    cost_percentage=int(item["costPercentage"]),
                                )
                            )
                    else:
                        items = None
                    result.append(
                        CostRead(
                            start_time=datetime.fromisoformat(
                                read["intervalStartDate"]
                            ),
                            end_time=datetime.fromisoformat(read["intervalEndDate"]),
                            consumption=read["consumption"],
                            cost=read["cost"],
                            temperature=read["temperature"],
                            itemization=items,
                        )
                    )
        except ClientResponseError as err:
            if err.status in (401, 403):
                logger.debug("Failed to read data from Bidgely due to InvalidAuth")
                raise InvalidAuth(err)
            else:
                raise CannotConnect(err)

        return result

    async def async_get_usage_data(
        self,
        measurement: str,
        mode: AggregateType = AggregateType.MONTH,
        start: datetime = datetime.fromtimestamp(967231641),
        end: datetime = datetime.now() - timedelta(days=1),
        skip_itemization: bool = True,
    ) -> list[CostRead]:
        """
        Only the year mode uses start. All others base results on end.
        The most up to date data you can retrieve is up to noon on the previous day.
        """
        result = []

        match mode:
            case AggregateType.MONTH:
                result = await self.async_fetch(
                    measurement, mode, start, end, skip_itemization
                )
            case AggregateType.DAY:
                n_months = (end - start).days // 30
                tasks = []
                for i in range(n_months):
                    months = 30 * (i + 1)
                    single = await self.async_fetch(
                        measurement,
                        mode,
                        start,
                        start + timedelta(days=months),
                    )
                    tasks.append(single)
                result = await asyncio.gather(*tasks)
                results = list(chain(*result))
            case AggregateType.HOUR:
                n_days = (end - start).days
                tasks = []
                for i in range(n_days):
                    single = self.async_fetch(
                        measurement,
                        mode,
                        start,
                        start + timedelta(days=i + 1),
                    )
                    tasks.append(single)
                result = await asyncio.gather(*tasks)
                results = list(chain(*result))
        return results

    async def async_get_breakdown(
        self,
        start: datetime = datetime.fromtimestamp(967231641),
        end: datetime = datetime.now() - timedelta(days=1),
    ) -> list[CostRead]:
        result = await self.async_fetch(
            "ELECTRIC",
            AggregateType.MONTH,
            start,
            end,
            skip_itemization=False,
        )
        return result
