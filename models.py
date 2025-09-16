from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import BigInteger, DateTime


class User(SQLModel, table=True):
    """
    Represents a Discord user in the database for a single guild.

    Stores basic user information and serves as the primary reference
    for all user activity tracking within the monitored Discord server.

    Attributes:
        user_id: Discord user ID (snowflake) - primary key
        username: Current Discord username
        display_name: Current Discord display name (server nickname)
        global_name: Discord global display name
        first_seen: When the user first joined the Discord server (member since date)
        last_updated: When user information was last updated by the bot
    """
    __tablename__ = "users"

    user_id: int = Field(
        primary_key=True,
        sa_type=BigInteger,
        description="Discord user ID (snowflake)"
    )
    username: Optional[str] = Field(default=None, max_length=32, description="Current Discord username")
    display_name: Optional[str] = Field(default=None, max_length=32, description="Current Discord display name")
    global_name: Optional[str] = Field(default=None, max_length=32, description="Discord global display name")

    first_seen: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=datetime.utcnow,
        description="When the user first joined the Discord server (member since)"
    )
    last_updated: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=datetime.utcnow,
        description="When user info was last updated"
    )

    messages: List["MessageActivity"] = Relationship(back_populates="user")
    voice_sessions: List["VoiceActivity"] = Relationship(back_populates="user")
    presence_logs: List["PresenceActivity"] = Relationship(back_populates="user")


class MessageActivity(SQLModel, table=True):
    """
    Tracks when users send messages in channels within the monitored guild.

    Records every message sent by users for analysis of messaging patterns,
    activity levels, and communication statistics. Does not store message content
    for privacy, only metadata.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID who sent the message
        channel_id: Discord channel ID where message was sent
        message_id: Discord message ID (snowflake) - unique identifier
        message_type: Type of Discord message (default, reply, etc.)
        has_attachments: Whether the message contained file attachments
        has_embeds: Whether the message contained rich embeds
        character_count: Length of the message content in characters
        sent_at: Timestamp when the message was sent
    """
    __tablename__ = "message_activity"

    id: Optional[int] = Field(default=None, primary_key=True)
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
    message_id: int = Field(
        sa_type=BigInteger,
        unique=True,
        index=True,
        description="Discord message ID (snowflake)"
    )

    message_type: Optional[str] = Field(default="default", max_length=20, description="Type of message")
    has_attachments: bool = Field(default=False, description="Whether message had attachments")
    has_embeds: bool = Field(default=False, description="Whether message had embeds")
    character_count: Optional[int] = Field(default=None, description="Length of message content")

    sent_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        index=True,
        description="When the message was sent"
    )

    user: User = Relationship(back_populates="messages")


class VoiceActivity(SQLModel, table=True):
    """
    Tracks voice channel activity and session durations within the monitored guild.

    Records when users join/leave voice channels, calculates session durations,
    and captures voice states during sessions for detailed voice activity analysis.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID who joined/left voice
        channel_id: Discord voice channel ID
        joined_at: Timestamp when user joined the voice channel
        left_at: Timestamp when user left (NULL if still in channel)
        duration_seconds: Total session duration in seconds
        was_muted: Whether user was muted during the session
        was_deafened: Whether user was deafened during the session
        was_streaming: Whether user was streaming during the session
        was_video: Whether user had video enabled during the session
    """
    __tablename__ = "voice_activity"

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
    duration_seconds: Optional[int] = Field(
        default=None,
        description="Duration of voice session in seconds (calculated when user leaves)"
    )

    was_muted: bool = Field(default=False, description="Whether user was muted during session")
    was_deafened: bool = Field(default=False, description="Whether user was deafened during session")
    was_streaming: bool = Field(default=False, description="Whether user was streaming during session")
    was_video: bool = Field(default=False, description="Whether user had video enabled during session")

    user: User = Relationship(back_populates="voice_sessions")


class PresenceActivity(SQLModel, table=True):
    """
    Tracks user presence status changes and activities within the monitored guild.

    Records when users change their presence status (online, offline, idle, dnd)
    and what activities they're engaged in, enabling analysis of online patterns
    and user behavior trends.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID whose presence changed
        status: Current user status (online, offline, idle, dnd)
        previous_status: Previous status before this change
        activity_type: Type of activity (playing, streaming, listening, watching, custom)
        activity_name: Name/description of the current activity
        changed_at: Timestamp when the presence status changed
        duration_seconds: Duration of the previous status in seconds
    """
    __tablename__ = "presence_activity"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )

    status: str = Field(
        max_length=20,
        description="User status (online, offline, idle, dnd)"
    )
    previous_status: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Previous status before this change"
    )

    activity_type: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Type of activity (playing, streaming, listening, watching, custom)"
    )
    activity_name: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Name of the activity"
    )

    changed_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        index=True,
        description="When the presence status changed"
    )
    duration_seconds: Optional[int] = Field(
        default=None,
        description="Duration of previous status in seconds (calculated when status changes)"
    )

    user: User = Relationship(back_populates="presence_logs")


class UserNameHistory(SQLModel, table=True):
    """
    Tracks username and display name changes over time within the monitored guild.

    Maintains a complete audit trail of all username, display name, and global name
    changes, enabling historical analysis of user identity changes and nickname patterns.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Discord user ID whose name changed
        old_username: Previous username value
        new_username: New username value
        old_display_name: Previous display name (server nickname)
        new_display_name: New display name (server nickname)
        old_global_name: Previous global display name
        new_global_name: New global display name
        change_type: Type of change (username, display_name, global_name)
        changed_at: Timestamp when the name change occurred
    """
    __tablename__ = "user_name_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )

    old_username: Optional[str] = Field(default=None, max_length=32, description="Previous username")
    new_username: Optional[str] = Field(default=None, max_length=32, description="New username")
    old_display_name: Optional[str] = Field(default=None, max_length=32, description="Previous display name")
    new_display_name: Optional[str] = Field(default=None, max_length=32, description="New display name")
    old_global_name: Optional[str] = Field(default=None, max_length=32, description="Previous global name")
    new_global_name: Optional[str] = Field(default=None, max_length=32, description="New global name")

    change_type: str = Field(
        max_length=20,
        description="Type of change: username, display_name, global_name"
    )

    changed_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=datetime.utcnow,
        index=True,
        description="When the name change occurred"
    )


Base = SQLModel.metadata
