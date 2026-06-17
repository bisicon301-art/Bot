import asyncpg
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool = None

    async def connect(self):
        """Connect to PostgreSQL database"""
        self.pool = await asyncpg.create_pool(self.dsn, min_size=5, max_size=20)
        await self.init_tables()

    async def disconnect(self):
        """Disconnect from database"""
        if self.pool:
            await self.pool.close()

    async def init_tables(self):
        """Initialize database tables"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance DECIMAL(18, 8) DEFAULT 0,
                    ip_address TEXT,
                    ip_verified BOOLEAN DEFAULT FALSE,
                    channels_verified BOOLEAN DEFAULT FALSE,
                    total_referrals INT DEFAULT 0,
                    active_referrals INT DEFAULT 0,
                    total_earned DECIMAL(18, 8) DEFAULT 0,
                    is_banned BOOLEAN DEFAULT FALSE,
                    ban_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    referral_id SERIAL PRIMARY KEY,
                    referrer_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    referred_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    is_active BOOLEAN DEFAULT FALSE,
                    earned DECIMAL(18, 8) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    activated_at TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    withdrawal_id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    amount DECIMAL(18, 8) NOT NULL,
                    wallet_address TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    transaction_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    admin_notes TEXT
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS mandatory_channels (
                    channel_id SERIAL PRIMARY KEY,
                    channel_name TEXT UNIQUE NOT NULL,
                    channel_username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ip_logs (
                    log_id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    ip_address TEXT NOT NULL,
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_settings (
                    setting_id SERIAL PRIMARY KEY,
                    min_withdrawal DECIMAL(18, 8) DEFAULT 10,
                    referral_bonus DECIMAL(18, 8) DEFAULT 2.0,
                    payment_timeout_hours INT DEFAULT 48,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                INSERT INTO admin_settings DEFAULT VALUES
                ON CONFLICT DO NOTHING
            """)

    async def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None, ip_address: str = None) -> Dict[str, Any]:
        """Get or create a user"""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            
            if user:
                if ip_address:
                    await conn.execute("INSERT INTO ip_logs (user_id, ip_address) VALUES ($1, $2)", user_id, ip_address)
                await conn.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = $1", user_id)
                return dict(user)
            
            new_user = await conn.fetchrow("""INSERT INTO users (user_id, username, first_name, last_name, ip_address) VALUES ($1, $2, $3, $4, $5) RETURNING *""", user_id, username, first_name, last_name, ip_address)
            
            if ip_address:
                await conn.execute("INSERT INTO ip_logs (user_id, ip_address) VALUES ($1, $2)", user_id, ip_address)
            
            return dict(new_user)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            return dict(user) if user else None

    async def ban_user(self, user_id: int, reason: str = "IP verification failed"):
        """Ban a user"""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET is_banned = TRUE, ban_reason = $1 WHERE user_id = $2", reason, user_id)

    async def is_user_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        user = await self.get_user(user_id)
        return user.get('is_banned', False) if user else False

    async def verify_user_ip(self, user_id: int, ip_address: str) -> bool:
        """Verify user IP - ban if duplicate"""
        async with self.pool.acquire() as conn:
            other_users = await conn.fetch("""SELECT DISTINCT user_id FROM ip_logs WHERE ip_address = $1 AND user_id != $2""", ip_address, user_id)
            
            if other_users:
                for record in other_users:
                    await conn.execute("UPDATE users SET is_banned = TRUE, ban_reason = 'Multiple accounts detected from same IP' WHERE user_id = $1", record['user_id'])
                await conn.execute("UPDATE users SET is_banned = TRUE, ban_reason = 'Multiple accounts detected from same IP' WHERE user_id = $1", user_id)
                return False
            
            await conn.execute("UPDATE users SET ip_verified = TRUE WHERE user_id = $1", user_id)
            return True

    async def get_user_ips(self, user_id: int) -> List[str]:
        """Get all IPs used by a user"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch("SELECT DISTINCT ip_address FROM ip_logs WHERE user_id = $1", user_id)
            return [record['ip_address'] for record in records]

    async def add_mandatory_channel(self, channel_name: str, channel_username: str):
        """Add mandatory channel"""
        async with self.pool.acquire() as conn:
            await conn.execute("""INSERT INTO mandatory_channels (channel_name, channel_username) VALUES ($1, $2) ON CONFLICT (channel_name) DO NOTHING""", channel_name, channel_username)

    async def remove_mandatory_channel(self, channel_name: str):
        """Remove mandatory channel"""
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM mandatory_channels WHERE channel_name = $1", channel_name)

    async def get_mandatory_channels(self) -> List[Dict[str, str]]:
        """Get all mandatory channels"""
        async with self.pool.acquire() as conn:
            channels = await conn.fetch("SELECT channel_name, channel_username FROM mandatory_channels ORDER BY created_at")
            return [dict(ch) for ch in channels]

    async def mark_channels_verified(self, user_id: int):
        """Mark user as verified all channels"""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET channels_verified = TRUE WHERE user_id = $1", user_id)

    async def add_referral(self, referrer_id: int, referred_id: int) -> bool:
        """Add a referral link"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES ($1, $2)", referrer_id, referred_id)
                await conn.execute("UPDATE users SET total_referrals = total_referrals + 1 WHERE user_id = $1", referrer_id)
                return True
            except:
                return False

    async def activate_referral(self, referrer_id: int, referred_id: int, bonus: float):
        """Activate referral and award bonus"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""UPDATE referrals SET is_active = TRUE, earned = $1, activated_at = CURRENT_TIMESTAMP WHERE referrer_id = $2 AND referred_id = $3""", bonus, referrer_id, referred_id)
                await conn.execute("""UPDATE users SET balance = balance + $1, active_referrals = active_referrals + 1, total_earned = total_earned + $1 WHERE user_id = $2""", bonus, referrer_id)

    async def get_user_referrals(self, user_id: int) -> Dict[str, Any]:
        """Get user's referral statistics"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("SELECT total_referrals, active_referrals, total_earned FROM users WHERE user_id = $1", user_id)
            return dict(stats) if stats else {}

    async def get_referral_link(self, user_id: int) -> str:
        """Generate referral link"""
        return f"https://t.me/referral_earn_usdt_bot?start=ref_{user_id}"

    async def get_balance(self, user_id: int) -> float:
        """Get user balance"""
        user = await self.get_user(user_id)
        return float(user['balance']) if user else 0

    async def add_balance(self, user_id: int, amount: float):
        """Add balance to user"""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)

    async def subtract_balance(self, user_id: int, amount: float) -> bool:
        """Subtract balance from user"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("UPDATE users SET balance = balance - $1 WHERE user_id = $2 AND balance >= $1", amount, user_id)
            return "1" in result

    async def create_withdrawal(self, user_id: int, amount: float, wallet_address: str) -> int:
        """Create withdrawal request"""
        async with self.pool.acquire() as conn:
            withdrawal = await conn.fetchrow("INSERT INTO withdrawals (user_id, amount, wallet_address) VALUES ($1, $2, $3) RETURNING withdrawal_id", user_id, amount, wallet_address)
            return withdrawal['withdrawal_id']

    async def get_pending_withdrawals(self) -> List[Dict[str, Any]]:
        """Get all pending withdrawals"""
        async with self.pool.acquire() as conn:
            withdrawals = await conn.fetch("SELECT w.*, u.username, u.first_name FROM withdrawals w JOIN users u ON w.user_id = u.user_id WHERE w.status = 'pending' ORDER BY w.created_at")
            return [dict(w) for w in withdrawals]

    async def approve_withdrawal(self, withdrawal_id: int, transaction_hash: str = None):
        """Approve withdrawal"""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE withdrawals SET status = 'approved', transaction_hash = $1, processed_at = CURRENT_TIMESTAMP WHERE withdrawal_id = $2", transaction_hash, withdrawal_id)

    async def reject_withdrawal(self, withdrawal_id: int, notes: str = None):
        """Reject withdrawal and refund"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                withdrawal = await conn.fetchrow("SELECT * FROM withdrawals WHERE withdrawal_id = $1", withdrawal_id)
                if withdrawal:
                    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", withdrawal['amount'], withdrawal['user_id'])
                    await conn.execute("UPDATE withdrawals SET status = 'rejected', admin_notes = $1, processed_at = CURRENT_TIMESTAMP WHERE withdrawal_id = $2", notes, withdrawal_id)

    async def get_withdrawal(self, withdrawal_id: int) -> Optional[Dict[str, Any]]:
        """Get withdrawal details"""
        async with self.pool.acquire() as conn:
            withdrawal = await conn.fetchrow("SELECT * FROM withdrawals WHERE withdrawal_id = $1", withdrawal_id)
            return dict(withdrawal) if withdrawal else None

    async def get_admin_settings(self) -> Dict[str, Any]:
        """Get admin settings"""
        async with self.pool.acquire() as conn:
            settings = await conn.fetchrow("SELECT * FROM admin_settings LIMIT 1")
            return dict(settings) if settings else {}

    async def update_min_withdrawal(self, amount: float):
        """Update minimum withdrawal"""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET min_withdrawal = $1, updated_at = CURRENT_TIMESTAMP", amount)

    async def update_referral_bonus(self, bonus: float):
        """Update referral bonus"""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET referral_bonus = $1, updated_at = CURRENT_TIMESTAMP", bonus)

    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        async with self.pool.acquire() as conn:
            stats = {}
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned = FALSE")
            stats['total_users'] = total_users
            total_active_referrals = await conn.fetchval("SELECT COALESCE(SUM(active_referrals), 0) FROM users")
            stats['total_active_referrals'] = int(total_active_referrals)
            total_withdrawals = await conn.fetchval("SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE status = 'approved'")
            stats['total_approved_withdrawals'] = float(total_withdrawals)
            pending_count = await conn.fetchval("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
            stats['pending_withdrawals'] = pending_count
            return stats