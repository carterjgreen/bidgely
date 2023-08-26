import argparse
import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp

from bidgely import AggregateType, Bidgely

BIDGELY_URL = "https://naapi-read.bidgely.com"


async def _main() -> None:
    supported_utilities = ["HydroOttawa"]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--utility",
        help="The name of your utility",
        choices=supported_utilities,
        default="HydroOttawa",
    )
    parser.add_argument(
        "-u",
        "--username",
        help="Username for logging into the utility's website. "
        "If not provided, you will be asked for it",
        required=True,
    )
    parser.add_argument(
        "-p",
        "--password",
        help="Password for logging into the utility's website.",
        required=True,
    )
    parser.add_argument(
        "--account_id",
        help="Account number that appears on your bill",
    )
    parser.add_argument(
        "--aggregate_type",
        help="How to aggregate historical data. Defaults to day",
        choices=list(AggregateType),
        type=AggregateType,
        default=AggregateType.DAY,
    )
    parser.add_argument(
        "--start_date",
        help="Start datetime for historical data. Defaults to 30 days ago",
        type=lambda s: datetime.fromisoformat(s),
        default=datetime.now() - timedelta(days=30),
    )
    parser.add_argument(
        "--end_date",
        help="end datetime for historical data. Defaults to now",
        type=lambda s: datetime.fromisoformat(s),
        default=datetime.now(),
    )
    parser.add_argument(
        "-v", "--verbose", help="enable verbose logging", action="store_true"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    async with aiohttp.ClientSession() as session:
        bidgely = Bidgely(
            session, "Hydro Ottawa", args.username, args.password, args.account_id
        )
        await bidgely.async_login()
        print(f"Bidgely User ID: {bidgely.user_id}")

        usage = await bidgely.async_get_usage_data(
            "ELECTRIC",
            args.aggregate_type,
            start=args.start_date,
            end=args.end_date,
        )
        for read in usage:
            if read.consumption is not None:
                print(
                    f"From {read.start_time} to {read.end_time} - ",
                    f"Consumption: {read.consumption:6.2f} kWh ",
                    f"Cost: ${read.cost:4.2f}",
                )

        forecasted = await bidgely.async_get_forecast()
        print(forecasted)
        items = await bidgely.async_get_breakdown(
            start=datetime.now() - timedelta(days=29)
        )
        print(f"Usage from {items[0].start_time} to {items[0].end_time}")
        for item in items[0].itemization:
            print(
                f"Category: {item.category:>15} Usage: {item.usage:3} kWh",
                f"Cost: ${item.cost}",
            )


asyncio.run(_main())
