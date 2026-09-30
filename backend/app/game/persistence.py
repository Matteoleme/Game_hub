from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.models import Game
from app.rooms.models import Room
from app.rooms.persistence_models import GameRecord, RoomRecord


async def persist_room(session: AsyncSession, room: Room) -> None:
    session.add(
        RoomRecord(
            id=room.id,
            code=room.code,
            host_user_id=room.host_user_id,
            status=room.status.value,
            created_at=room.created_at,
        )
    )
    await session.commit()


async def persist_room_closed(session: AsyncSession, room: Room) -> None:
    record = await session.scalar(select(RoomRecord).where(RoomRecord.id == room.id))
    if record is not None:
        record.status = room.status.value
        record.closed_at = room.created_at
        await session.commit()


async def persist_game_started(session: AsyncSession, game: Game) -> None:
    session.add(
        GameRecord(
            id=game.id,
            room_id=game.room_id,
            mode=game.mode,
            started_at=game.started_at,
        )
    )
    await session.commit()


async def persist_game_finished(session: AsyncSession, game: Game) -> None:
    record = await session.scalar(select(GameRecord).where(GameRecord.id == game.id))
    if record is not None:
        record.finished_at = game.finished_at
        await session.commit()
