"""Apply a price CSV (sku_or_name, price_rub, in_stock, source, updated_at) to the DB."""

import argparse
import asyncio

import _common  # noqa: F401

from app.catalog.db_loader import load_db_components
from app.catalog.db_writer import apply_prices
from app.db.session import get_engine, get_session_maker
from app.pricing.providers import CsvPriceProvider


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    a = ap.parse_args()
    comps = await load_db_components()
    provider = CsvPriceProvider(a.csv, comps)
    prices = await provider.get_prices([c.id for c in comps])
    get_engine()
    async with get_session_maker()() as session:
        n = await apply_prices(session, prices)
    print(f"prices applied: {n}; unmatched rows: {len(provider.unmatched)}")
    for name in provider.unmatched:
        print("  unmatched:", name)


if __name__ == "__main__":
    asyncio.run(main())
