# FBI Bot 🕵️

A comprehensive Discord surveillance bot that monitors and tracks all user activity within your Discord server for analytics and insights.

## What It Does

This bot silently monitors your Discord server and collects detailed analytics on:

- **👥 User Activity**: Join dates, member statistics, and user information
- **💬 Message Tracking**: Message counts, activity patterns, and communication stats (content not stored)
- **🎤 Voice Activity**: Voice channel usage, session durations, and participation metrics  
- **🟢 Presence Monitoring**: Status changes, activity tracking, and online patterns
- **📝 Name History**: Complete audit trail of username and nickname changes

## Data Collected

### User Information
- Discord user IDs, usernames, display names
- Server join dates ("member since" data)
- Username/nickname change history

### Activity Metrics  
- Message frequency and timing patterns
- Voice channel join/leave events and session durations
- Presence status changes (online, away, DND, offline)
- Current activities (games, streaming, custom status)

## Installation

1. Set up your environment variables in `.env` file:
   ```
   TOKEN=your_discord_bot_token
   DATABASE_URL=your_database_connection_string
   ```

2. Run the bot:
   ```bash
   run.bat
   ```

## Bot Setup Requirements

### Required Discord Intents
The bot requires **all 3 privileged intents** to be enabled in the Discord Developer Portal:
- **Presence Intent** - To monitor user status and activity changes
- **Server Members Intent** - To track member joins/leaves and user information  
- **Message Content Intent** - To analyze message patterns and activity

### Required Bot Permissions
When inviting the bot to your server, ensure it has these permissions:
- **Connect** - To join voice channels and monitor voice activity
- **Read Message History** - To access historical messages for analysis
- **View Channels** - To see all channels and monitor activity across the server

## Requirements

- Discord bot with proper permissions and intents enabled (see above)
- PostgreSQL database
- Python 3.12+
