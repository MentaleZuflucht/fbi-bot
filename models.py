from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import BigInteger, DateTime, CheckConstraint, Index, Enum as SQLEnum
from enum import Enum


class MessageType(str, Enum):
    """Discord message types as Python enum."""
    DEFAULT = "default"
    RECIPIENT_ADD = "recipient_add"
    RECIPIENT_REMOVE = "recipient_remove"
    CALL = "call"
    CHANNEL_NAME_CHANGE = "channel_name_change"
    CHANNEL_ICON_CHANGE = "channel_icon_change"
    CHANNEL_PINNED_MESSAGE = "channel_pinned_message"
    USER_JOIN = "user_join"
    GUILD_BOOST = "guild_boost"
    GUILD_BOOST_TIER_1 = "guild_boost_tier_1"
    GUILD_BOOST_TIER_2 = "guild_boost_tier_2"
    GUILD_BOOST_TIER_3 = "guild_boost_tier_3"
    CHANNEL_FOLLOW_ADD = "channel_follow_add"
    GUILD_DISCOVERY_DISQUALIFIED = "guild_discovery_disqualified"
    GUILD_DISCOVERY_REQUALIFIED = "guild_discovery_requalified"
    GUILD_DISCOVERY_GRACE_PERIOD_INITIAL_WARNING = "guild_discovery_grace_period_initial_warning"
    GUILD_DISCOVERY_GRACE_PERIOD_FINAL_WARNING = "guild_discovery_grace_period_final_warning"
    THREAD_CREATED = "thread_created"
    REPLY = "reply"
    CHAT_INPUT_COMMAND = "chat_input_command"
    THREAD_STARTER_MESSAGE = "thread_starter_message"
    GUILD_INVITE_REMINDER = "guild_invite_reminder"
    CONTEXT_MENU_COMMAND = "context_menu_command"
    ROLE_SUBSCRIPTION_PURCHASE = "role_subscription_purchase"
    INTERACTION_PREMIUM_UPSELL = "interaction_premium_upsell"
    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    STAGE_SPEAKER = "stage_speaker"
    STAGE_RAISE_HAND = "stage_raise_hand"
    STAGE_TOPIC = "stage_topic"
    GUILD_APPLICATION_PREMIUM_SUBSCRIPTION = "guild_application_premium_subscription"
    GUILD_INCIDENT_ALERT_MODE_ENABLED = "guild_incident_alert_mode_enabled"
    GUILD_INCIDENT_ALERT_MODE_DISABLED = "guild_incident_alert_mode_disabled"
    GUILD_INCIDENT_REPORT_RAID = "guild_incident_report_raid"
    GUILD_INCIDENT_REPORT_FALSE_ALARM = "guild_incident_report_false_alarm"
    PURCHASE_NOTIFICATION = "purchase_notification"
    POLL_RESULT = "poll_result"


class DiscordStatus(str, Enum):
    """Discord status types as Python enum."""
    ONLINE = "online"
    IDLE = "idle"
    DND = "dnd"
    OFFLINE = "offline"
    STREAMING = "streaming"


class ActivityType(str, Enum):
    """Discord activity types as Python enum."""
    COMPETING = "competing"
    CUSTOM = "custom"
    LISTENING = "listening"
    PLAYING = "playing"
    STREAMING = "streaming"
    WATCHING = "watching"


class VoiceStateType(str, Enum):
    """Discord voice state types as Python enum."""
    DEAF = "deaf"
    MUTE = "mute"
    SELF_DEAF = "self_deaf"
    SELF_MUTE = "self_mute"
    SELF_STREAM = "self_stream"
    SELF_VIDEO = "self_video"


class User(SQLModel, table=True):
    """
    Represents a Discord user in the database.

    Current names are derived from the most recent entry in the user_name_history table.

    Attributes:
        user_id: Discord user ID (snowflake) - primary key
        first_seen: When the user first joined the Discord server (member since date)
    """
    __tablename__ = "user"

    user_id: int = Field(
        primary_key=True,
        sa_type=BigInteger,
        description="Discord user ID (snowflake)"
    )

    first_seen: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the user first joined the Discord server (member since)"
    )

    messages: List["MessageActivity"] = Relationship(back_populates="user")
    voice_sessions: List["VoiceSession"] = Relationship(back_populates="user")
    presence_logs: List["PresenceStatusLog"] = Relationship(back_populates="user")
    activity_logs: List["ActivityLog"] = Relationship(back_populates="user")
    custom_statuses: List["CustomStatus"] = Relationship(back_populates="user")
    name_history: List["UserNameHistory"] = Relationship(back_populates="user")


class MessageActivity(SQLModel, table=True):
    """
    Tracks when users send messages in channels.

    Records every message sent by users for analysis of messaging patterns and
    activity levels. Does not store message content, only metadata.

    Attributes:
        message_id: Discord message ID (snowflake) - primary key
        user_id: Discord user ID who sent the message
        channel_id: Discord channel ID where message was sent
        message_type: Discord message type enum
        has_attachments: Whether the message contained file attachments
        has_embeds: Whether the message contained rich embeds
        character_count: Length of the message content in characters
        sent_at: Timestamp when the message was sent
    """
    __tablename__ = "message_activity"

    message_id: int = Field(
        primary_key=True,
        sa_type=BigInteger,
        description="Discord message ID (snowflake)"
    )
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID who sent the message"
    )
    channel_id: int = Field(
        sa_type=BigInteger,
        index=True,
        description="Discord channel ID where message was sent"
    )

    message_type: MessageType = Field(
        default=MessageType.DEFAULT,
        sa_type=SQLEnum(MessageType, name="message_type_enum"),
        description="Discord message type",
        sa_column_kwargs={"nullable": False}
    )
    has_attachments: bool = Field(default=False, description="Whether message had attachments")
    has_embeds: bool = Field(default=False, description="Whether message had embeds")
    character_count: Optional[int] = Field(default=None, description="Length of message content")

    sent_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        index=True,
        description="When the message was sent"
    )

    user: User = Relationship(back_populates="messages")


class VoiceSession(SQLModel, table=True):
    """
    Tracks voice channel sessions (join/leave events).

    Records when users join and leave voice channels. Individual voice states
    are tracked separately in VoiceStateLog.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID who joined/left voice
        channel_id: Discord voice channel ID
        joined_at: Timestamp when user joined the voice channel
        left_at: Timestamp when user left (NULL if still in channel)
    """
    __tablename__ = "voice_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )
    channel_id: int = Field(
        sa_type=BigInteger,
        index=True,
        description="Discord voice channel ID"
    )

    joined_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        index=True,
        description="When user joined the voice channel"
    )
    left_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True),
        default=None,
        description="When user left the voice channel (NULL if still in channel)"
    )

    user: User = Relationship(back_populates="voice_sessions")
    voice_states: List["VoiceStateLog"] = Relationship(back_populates="session")


class VoiceStateLog(SQLModel, table=True):
    """
    Tracks individual voice state changes during voice sessions.

    Records when users change their voice states
    during a voice session. Duration can be calculated from started_at and ended_at.

    Attributes:
        id: Auto-incrementing primary key
        session_id: Reference to the voice session
        state_type: Type of voice state
        started_at: When this state became active
        ended_at: When this state ended (NULL if still active)
    """
    __tablename__ = "voice_state_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(
        foreign_key="voice_sessions.id",
        index=True,
        description="Reference to the voice session"
    )
    state_type: VoiceStateType = Field(
        sa_type=SQLEnum(VoiceStateType, name="voice_state_type_enum"),
        index=True,
        description="Type of voice state"
    )

    started_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
        description="When this state became active"
    )
    ended_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True),
        default=None,
        description="When this state ended (NULL if still active)"
    )

    session: VoiceSession = Relationship(back_populates="voice_states")


class PresenceStatusLog(SQLModel, table=True):
    """
    Tracks user presence status periods with explicit start/end times.

    Records when users enter and exit specific presence states (online, idle, dnd, offline).
    Duration can be calculated directly from set_at and cleared_at timestamps.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID whose status changed
        status_type: The Discord presence status
        set_at: When this status became active
        cleared_at: When this status ended (NULL if still active)
    """
    __tablename__ = "presence_status_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )
    status_type: DiscordStatus = Field(
        sa_type=SQLEnum(DiscordStatus, name="discord_status_enum"),
        index=True,
        description="The Discord presence status"
    )

    set_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
        description="When this status became active"
    )
    changed_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True),
        default=None,
        description="When this status ended (NULL if still active)"
    )

    user: User = Relationship(back_populates="presence_logs")


class ActivityLog(SQLModel, table=True):
    """
    Tracks user activities like playing games, streaming, listening to music.

    This table records when users start/stop activities with correct activity types.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID who started/stopped the activity
        activity_type: Type of activity
        activity_name: Name of the activity
        started_at: When the activity started
        ended_at: When the activity ended (NULL if still active)
    """
    __tablename__ = "activity_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )

    activity_type: ActivityType = Field(
        sa_type=SQLEnum(ActivityType, name="activity_type_enum"),
        description="Type of activity (competing, custom, listening, playing, streaming, watching)",
        sa_column_kwargs={"nullable": False}
    )
    activity_name: str = Field(
        max_length=128,
        description="Name of the activity (game name, stream title, etc.)",
        sa_column_kwargs={"nullable": False}
    )

    started_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
        description="When the activity started"
    )
    ended_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True),
        default=None,
        description="When the activity ended (NULL if still active)"
    )

    user: "User" = Relationship(back_populates="activity_logs")


class CustomStatus(SQLModel, table=True):
    """
    Tracks custom status changes separately from presence activity.

    Custom statuses are user-set messages with optional emojis that appear
    below their username.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID who set the custom status
        status_text: The custom status message text
        emoji: Emoji used in the custom status (name or unicode)
        set_at: When the custom status was set
        cleared_at: When the custom status was cleared (NULL if still active)
    """
    __tablename__ = "custom_status"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )

    status_text: Optional[str] = Field(
        default=None,
        max_length=128,
        description="The custom status message text"
    )
    emoji: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Emoji used in custom status (name or unicode)"
    )

    set_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
        description="When the custom status was set"
    )
    cleared_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True),
        default=None,
        description="When the custom status was cleared (NULL if still active)"
    )

    user: "User" = Relationship(back_populates="custom_statuses")


class UserNameHistory(SQLModel, table=True):
    """
    Stores all username states over time. This is the single source for user names.

    Each row represents a user's name state at a specific point in time.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID
        username: Discord username at this point in time
        display_name: Discord display name (server nickname) at this point in time
        global_name: Discord global display name at this point in time
        effective_from: When this name state became active
        effective_until: When this name state ended (NULL if current)
    """
    __tablename__ = "user_names_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )

    username: str = Field(default=None, max_length=32, description="Discord username")
    display_name: Optional[str] = Field(default=None, max_length=32, description="Discord display name")
    global_name: Optional[str] = Field(default=None, max_length=32, description="Discord global display name")

    effective_from: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
        description="When this name state became active"
    )
    effective_until: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True),
        default=None,
        index=True,
        description="When this name state ended (NULL if current)"
    )

    user: "User" = Relationship(back_populates="name_history")


Index('idx_message_activity_user_sent', 'message_activity.user_id', 'message_activity.sent_at')
Index('idx_voice_sessions_user_joined', 'voice_sessions.user_id', 'voice_sessions.joined_at')
Index('idx_voice_state_log_session_started', 'voice_state_log.session_id', 'voice_state_log.started_at')
Index('idx_voice_state_log_state_type', 'voice_state_log.state_type', 'voice_state_log.started_at')
Index('idx_presence_status_log_user_set', 'presence_status_log.user_id', 'presence_status_log.set_at')
Index('idx_presence_status_log_status_type', 'presence_status_log.status_type', 'presence_status_log.set_at')
Index('idx_presence_status_log_cleared', 'presence_status_log.user_id', 'presence_status_log.cleared_at')
Index('idx_activity_log_user_started', 'activity_log.user_id', 'activity_log.started_at')
Index('idx_custom_status_user_set', 'custom_status.user_id', 'custom_status.set_at')
Index('idx_user_names_current', 'user_names_history.user_id', 'user_names_history.effective_until')
Index('idx_user_names_effective_from', 'user_names_history.user_id', 'user_names_history.effective_from')
Index('idx_user_names_unique_current', 'user_names_history.user_id', unique=True,
      postgresql_where='effective_until IS NULL', mysql_length={'user_id': None})

CheckConstraint(
    "activity_type IN ('competing', 'custom', 'listening', 'playing', 'streaming', 'watching')",
    name='ck_activity_type_valid'
)


CheckConstraint(
    "message_type IN ('default', 'recipient_add', 'recipient_remove', 'call', "
    "'channel_name_change', 'channel_icon_change', 'channel_pinned_message', 'user_join', "
    "'guild_boost', 'guild_boost_tier_1', 'guild_boost_tier_2', 'guild_boost_tier_3', "
    "'channel_follow_add', 'guild_discovery_disqualified', 'guild_discovery_requalified', "
    "'guild_discovery_grace_period_initial_warning', 'guild_discovery_grace_period_final_warning', "
    "'thread_created', 'reply', 'chat_input_command', 'thread_starter_message', "
    "'guild_invite_reminder', 'context_menu_command', 'role_subscription_purchase', "
    "'interaction_premium_upsell', 'stage_start', 'stage_end', 'stage_speaker', "
    "'stage_raise_hand', 'stage_topic', 'guild_application_premium_subscription', "
    "'guild_incident_alert_mode_enabled', 'guild_incident_alert_mode_disabled', "
    "'guild_incident_report_raid', 'guild_incident_report_false_alarm', "
    "'purchase_notification', 'poll_result')",
    name='ck_message_type_valid'
)

CheckConstraint(
    "(effective_until IS NULL AND effective_from IS NOT NULL) OR "
    "(effective_until IS NOT NULL AND effective_until > effective_from)",
    name='ck_user_names_history_valid_period'
)

CheckConstraint(
    "status_type IN ('online', 'idle', 'dnd', 'offline', 'streaming')",
    name='ck_presence_status_enum_valid'
)

CheckConstraint(
    "state_type IN ('deaf', 'mute', 'self_deaf', 'self_mute', 'self_stream', 'self_video')",
    name='ck_voice_state_type_valid'
)

CheckConstraint(
    "(ended_at IS NULL) OR (ended_at >= started_at)",
    name='ck_voice_state_log_valid_period'
)

CheckConstraint(
    "(left_at IS NULL) OR (left_at >= joined_at)",
    name='ck_voice_session_valid_period'
)

CheckConstraint(
    "(ended_at IS NULL) OR (ended_at >= started_at)",
    name='ck_activity_log_valid_period'
)

CheckConstraint(
    "(cleared_at IS NULL) OR (cleared_at >= set_at)",
    name='ck_custom_status_valid_period'
)

CheckConstraint(
    "(changed_at IS NULL) OR (changed_at >= set_at)",
    name='ck_presence_status_valid_period'
)

Base = SQLModel.metadata
