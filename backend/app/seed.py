"""
Data seeder: generate 10k+ simulated form data.
Run: python -m app.seed
"""
import asyncio
import random
import math
from datetime import datetime, timedelta
from app.database import init_db, async_session
from app.models import (
    MerchantForm, ListingForm, ProductForm, ReportForm,
    SubmissionLog, FormStatus,
)

# Simulate Nanjing area coordinates
NANJING_BOUNDS = {
    "lat": (31.2, 32.4),
    "lng": (118.4, 119.2),
}

GEOHASH_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

CATEGORIES = ["餐饮", "零售", "科技", "教育", "医疗", "金融", "物流", "制造"]
REPORT_TYPES = ["daily", "weekly", "monthly"]

async def seed_merchants(count: int = 10000):
    """Seed merchant forms with geographic coordinates."""
    async with async_session() as session:
        for i in range(count):
            lat = random.uniform(*NANJING_BOUNDS["lat"])
            lng = random.uniform(*NANJING_BOUNDS["lng"])
            # Simple geohash-like prefix
            geohash = f"{GEOHASH_BASE32[int((lat - 31.2) * 100) % 32]}{GEOHASH_BASE32[int((lng - 118.4) * 100) % 32]}"

            form = MerchantForm(
                name=f"商户_{i:06d}",
                address=f"南京某路{i}号",
                status=random.choice(list(FormStatus)),
                category=random.choice(CATEGORIES),
                contact_name=f"联系人{i}",
                contact_phone=f"138{i:07d}",
                geohash=geohash,
                submitted_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            )
            from geoalchemy2 import WKTElement
            form.geo = WKTElement(f'POINT({lng} {lat})', srid=4326)
            session.add(form)

            if i > 0 and i % 1000 == 0:
                await session.commit()
                print(f"  Seeded {i}/{count} merchants...")

        await session.commit()
        print(f"✅ Seeded {count} merchants")


async def seed_listings(count: int = 5000):
    async with async_session() as session:
        # Get existing merchant IDs
        from sqlalchemy import select
        result = await session.execute(select(MerchantForm.id).limit(1000))
        merchant_ids = [r[0] for r in result.all()]

        for i in range(count):
            form = ListingForm(
                merchant_id=random.choice(merchant_ids),
                title=f"房源_{i:06d}",
                area=random.uniform(30, 300),
                price=random.uniform(2000, 20000),
                images=[],
                status=random.choice(list(FormStatus)),
                geohash=f"{GEOHASH_BASE32[random.randint(0, 31)]}{GEOHASH_BASE32[random.randint(0, 31)]}",
                submitted_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            )
            session.add(form)
            if i > 0 and i % 1000 == 0:
                await session.commit()
                print(f"  Seeded {i}/{count} listings...")
        await session.commit()
        print(f"✅ Seeded {count} listings")


async def seed_products(count: int = 5000):
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(MerchantForm.id).limit(1000))
        merchant_ids = [r[0] for r in result.all()]

        for i in range(count):
            form = ProductForm(
                merchant_id=random.choice(merchant_ids),
                name=f"商品_{i:06d}",
                sku=f"SKU{i:08d}",
                category=random.choice(CATEGORIES),
                price=round(random.uniform(10, 9999), 2),
                stock=random.randint(0, 10000),
                status=random.choice(list(FormStatus)),
                submitted_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            )
            session.add(form)
            if i > 0 and i % 1000 == 0:
                await session.commit()
                print(f"  Seeded {i}/{count} products...")
        await session.commit()
        print(f"✅ Seeded {count} products")


async def seed_submission_logs(count: int = 50000):
    """Seed submission logs for analytics."""
    async with async_session() as session:
        form_types = ["merchant", "listing", "product", "report"]
        statuses = ["start", "success", "fail", "timeout"]
        error_codes = ["FORM_001", "FORM_002", "DB_001", "NET_001", "AUTH_001"]

        for i in range(count):
            is_fail = random.random() < 0.08  # ~8% failure rate
            log = SubmissionLog(
                form_type=random.choice(form_types),
                merchant_id=f"m_{random.randint(1, 1000):06d}",
                status=random.choice(statuses) if not is_fail else "fail",
                duration_ms=random.randint(50, 5000),
                error_code=random.choice(error_codes) if is_fail else None,
                error_msg="模拟错误" if is_fail else None,
                geo_hash=f"{GEOHASH_BASE32[random.randint(0, 31)]}{GEOHASH_BASE32[random.randint(0, 31)]}",
                batch_id=f"batch_{random.randint(1, 100)}" if random.random() < 0.3 else None,
                created_at=datetime.utcnow() - timedelta(
                    hours=random.randint(0, 168),  # last 7 days
                    minutes=random.randint(0, 59),
                ),
            )
            session.add(log)
            if i > 0 and i % 5000 == 0:
                await session.commit()
                print(f"  Seeded {i}/{count} logs...")
        await session.commit()
        print(f"✅ Seeded {count} submission logs")


async def main():
    print("Initializing database...")
    await init_db()

    print("\n1. Seeding merchant forms (10k)...")
    await seed_merchants(10000)

    print("\n2. Seeding listing forms (5k)...")
    await seed_listings(5000)

    print("\n3. Seeding product forms (5k)...")
    await seed_products(5000)

    print("\n4. Seeding submission logs (50k)...")
    await seed_submission_logs(50000)

    print("\n🎉 All data seeded!")


if __name__ == "__main__":
    asyncio.run(main())
