from discord.ext import commands
import discord
import logging
from datetime import datetime, timezone
from database import get_async_session
from models import (User, MessageActivity, VoiceSession, VoiceStateLog, PresenceStatusLog,
                    ActivityLog, UserNameHistory, CustomStatus, MessageType, DiscordStatus,
                    ActivityType, VoiceStateType)
from sqlmodel import select
from typing import Optional

events_logger = logging.getLogger('cogs.events')


class Events(commands.Cog):
    """Discord events handler for comprehensive data collection."""

    def __init__(self, bot):
        """Initialize the Events cog.

        Args:
            bot: Discord bot instance to attach events to.
        """
        self.bot = bot
        events_logger.info('Events cog initialized')

    async def get_or_create_user(self, user: discord.User, member: Optional[discord.Member] = None) -> User:
        """Get existing user or create new user record.

        Args:
            user: Discord user object to get or create.
            member: Optional member object for join date info.

        Returns:
            User: Database user record.
        """
        async with get_async_session() as session:
            statement = select(User).where(User.user_id == user.id)
            result = await session.execute(statement)
            db_user = result.scalar_one_or_none()

            if not db_user:
                join_date = member.joined_at if member else datetime.now(timezone.utc)
                db_user = User(user_id=user.id, first_seen=join_date)
                session.add(db_user)
                await session.commit()
                await session.refresh(db_user)
                events_logger.info(f"Created user record for {user.name} ({user.id})")

                # Create initial name history entry
                await self._create_name_history_entry(user, member, session)

            return db_user

    async def _create_name_history_entry(self, user: discord.User, member: Optional[discord.Member], session):
        """Create name history entry for user.

        Args:
            user: Discord user object.
            member: Optional member object for display name.
            session: Database session for operations.
        """
        # End any existing current name entries
        statement = select(UserNameHistory).where(
            UserNameHistory.user_id == user.id,
            UserNameHistory.effective_until.is_(None)
        )
        result = await session.execute(statement)
        current_entries = result.scalars().all()

        current_time = datetime.now(timezone.utc)
        for entry in current_entries:
            entry.effective_until = current_time
            session.add(entry)

        # Create new current name entry
        name_entry = UserNameHistory(
            user_id=user.id,
            username=user.name,
            display_name=member.display_name if member else user.display_name,
            global_name=user.global_name,
            effective_from=current_time
        )
        session.add(name_entry)
        await session.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot ready event."""
        events_logger.info(f'Bot ready! Logged in as {self.bot.user} (ID: {self.bot.user.id})')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join events.

        Args:
            member: Discord member who joined the server.
        """
        try:
            await self.get_or_create_user(member, member)
            events_logger.info(f"Member joined: {member.name} ({member.id})")
        except Exception as e:
            events_logger.error(f"Error handling member join for {member.name}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leave events.

        Args:
            member: Discord member who left the server.
        """
        try:
            # End any active sessions when user leaves
            await self._end_active_sessions(member.id)
            events_logger.info(f"Member left: {member.name} ({member.id})")
        except Exception as e:
            events_logger.error(f"Error handling member remove: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Handle member updates (name changes only).

        Args:
            before: Member state before the update.
            after: Member state after the update.
        """
        try:
            if (before.name != after.name or
                    before.display_name != after.display_name or
                    before.global_name != after.global_name):
                await self._handle_name_change(before, after)
        except Exception as e:
            events_logger.error(f"Error handling member update: {e}")

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Handle presence updates (status and activity changes).

        Args:
            before: Member state before presence update.
            after: Member state after presence update.
        """
        try:
            if before.status == after.status and before.activities == after.activities:
                return

            await self.get_or_create_user(after, after)

            if before.status != after.status:
                await self._handle_status_change(before, after)

            if before.activities != after.activities:
                await self._handle_activity_change(before, after)
                await self._handle_custom_status_change(before, after)

        except Exception as e:
            events_logger.error(f"Error handling presence update: {e}")

    async def _handle_name_change(self, before: discord.Member, after: discord.Member):
        """Handle name changes and update history.

        Args:
            before: Member state before name change.
            after: Member state after name change.
        """
        async with get_async_session() as session:
            await self.get_or_create_user(after, after)
            await self._create_name_history_entry(after, after, session)

            changes = []
            if before.name != after.name:
                changes.append(f"username: {before.name} -> {after.name}")
            if before.display_name != after.display_name:
                changes.append(f"display_name: {before.display_name} -> {after.display_name}")
            if before.global_name != after.global_name:
                changes.append(f"global_name: {before.global_name} -> {after.global_name}")

            events_logger.info(f"Name change for {after.id}: {', '.join(changes)}")

    async def _handle_status_change(self, before: discord.Member, after: discord.Member):
        """Handle presence status changes.

        Args:
            before: Member state before status change.
            after: Member state after status change.
        """
        async with get_async_session() as session:
            current_time = datetime.now(timezone.utc)

            # End previous status if exists
            statement = select(PresenceStatusLog).where(
                PresenceStatusLog.user_id == after.id,
                PresenceStatusLog.changed_at.is_(None)
            ).order_by(PresenceStatusLog.set_at.desc()).limit(1)

            result = await session.execute(statement)
            current_status = result.scalar_one_or_none()

            if current_status:
                current_status.changed_at = current_time
                session.add(current_status)

            # Clean up any other orphaned active statuses for this user
            statement = select(PresenceStatusLog).where(
                PresenceStatusLog.user_id == after.id,
                PresenceStatusLog.changed_at.is_(None)
            )
            result = await session.execute(statement)
            remaining_active = result.scalars().all()

            for orphaned_status in remaining_active:
                orphaned_status.changed_at = current_time
                session.add(orphaned_status)

            # Create new status entry
            try:
                status_type = DiscordStatus(after.status.name.lower())
            except ValueError:
                status_type = DiscordStatus.OFFLINE

            status_log = PresenceStatusLog(
                user_id=after.id,
                status_type=status_type,
                set_at=current_time
            )
            session.add(status_log)
            await session.commit()

            events_logger.info(f"{after.name}: {before.status.name} -> {after.status.name}")

    async def _handle_activity_change(self, before: discord.Member, after: discord.Member):
        """Handle activity changes (games, streaming, etc.).

        Args:
            before: Member state before activity change.
            after: Member state after activity change.
        """
        before_activities = self._extract_real_activities(before.activities)
        after_activities = self._extract_real_activities(after.activities)

        async with get_async_session() as session:
            current_time = datetime.now(timezone.utc)

            # End activities that stopped
            for activity_type, activity_name in before_activities:
                if (activity_type, activity_name) not in after_activities:
                    await self._end_activity(after.id, activity_type, activity_name, current_time, session)
                    events_logger.info(f"{after.name}: Stopped {activity_type.value} -> {activity_name}")

            # Start new activities
            for activity_type, activity_name in after_activities:
                if (activity_type, activity_name) not in before_activities:
                    await self._start_activity(after.id, activity_type, activity_name, current_time, session)
                    events_logger.info(f"{after.name}: Started {activity_type.value} -> {activity_name}")

            await session.commit()

    def _extract_real_activities(self, activities):
        """Extract real activities (not custom status) from Discord activities.

        Args:
            activities: List of Discord activities to filter.

        Returns:
            set: Set of (activity_type, activity_name) tuples.
        """
        real_activities = set()
        if activities:
            for activity in activities:
                if activity.type and activity.type.name.lower() != 'custom' and activity.name:
                    try:
                        activity_type = ActivityType(activity.type.name.lower())
                        real_activities.add((activity_type, activity.name))
                    except ValueError:
                        continue
        return real_activities

    async def _start_activity(self, user_id: int, activity_type: ActivityType, activity_name: str,
                              current_time: datetime, session):
        """Start new activity session.

        Args:
            user_id: Discord user ID.
            activity_type: Type of activity being started.
            activity_name: Name of the activity.
            current_time: Timestamp when activity started.
            session: Database session for operations.
        """
        activity_log = ActivityLog(
            user_id=user_id,
            activity_type=activity_type,
            activity_name=activity_name,
            started_at=current_time
        )
        session.add(activity_log)

    async def _end_activity(self, user_id: int, activity_type: ActivityType, activity_name: str,
                            current_time: datetime, session):
        """End existing activity session.

        Args:
            user_id: Discord user ID.
            activity_type: Type of activity being ended.
            activity_name: Name of the activity.
            current_time: Timestamp when activity ended.
            session: Database session for operations.
        """
        statement = select(ActivityLog).where(
            ActivityLog.user_id == user_id,
            ActivityLog.activity_type == activity_type,
            ActivityLog.activity_name == activity_name,
            ActivityLog.ended_at.is_(None)
        ).order_by(ActivityLog.started_at.desc()).limit(1)

        result = await session.execute(statement)
        activity_record = result.scalar_one_or_none()

        if activity_record:
            activity_record.ended_at = current_time
            session.add(activity_record)

    async def _handle_custom_status_change(self, before: discord.Member, after: discord.Member):
        """Handle custom status changes.

        Args:
            before: Member state before custom status change.
            after: Member state after custom status change.
        """
        before_custom = self._extract_custom_status(before.activities)
        after_custom = self._extract_custom_status(after.activities)

        if before_custom == after_custom:
            return

        # Only add new custom status if we have one
        if after_custom:
            status_text, emoji = after_custom

            async with get_async_session() as session:
                statement = select(CustomStatus).where(
                    CustomStatus.user_id == after.id,
                    CustomStatus.status_text == status_text,
                    CustomStatus.emoji == emoji
                )
                result = await session.execute(statement)
                existing_status = result.scalar_one_or_none()

                if not existing_status:
                    custom_status = CustomStatus(
                        user_id=after.id,
                        status_text=status_text,
                        emoji=emoji,
                        set_at=datetime.now(timezone.utc)
                    )
                    session.add(custom_status)
                    await session.commit()

                    emoji_part = f"{emoji} " if emoji else ""
                    events_logger.info(f"{after.name}: New Custom Status -> {emoji_part}{status_text}")
                else:
                    emoji_part = f"{emoji} " if emoji else ""
                    events_logger.debug(f"{after.name}: Duplicate custom status ignored -> {emoji_part}{status_text}")
        else:
            events_logger.debug(f"{after.name}: Custom status cleared (no action needed)")

    def _extract_custom_status(self, activities):
        """Extract custom status from activities.

        Args:
            activities: List of Discord activities to search.

        Returns:
            tuple: (status_text, emoji) or None if no custom status.
        """
        if not activities:
            return None

        for activity in activities:
            if (hasattr(activity, 'type') and activity.type and
                    activity.type.name.lower() == 'custom' and hasattr(activity, 'state')):
                status_text = activity.state
                emoji = str(activity.emoji) if hasattr(activity, 'emoji') and activity.emoji else None
                return (status_text, emoji)
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle message events.

        Args:
            message: Discord message that was sent.
        """
        if message.author.bot:
            return

        try:
            member = None
            if message.guild:
                member = message.guild.get_member(message.author.id)
            await self.get_or_create_user(message.author, member)

            async with get_async_session() as session:
                # Map Discord message type to our enum
                try:
                    msg_type = MessageType(message.type.name.lower())
                except (ValueError, AttributeError):
                    msg_type = MessageType.DEFAULT

                message_activity = MessageActivity(
                    message_id=message.id,
                    user_id=message.author.id,
                    channel_id=message.channel.id,
                    message_type=msg_type,
                    has_attachments=len(message.attachments) > 0,
                    has_embeds=len(message.embeds) > 0,
                    character_count=len(message.content) if message.content else 0,
                    sent_at=message.created_at
                )

                session.add(message_activity)
                await session.commit()

                channel_name = message.channel.name if hasattr(message.channel, 'name') else 'DM'
                events_logger.debug(f"Message from {message.author.name} in {channel_name}")

        except Exception as e:
            events_logger.error(f"Error handling message: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handle message edit events.

        Args:
            before: Message state before edit.
            after: Message state after edit.
        """
        if after.author.bot:
            return

        try:
            async with get_async_session() as session:
                statement = select(MessageActivity).where(MessageActivity.message_id == after.id)
                result = await session.execute(statement)
                message_record = result.scalar_one_or_none()

                if message_record:
                    message_record.character_count = len(after.content) if after.content else 0
                    message_record.has_attachments = len(after.attachments) > 0
                    message_record.has_embeds = len(after.embeds) > 0
                    session.add(message_record)
                    await session.commit()
                    events_logger.debug(f"Updated message record for {after.author.name}")

        except Exception as e:
            events_logger.error(f"Error handling message edit: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Handle message delete events.

        Args:
            message: Discord message that was deleted.
        """
        if message.author.bot:
            return
        events_logger.debug(f"Message deleted from {message.author.name} (ID: {message.id})")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        """Handle voice state changes.

        Args:
            member: Discord member whose voice state changed.
            before: Voice state before the change.
            after: Voice state after the change.
        """
        try:
            await self.get_or_create_user(member, member)
            current_time = datetime.now(timezone.utc)

            if before.channel and not after.channel:
                await self._handle_voice_leave(member, before, current_time)
            elif not before.channel and after.channel:
                await self._handle_voice_join(member, after, current_time)
            elif before.channel and after.channel and before.channel != after.channel:
                await self._handle_voice_move(member, before, after, current_time)
            elif before.channel and after.channel and before.channel == after.channel:
                await self._handle_voice_state_change(member, before, after, current_time)

        except Exception as e:
            events_logger.error(f"Error handling voice state update: {e}")

    async def _handle_voice_leave(self, member: discord.Member, before: discord.VoiceState, current_time: datetime):
        """Handle user leaving voice channel.

        Args:
            member: Discord member who left the channel.
            before: Voice state before leaving (contains channel info).
            current_time: Timestamp when user left.
        """
        async with get_async_session() as session:
            # End voice session
            statement = select(VoiceSession).where(
                VoiceSession.user_id == member.id,
                VoiceSession.channel_id == before.channel.id,
                VoiceSession.left_at.is_(None)
            ).order_by(VoiceSession.joined_at.desc()).limit(1)

            result = await session.execute(statement)
            voice_session = result.scalar_one_or_none()

            if voice_session:
                voice_session.left_at = current_time
                session.add(voice_session)

                # End all active voice states for this session
                await self._end_active_voice_states(voice_session.id, current_time, session)
                await session.commit()

                duration = (current_time - voice_session.joined_at).total_seconds()
                events_logger.info(f"{member.name} left {before.channel.name} (duration: {duration:.0f}s)")

    async def _handle_voice_join(self, member: discord.Member, after: discord.VoiceState, current_time: datetime):
        """Handle user joining voice channel.

        Args:
            member: Discord member who joined the channel.
            after: Voice state after joining (contains channel info).
            current_time: Timestamp when user joined.
        """
        async with get_async_session() as session:
            voice_session = VoiceSession(
                user_id=member.id,
                channel_id=after.channel.id,
                joined_at=current_time
            )
            session.add(voice_session)
            await session.commit()
            await session.refresh(voice_session)

            # Track initial voice states
            await self._track_voice_states(voice_session.id, after, current_time, session)
            await session.commit()

            events_logger.info(f"{member.name} joined {after.channel.name}")

    async def _handle_voice_move(self, member: discord.Member, before: discord.VoiceState,
                                 after: discord.VoiceState, current_time: datetime):
        """Handle user moving between voice channels.

        Args:
            member: Discord member who moved channels.
            before: Voice state before moving (old channel).
            after: Voice state after moving (new channel).
            current_time: Timestamp when move occurred.
        """
        await self._handle_voice_leave(member, before, current_time)
        await self._handle_voice_join(member, after, current_time)
        events_logger.info(f"{member.name} moved from {before.channel.name} to {after.channel.name}")

    async def _handle_voice_state_change(self, member: discord.Member, before: discord.VoiceState,
                                         after: discord.VoiceState, current_time: datetime):
        """Handle voice state changes within same channel.

        Args:
            member: Discord member whose voice state changed.
            before: Voice state before the change.
            after: Voice state after the change.
            current_time: Timestamp when state change occurred.
        """
        async with get_async_session() as session:
            # Get current voice session
            statement = select(VoiceSession).where(
                VoiceSession.user_id == member.id,
                VoiceSession.channel_id == after.channel.id,
                VoiceSession.left_at.is_(None)
            ).order_by(VoiceSession.joined_at.desc()).limit(1)

            result = await session.execute(statement)
            voice_session = result.scalar_one_or_none()

            if voice_session:
                # End changed states and start new ones
                await self._update_voice_states(voice_session.id, before, after, current_time, session)
                await session.commit()

                changes = self._get_voice_state_changes(before, after)
                if changes:
                    events_logger.debug(f"Voice state changes for {member.name}: {', '.join(changes)}")

    async def _track_voice_states(self, session_id: int, voice_state: discord.VoiceState,
                                  current_time: datetime, session):
        """Track initial voice states when joining.

        Args:
            session_id: Voice session ID to associate states with.
            voice_state: Discord voice state to track.
            current_time: Timestamp when states started.
            session: Database session for operations.
        """
        states_to_track = [
            (voice_state.deaf, VoiceStateType.DEAF),
            (voice_state.mute, VoiceStateType.MUTE),
            (voice_state.self_deaf, VoiceStateType.SELF_DEAF),
            (voice_state.self_mute, VoiceStateType.SELF_MUTE),
            (voice_state.self_stream, VoiceStateType.SELF_STREAM),
            (voice_state.self_video, VoiceStateType.SELF_VIDEO)
        ]

        for is_active, state_type in states_to_track:
            if is_active:
                voice_state_log = VoiceStateLog(
                    session_id=session_id,
                    state_type=state_type,
                    started_at=current_time
                )
                session.add(voice_state_log)

    async def _update_voice_states(self, session_id: int, before: discord.VoiceState,
                                   after: discord.VoiceState, current_time: datetime, session):
        """Update voice states when they change.

        Args:
            session_id: Voice session ID to update states for.
            before: Voice state before changes.
            after: Voice state after changes.
            current_time: Timestamp when changes occurred.
            session: Database session for operations.
        """
        state_changes = [
            (before.deaf, after.deaf, VoiceStateType.DEAF),
            (before.mute, after.mute, VoiceStateType.MUTE),
            (before.self_deaf, after.self_deaf, VoiceStateType.SELF_DEAF),
            (before.self_mute, after.self_mute, VoiceStateType.SELF_MUTE),
            (before.self_stream, after.self_stream, VoiceStateType.SELF_STREAM),
            (before.self_video, after.self_video, VoiceStateType.SELF_VIDEO)
        ]

        for before_state, after_state, state_type in state_changes:
            if before_state != after_state:
                if before_state:  # State ended
                    await self._end_voice_state(session_id, state_type, current_time, session)
                if after_state:  # State started
                    voice_state_log = VoiceStateLog(
                        session_id=session_id,
                        state_type=state_type,
                        started_at=current_time
                    )
                    session.add(voice_state_log)

    async def _end_voice_state(self, session_id: int, state_type: VoiceStateType,
                               current_time: datetime, session):
        """End a specific voice state.

        Args:
            session_id: Voice session ID containing the state.
            state_type: Type of voice state to end.
            current_time: Timestamp when state ended.
            session: Database session for operations.
        """
        statement = select(VoiceStateLog).where(
            VoiceStateLog.session_id == session_id,
            VoiceStateLog.state_type == state_type,
            VoiceStateLog.ended_at.is_(None)
        ).order_by(VoiceStateLog.started_at.desc()).limit(1)

        result = await session.execute(statement)
        voice_state = result.scalar_one_or_none()

        if voice_state:
            voice_state.ended_at = current_time
            session.add(voice_state)

    async def _end_active_voice_states(self, session_id: int, current_time: datetime, session):
        """End all active voice states for a session.

        Args:
            session_id: Voice session ID to end states for.
            current_time: Timestamp when states ended.
            session: Database session for operations.
        """
        statement = select(VoiceStateLog).where(
            VoiceStateLog.session_id == session_id,
            VoiceStateLog.ended_at.is_(None)
        )

        result = await session.execute(statement)
        active_states = result.scalars().all()

        for state in active_states:
            state.ended_at = current_time
            session.add(state)

    def _get_voice_state_changes(self, before: discord.VoiceState, after: discord.VoiceState):
        """Get list of voice state changes for logging.

        Args:
            before: Voice state before changes.
            after: Voice state after changes.

        Returns:
            list: List of change descriptions for logging.
        """
        changes = []
        state_attrs = ['deaf', 'mute', 'self_deaf', 'self_mute', 'self_stream', 'self_video']

        for attr in state_attrs:
            before_val = getattr(before, attr)
            after_val = getattr(after, attr)
            if before_val != after_val:
                changes.append(f"{attr}: {before_val} -> {after_val}")

        return changes

    async def _end_active_sessions(self, user_id: int):
        """End all active sessions when user leaves server.

        Args:
            user_id: Discord user ID whose sessions to end.
        """
        async with get_async_session() as session:
            current_time = datetime.now(timezone.utc)

            # End voice sessions
            statement = select(VoiceSession).where(
                VoiceSession.user_id == user_id,
                VoiceSession.left_at.is_(None)
            )
            result = await session.execute(statement)
            active_voice_sessions = result.scalars().all()

            for voice_session in active_voice_sessions:
                voice_session.left_at = current_time
                session.add(voice_session)
                await self._end_active_voice_states(voice_session.id, current_time, session)

            # End presence status
            statement = select(PresenceStatusLog).where(
                PresenceStatusLog.user_id == user_id,
                PresenceStatusLog.changed_at.is_(None)
            ).order_by(PresenceStatusLog.set_at.desc()).limit(1)

            result = await session.execute(statement)
            active_status = result.scalar_one_or_none()

            if active_status:
                active_status.changed_at = current_time
                session.add(active_status)

            # End activities
            statement = select(ActivityLog).where(
                ActivityLog.user_id == user_id,
                ActivityLog.ended_at.is_(None)
            )
            result = await session.execute(statement)
            active_activities = result.scalars().all()

            for activity in active_activities:
                activity.ended_at = current_time
                session.add(activity)

            await session.commit()


async def setup(bot):
    """Set up the Events cog.

    Args:
        bot: Discord bot instance to add the cog to.
    """
    await bot.add_cog(Events(bot))
    events_logger.info('Events cog loaded')
