"""A coherent starting point for trying the platform end to end.

Seeds the people, the places and the themes — the reference data a workflow
needs before it can run. Nothing with a lifecycle is created here on purpose:
evidence, signals and decisions are driven through the API by ``demo.sh``, so
the audit trail is real rather than manufactured, and what you see on the
change feed is what actually happened.

Six people, because the platform refuses self-certification and a single
account cannot demonstrate it: a verifier cannot approve their own
verification, an approver cannot publish what they approved, and the owner of
an action cannot record it as done.

    DATABASE_URL=postgresql://...  python scripts/demo_seed.py
"""

import os
from datetime import date, timedelta

os.environ.setdefault("DATABASE_URL", "postgresql://epiro:epiro_password@localhost:5432/epiro_demo")

from app.database import SessionLocal
from app.models import (
    Geography,
    GeographyLevel,
    Organisation,
    Role,
    Source,
    SourceType,
    ThematicArea,
    User,
    user_organisation,
)
from app.security import hash_password

PASSWORD = "final-test-password"
db = SessionLocal()

org = Organisation(name="Water Directorate", code="water")
db.add(org)
db.commit()
db.refresh(org)

people = {}
for email, first, last, role in [
    ("researcher@example.com", "Amina", "Researcher", Role.RESEARCHER),
    ("verifier@example.com", "Bala", "Verifier", Role.VERIFIER),
    ("approver@example.com", "Chidi", "Approver", Role.APPROVER),
    ("editor@example.com", "Dami", "Editor", Role.EDITOR),
    ("executive@example.com", "Ese", "Executive", Role.EXECUTIVE),
    ("analyst@example.com", "Femi", "Analyst", Role.ANALYST),
]:
    u = User(email=email, password_hash=hash_password(PASSWORD), first_name=first, last_name=last)
    db.add(u)
    db.commit()
    db.refresh(u)
    db.execute(user_organisation.insert().values(user_id=u.id, organisation_id=org.id, role=role))
    db.commit()
    people[email] = str(u.id)

country = Geography(name="Nigeria", level=GeographyLevel.COUNTRY)
db.add(country)
db.commit()
db.refresh(country)
kano = Geography(name="Kano State", level=GeographyLevel.STATE, parent_id=country.id)
niger = Geography(name="Niger State", level=GeographyLevel.STATE, parent_id=country.id)
db.add_all([kano, niger])
db.commit()
db.refresh(kano)
db.refresh(niger)

water = ThematicArea(name="Water and sanitation", code="water", order=0)
roads = ThematicArea(name="Roads and transport", code="roads", order=1)
db.add_all([water, roads])
db.commit()
db.refresh(water)
db.refresh(roads)

source = Source(
    organisation_id=org.id, name="LGA works register", source_type=SourceType.OFFICIAL_DOCUMENT
)
db.add(source)
db.commit()
db.refresh(source)

print("ORG=%s" % org.id)
print("SOURCE=%s" % source.id)
print("KANO=%s" % kano.id)
print("WATER=%s" % water.id)
for email, uid in people.items():
    print("USER_%s=%s" % (email.split("@")[0].upper(), uid))
