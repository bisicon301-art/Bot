# Telegram Referral Bot with IP Verification

A powerful Telegram bot for managing referral programs with built-in IP verification, mandatory channel validation, withdrawal system, and admin panel.

## Features

### User Features
- ✅ **IP Verification System**: Automatically detects and bans accounts using the same IP (preventing fake referrals)
- ✅ **Mandatory Channel Verification**: Users must join specific channels to use the bot
- ✅ **Wallet Management**: Check balance and withdraw USDT via BEP20 network
- ✅ **Referral System**: Generate referral links and earn bonuses when referrals complete verification
- ✅ **Real-time Notifications**: Users are notified about withdrawal approvals/rejections and new referral bonuses

### Admin Features
- 🔐 **Admin Panel** (`/adminpanel` command)
- 📺 **Channel Management**: Add/remove mandatory channels
- 💎 **Bonus Settings**: Adjust referral bonus amount
- 💵 **Withdrawal Settings**: Set minimum withdrawal amount
- 📢 **Broadcast**: Send messages to all users
- ⏳ **Withdrawal Management**: Approve or reject withdrawal requests with notes
- 📊 **Performance Statistics**: View user count, active referrals, and withdrawal data

## Technology Stack

- **Python 3.11+**
- **python-telegram-bot 20.3**: Telegram bot API
- **PostgreSQL**: Database (Neon.com)
- **asyncpg**: Async PostgreSQL driver
- **Docker**: Containerization for Railway deployment

## Deployment on Railway.com

### Prerequisites
1. Railway.com account
2. Telegram Bot Token (from @BotFather)
3. Admin User ID
4. Neon.com PostgreSQL database

### Setup Steps

1. **Create PostgreSQL Database on Neon.com**
   - Sign up at neon.tech
   - Create a new project
   - Copy the connection string (DATABASE_URL)

2. **Deploy to Railway**
   - Connect your GitHub repository to Railway.com
   - Add environment variables:
     ```
     ADMIN_ID=7503462902
     BOT_TOKEN=8962945474:AAHIAdRlPPM5p-yR26my3fn0ISTc9833FDs
     DATABASE_URL=postgresql://user:password@host/dbname
     ```
   - Railway will automatically deploy using the Dockerfile

### Environment Variables

```env
ADMIN_ID=7503462902
BOT_TOKEN=8962945474:AAHIAdRlPPM5p-yR26my3fn0ISTc9833FDs
DATABASE_URL=postgresql://user:password@neon.tech/dbname
MIN_WITHDRAWAL=10
REFERRAL_BONUS=2.0
```

## Bot Commands

### User Commands
- `/start` - Start the bot and show main menu

### Admin Commands
- `/adminpanel` - Open admin control panel

## Database Schema

- **users**: User profiles with balances and verification status
- **referrals**: Referral relationships and earnings tracking
- **withdrawals**: Withdrawal requests with status tracking
- **mandatory_channels**: List of required channels
- **ip_logs**: IP address history for fraud detection
- **admin_settings**: Bot configuration

## IP Verification System

The bot automatically detects when multiple accounts use the same IP address and bans both accounts to prevent fake referral farming.

## Withdrawal Flow

1. User requests withdrawal
2. User enters USDT amount and wallet address
3. Admin reviews and approves/rejects
4. User is notified
5. Payment processed within 48 hours

Version: 1.0.0