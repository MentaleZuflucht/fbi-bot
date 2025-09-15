from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import BigInteger, DateTime


class User(SQLModel, table=True):
    """
    Represents a Discord user in the database.

    This table stores basic user information and serves as the primary
    reference for all user activity tracking.
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
        description="When this user was first recorded"
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
    Tracks when users send messages in channels.

    This table records every message sent by users, allowing for
    analysis of messaging patterns and activity levels.
    """
    __tablename__ = "message_activity"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID who sent the message"
    )
    guild_id: int = Field(
        sa_type=BigInteger,
        index=True,
        description="Discord guild (server) ID where message was sent"
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
    Tracks when users join/leave voice channels and their session duration.

    This table records voice channel activity including join times,
    leave times, and calculated session durations.
    """
    __tablename__ = "voice_activity"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )
    guild_id: int = Field(
        sa_type=BigInteger,
        index=True,
        description="Discord guild (server) ID"
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
    Tracks user presence status changes (online, offline, away, dnd).

    This table records when users change their presence status,
    allowing for analysis of online patterns and activity times.
    """
    __tablename__ = "presence_activity"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id",
        sa_type=BigInteger,
        index=True,
        description="Discord user ID"
    )
    guild_id: int = Field(
        sa_type=BigInteger,
        index=True,
        description="Discord guild (server) ID where presence was observed"
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
    Tracks username and display name changes over time.

    This table maintains a complete history of all username/display name
    changes, allowing you to see what a user was called at any point in time.
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

    guild_id: Optional[int] = Field(
        sa_type=BigInteger,
        default=None,
        description="Guild ID if this was a server nickname change"
    )


Base = SQLModel.metadata
