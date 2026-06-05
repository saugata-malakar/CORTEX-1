# Cortex — scripts/seed_db.py
import asyncio
from api.database import init_db, close_db, get_session
from api.models import Organization, User, Building, UserRole
from api.auth import hash_password

async def seed():
    print("Initializing DB connection...")
    await init_db()
    
    # We must access the internal session factory configured by init_db()
    from api.database import _session_factory
    if not _session_factory:
        print("Error: Database not initialized.")
        return
        
    async with _session_factory() as session:
        from sqlalchemy import select
        # 1. Create Organization
        org_res = await session.execute(select(Organization).where(Organization.slug == "cortex"))
        org = org_res.scalar_one_or_none()
        if not org:
            org = Organization(name="Cortex Corporation", slug="cortex")
            session.add(org)
            await session.flush()
            print(f"Created Organization: {org.id}")
        else:
            print(f"Organization already exists: {org.id}")
            
        # 2. Create User (Admin/Engineer)
        user_res = await session.execute(select(User).where(User.email == "admin@cortex.com"))
        user = user_res.scalar_one_or_none()
        if not user:
            user = User(
                org_id=org.id,
                email="admin@cortex.com",
                hashed_pw=hash_password("CortexPass123!"),
                full_name="Cortex Administrator",
                role=UserRole.ADMIN,
                is_active=True
            )
            session.add(user)
            await session.flush()
            print(f"Created User: {user.id}")
        else:
            print(f"User already exists: {user.id}")
            
        # 3. Create Building
        building_res = await session.execute(select(Building).where(Building.name == "Cortex Headquarters"))
        building = building_res.scalar_one_or_none()
        if not building:
            building = Building(
                org_id=org.id,
                name="Cortex Headquarters",
                address="123 AI Boulevard, Tech City",
                lat=22.56,
                lng=87.31,
                metadata_={"type": "office_building"}
            )
            session.add(building)
            await session.flush()
            print(f"Created Building: {building.id}")
        else:
            print(f"Building already exists: {building.id}")
            
        await session.commit()
        print("Database seeding completed successfully.")
        
    await close_db()

if __name__ == "__main__":
    asyncio.run(seed())
