from discord.ext import commands
import discord
import logging
from datetime import datetime, timezone
from database import get_async_session
from models import User, MessageActivity, VoiceActivity, PresenceActivity, UserNameHistory
from sqlmodel import select
from typing import Optional

events_logger = logging.getLogger('cogs.events')


class Events(commands.Cog):
    """
    A cog that handles various Discord events for comprehensive data collection.

    This cog captures and stores all relevant Discord activity including:
    - User management (joins, leaves, updates)
    - Message activity (sends, edits, deletes)
    - Voice channel activity (joins, leaves, state changes)
    - Presence updates (status changes, activities)

    Attributes:
        bot: The Discord bot instance
    """
    def __init__(self, bot):
        """
        Initialize the Events cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        events_logger.info('Events cog initialized')

    async def get_or_create_user(self, user: discord.User, member: Optional[discord.Member] = None) -> User:
        """
        Get existing user from database or create new user record.

        Args:
            user: Discord user object
            member: Optional Discord member object (for join date)

        Returns:
            User: Database user record
        """
        async with get_async_session() as session:
            # Check if user exists
            statement = select(User).where(User.user_id == user.id)
            result = await session.execute(statement)
            db_user = result.scalar_one_or_none()

            if db_user:
                # Update existing user info if changed
                updated = False
                if db_user.username != user.name:
                    db_user.username = user.name
                    updated = True
                if db_user.display_name != user.display_name:
                    db_user.display_name = user.display_name
                    updated = True
                if db_user.global_name != user.global_name:
                    db_user.global_name = user.global_name
                    updated = True

                if updated:
                    db_user.last_updated = datetime.now(timezone.utc)
                    session.add(db_user)
                    await session.commit()
                    await session.refresh(db_user)
                    events_logger.debug(f"Updated user info for {user.name} ({user.id})")
            else:
                # Create new user - use member join date if available
                join_date = member.joined_at if member else datetime.now(timezone.utc)
                db_user = User(
                    user_id=user.id,
                    username=user.name,
                    display_name=user.display_name,
                    global_name=user.global_name,
                    first_seen=join_date,
                    last_updated=datetime.now(timezone.utc)
                )
                session.add(db_user)
                await session.commit()
                await session.refresh(db_user)
                events_logger.info(f"Created new user record for {user.name} ({user.id}) - joined: {join_date}")

            return db_user

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event handler for when the bot is ready and connected to Discord.

        Logs bot information and connected guild count.
        """
        events_logger.info(f'Bot ready! Logged in as {self.bot.user} (ID: {self.bot.user.id})')
        events_logger.info(f'Monitoring {len(self.bot.guilds)} guild{"s" if len(self.bot.guilds) != 1 else ""}')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Event handler for when a member joins a guild.

        Args:
            member: The member who joined
        """
        try:
            await self.get_or_create_user(member, member)
            events_logger.info(f"Member joined: {member.name} ({member.id}) in guild {member.guild.name}")
        except Exception as e:
            events_logger.error(f"Error handling member join for {member.name}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """
        Event handler for when a member leaves a guild.

        Args:
            member: The member who left
        """
        try:
            events_logger.info(f"Member left: {member.name} ({member.id}) from guild {member.guild.name}")
        except Exception as e:
            events_logger.error(f"Error handling member remove for {member.name}: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Event handler for when a member is updated (nickname, roles, etc.).

        Note: This handles name changes only. Presence updates are handled
        by on_presence_update for better reliability.

        Args:
            before: Member state before the update
            after: Member state after the update
        """
        try:
            # Handle name changes only
            if (before.name != after.name or
                    before.display_name != after.display_name or
                    before.global_name != after.global_name):
                await self._handle_name_change(before, after)

        except Exception as e:
            events_logger.error(f"Error handling member update for {after.name}: {e}")

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        """
        Event handler for presence updates (status and activity changes).

        This is the primary event for tracking user presence changes,
        more reliable than on_member_update for presence data.

        Args:
            before: Member state before presence update
            after: Member state after presence update
        """
        try:
            # Only process if there are actual changes
            if before.status == after.status and before.activities == after.activities:
                return

            # Ensure user exists in database
            await self.get_or_create_user(after, after)

            # Record the presence change
            await self._handle_presence_change(before, after)

        except Exception as e:
            events_logger.error(f"Error handling presence update for {after.name}: {e}")

    async def _handle_name_change(self, before: discord.Member, after: discord.Member):
        """
        Handle username/display name changes and record them in history.

        Args:
            before: Member state before the name change
            after: Member state after the name change
        """
        async with get_async_session() as session:
            await self.get_or_create_user(after, after)

            change_type = None
            if before.name != after.name:
                change_type = "username"
            elif before.display_name != after.display_name:
                change_type = "display_name"
            elif before.global_name != after.global_name:
                change_type = "global_name"

            if change_type:
                name_history = UserNameHistory(
                    user_id=after.id,
                    old_username=before.name if change_type == "username" else None,
                    new_username=after.name if change_type == "username" else None,
                    old_display_name=before.display_name if change_type == "display_name" else None,
                    new_display_name=after.display_name if change_type == "display_name" else None,
                    old_global_name=before.global_name if change_type == "global_name" else None,
                    new_global_name=after.global_name if change_type == "global_name" else None,
                    change_type=change_type,
                    changed_at=datetime.now(timezone.utc)
                )
                session.add(name_history)
                await session.commit()
                events_logger.info(f"Recorded {change_type} change for {after.name} ({after.id})")

    async def _handle_presence_change(self, before: discord.Member, after: discord.Member):
        """
        Handle presence/status changes and record activity data.

        Args:
            before: Member state before the presence change
            after: Member state after the presence change
        """

        async with get_async_session() as session:
            # Get the last presence record to calculate duration
            statement = select(PresenceActivity).where(
                PresenceActivity.user_id == after.id
            ).order_by(PresenceActivity.changed_at.desc()).limit(1)

            result = await session.execute(statement)
            last_presence = result.scalar_one_or_none()

            # Calculate duration of previous status
            duration_seconds = None
            if last_presence and last_presence.duration_seconds is None:
                duration_seconds = int((datetime.now(timezone.utc) - last_presence.changed_at).total_seconds())
                last_presence.duration_seconds = duration_seconds
                session.add(last_presence)

            # Get primary activity
            activity_type = None
            activity_name = None
            if after.activities:
                primary_activity = after.activities[0]
                activity_type = primary_activity.type.name.lower() if primary_activity.type else None
                activity_name = primary_activity.name

            # Create new presence record
            presence = PresenceActivity(
                user_id=after.id,
                status=after.status.name,
                previous_status=before.status.name if before.status != after.status else None,
                activity_type=activity_type,
                activity_name=activity_name,
                changed_at=datetime.now(timezone.utc)
            )

            session.add(presence)
            await session.commit()

            if before.status != after.status:
                events_logger.info(f"{after.name}: {before.status.name} → {after.status.name}")

            if before.activities != after.activities:
                if after.activities and activity_name:
                    events_logger.info(f"{after.name}: Activity → {activity_name}")
                elif not after.activities:
                    events_logger.info(f"{after.name}: Activity cleared")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Event handler for when a message is sent.

        Args:
            message: The message that was sent
        """
        if message.author.bot:
            return

        try:
            member = None
            if message.guild:
                member = message.guild.get_member(message.author.id)
            await self.get_or_create_user(message.author, member)

            # Record message activity
            async with get_async_session() as session:
                message_activity = MessageActivity(
                    user_id=message.author.id,
                    channel_id=message.channel.id,
                    message_id=message.id,
                    message_type=message.type.name if message.type else "default",
                    has_attachments=len(message.attachments) > 0,
                    has_embeds=len(message.embeds) > 0,
                    character_count=len(message.content) if message.content else 0,
                    sent_at=message.created_at
                )

                session.add(message_activity)
                await session.commit()

                channel_name = message.channel.name if hasattr(message.channel, 'name') else 'DM'
                events_logger.debug(f"Recorded message from {message.author.name} in {channel_name}")

        except Exception as e:
            events_logger.error(f"Error handling message from {message.author.name}: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """
        Event handler for when a message is edited.

        Args:
            before: Message state before edit
            after: Message state after edit
        """
        # Ignore bot messages
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
            events_logger.error(f"Error handling message edit from {after.author.name}: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """
        Event handler for when a message is deleted.

        Args:
            message: The message that was deleted
        """
        if message.author.bot:
            return

        try:
            events_logger.info(f"Message deleted from {message.author.name} (ID: {message.id})")

        except Exception as e:
            events_logger.error(f"Error handling message deletion: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        """
        Event handler for voice state changes (join/leave/move channels).

        Args:
            member: The member whose voice state changed
            before: Voice state before the change
            after: Voice state after the change
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
            events_logger.error(f"Error handling voice state update for {member.name}: {e}")

    async def _handle_voice_leave(self, member: discord.Member, before: discord.VoiceState, current_time: datetime):
        """
        Handle user leaving a voice channel and calculate session duration.

        Args:
            member: Discord member who left the voice channel
            before: Voice state before leaving (contains the channel info)
            current_time: Timestamp when the user left
        """
        async with get_async_session() as session:
            # Find the most recent voice session for this user/channel
            statement = select(VoiceActivity).where(
                VoiceActivity.user_id == member.id,
                VoiceActivity.channel_id == before.channel.id,
                VoiceActivity.left_at.is_(None)
            ).order_by(VoiceActivity.joined_at.desc()).limit(1)

            result = await session.execute(statement)
            voice_session = result.scalar_one_or_none()

            if voice_session:
                # Update the session with leave time and duration
                voice_session.left_at = current_time
                duration = (current_time - voice_session.joined_at).total_seconds()
                voice_session.duration_seconds = int(duration)

                session.add(voice_session)
                await session.commit()

                events_logger.info(f"{member.name} left voice channel {before.channel.name} "
                                   f"(duration: {duration:.0f}s)")

    async def _handle_voice_join(self, member: discord.Member, after: discord.VoiceState, current_time: datetime):
        """
        Handle user joining a voice channel and create new session record.

        Args:
            member: Discord member who joined the voice channel
            after: Voice state after joining (contains the channel and state info)
            current_time: Timestamp when the user joined
        """
        async with get_async_session() as session:
            voice_session = VoiceActivity(
                user_id=member.id,
                channel_id=after.channel.id,
                joined_at=current_time,
                was_muted=after.self_mute or after.mute,
                was_deafened=after.self_deaf or after.deaf,
                was_streaming=after.self_stream or False,
                was_video=after.self_video or False
            )

            session.add(voice_session)
            await session.commit()

            events_logger.info(f"{member.name} joined voice channel {after.channel.name}")

    async def _handle_voice_move(self, member: discord.Member, before: discord.VoiceState,
                                 after: discord.VoiceState, current_time: datetime):
        """
        Handle user moving between voice channels by ending old session and starting new one.

        Args:
            member: Discord member who moved channels
            before: Voice state before moving (old channel)
            after: Voice state after moving (new channel)
            current_time: Timestamp when the move occurred
        """
        await self._handle_voice_leave(member, before, current_time)
        await self._handle_voice_join(member, after, current_time)

        events_logger.info(f"{member.name} moved from {before.channel.name} to {after.channel.name}")

    async def _handle_voice_state_change(self, member: discord.Member, before: discord.VoiceState,
                                         after: discord.VoiceState, current_time: datetime):
        """
        Handle voice state changes within the same channel (mute, deaf, streaming, video).

        Args:
            member: Discord member whose voice state changed
            before: Voice state before the change
            after: Voice state after the change
            current_time: Timestamp when the state change occurred
        """
        changes = []

        if before.self_mute != after.self_mute:
            changes.append(f"self_mute: {before.self_mute} -> {after.self_mute}")
        if before.self_deaf != after.self_deaf:
            changes.append(f"self_deaf: {before.self_deaf} -> {after.self_deaf}")
        if before.self_stream != after.self_stream:
            changes.append(f"self_stream: {before.self_stream} -> {after.self_stream}")
        if before.self_video != after.self_video:
            changes.append(f"self_video: {before.self_video} -> {after.self_video}")

        if changes:
            changes_str = ', '.join(changes)
            events_logger.debug(f"Voice state changes for {member.name} in {after.channel.name}: {changes_str}")


async def setup(bot):
    """
    Set up the Events cog.

    Args:
        bot: The Discord bot instance to add this cog to
    """
    await bot.add_cog(Events(bot))
    events_logger.info('Events cog loaded')
