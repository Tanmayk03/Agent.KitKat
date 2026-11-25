"""
Agent KitKat - Global automation halt (Emergency Stop).

Emergency Stop closes every browser and then HALTS automation until you press Resume:
- browser runs and previews are refused (HTTP 423),
- discovery runs (manual, background, scheduled) are refused,
- the daily schedule is paused (and restored on Resume if it was enabled).
The flag is stored in your profile, so it survives restarts.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.profile_service import ProfileService

HALT_KEY = "automation_halted"
HALT_MESSAGE = "Automation is halted by Emergency Stop. Press Resume (Settings or the banner) to continue."


class AutomationHaltedError(RuntimeError):
    pass


async def is_halted(session: AsyncSession) -> bool:
    profile = await ProfileService.get_or_create_profile(session)
    return bool((profile.application_preferences or {}).get(HALT_KEY))


async def set_halted(session: AsyncSession, halted: bool) -> None:
    profile = await ProfileService.get_or_create_profile(session)
    prefs = dict(profile.application_preferences or {})
    prefs[HALT_KEY] = halted
    profile.application_preferences = prefs
    await session.commit()


async def ensure_not_halted(session: AsyncSession) -> None:
    if await is_halted(session):
        raise AutomationHaltedError(HALT_MESSAGE)
