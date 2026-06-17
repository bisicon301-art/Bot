from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TelegramError
from database import Database
from utils import *
import logging

logger = logging.getLogger(__name__)

ADMIN_CHANNEL_NAME = 1
ADMIN_CHANNEL_USERNAME = 2
ADMIN_BONUS_AMOUNT = 3
ADMIN_MIN_WITHDRAWAL = 4
ADMIN_BROADCAST_MESSAGE = 5
ADMIN_WITHDRAWAL_ACTION = 6

class AdminHandlers:
    def __init__(self, db: Database, admin_id: int):
        self.db = db
        self.admin_id = admin_id

    async def check_admin(self, user_id: int) -> bool:
        return user_id == self.admin_id

    async def adminpanel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not await self.check_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        message = "🔐 <b>Admin Panel</b>\n\nSelect an option:"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 Manage Channels", callback_data="admin_channels")],
            [InlineKeyboardButton("💎 Set Referral Bonus", callback_data="admin_bonus")],
            [InlineKeyboardButton("💵 Set Min Withdrawal", callback_data="admin_min_withdrawal")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⏳ Pending Withdrawals", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📊 Performance Stats", callback_data="admin_performance")]
        ])
        
        await update.message.reply_text(message, reply_markup=keyboard, parse_mode='HTML')

    async def admin_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        channels = await self.db.get_mandatory_channels()
        
        message = "📺 <b>Mandatory Channels</b>\n\n"
        if channels:
            message += "<b>Current channels:</b>\n"
            for i, ch in enumerate(channels, 1):
                message += f"{i}. {ch['channel_username']}\n"
        else:
            message += "No channels configured yet.\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Channel", callback_data="admin_add_channel")],
            [InlineKeyboardButton("➖ Remove Channel", callback_data="admin_remove_channel")],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]
        ])
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    async def admin_add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("📝 Enter the channel name (display name):\n\nExample: News Channel")
        return ADMIN_CHANNEL_NAME

    async def handle_channel_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        channel_name = update.message.text.strip()
        context.user_data['channel_name'] = channel_name
        await update.message.reply_text("📝 Enter the channel username (must start with @):\n\nExample: @mychannel")
        return ADMIN_CHANNEL_USERNAME

    async def handle_channel_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        channel_username = update.message.text.strip()
        
        if not channel_username.startswith('@'):
            await update.message.reply_text("❌ Username must start with @")
            return ADMIN_CHANNEL_USERNAME
        
        channel_name = context.user_data.get('channel_name')
        await self.db.add_mandatory_channel(channel_name, channel_username)
        await update.message.reply_text(f"✅ Channel {channel_username} added successfully!")
        return ConversationHandler.END

    async def admin_remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        channels = await self.db.get_mandatory_channels()
        
        if not channels:
            await query.edit_message_text("ℹ️ No channels to remove.")
            return ConversationHandler.END
        
        keyboard = []
        for ch in channels:
            keyboard.append([InlineKeyboardButton(ch['channel_username'], callback_data=f"admin_remove_ch_{ch['channel_name']}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_channels")])
        
        await query.edit_message_text("❌ <b>Remove Channel</b>\n\nSelect a channel to remove:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def handle_remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        channel_name = query.data.split('_', 3)[3]
        await query.answer()
        await self.db.remove_mandatory_channel(channel_name)
        await query.edit_message_text(f"✅ Channel {channel_name} removed successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_channels")]]))

    async def admin_bonus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        settings = await self.db.get_admin_settings()
        current_bonus = float(settings.get('referral_bonus', 2.0))
        await query.edit_message_text(f"💎 <b>Set Referral Bonus</b>\n\nCurrent bonus: {Formatting.format_balance(current_bonus)}\n\nEnter new bonus amount (in USDT):", parse_mode='HTML')
        return ADMIN_BONUS_AMOUNT

    async def handle_bonus_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            bonus = float(update.message.text.strip())
            if bonus <= 0:
                await update.message.reply_text("❌ Bonus must be positive")
                return ADMIN_BONUS_AMOUNT
            await self.db.update_referral_bonus(bonus)
            await update.message.reply_text(f"✅ Referral bonus updated to {Formatting.format_balance(bonus)}")
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text("❌ Invalid amount")
            return ADMIN_BONUS_AMOUNT

    async def admin_min_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        settings = await self.db.get_admin_settings()
        current_min = float(settings.get('min_withdrawal', 10))
        await query.edit_message_text(f"💵 <b>Set Minimum Withdrawal</b>\n\nCurrent minimum: {Formatting.format_balance(current_min)}\n\nEnter new minimum amount (in USDT):", parse_mode='HTML')
        return ADMIN_MIN_WITHDRAWAL

    async def handle_min_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            min_amount = float(update.message.text.strip())
            if min_amount <= 0:
                await update.message.reply_text("❌ Amount must be positive")
                return ADMIN_MIN_WITHDRAWAL
            await self.db.update_min_withdrawal(min_amount)
            await update.message.reply_text(f"✅ Minimum withdrawal updated to {Formatting.format_balance(min_amount)}")
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text("❌ Invalid amount")
            return ADMIN_MIN_WITHDRAWAL

    async def admin_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("📢 <b>Broadcast Message</b>\n\nEnter the message to broadcast to all users:", parse_mode='HTML')
        return ADMIN_BROADCAST_MESSAGE

    async def handle_broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text
        async with self.db.pool.acquire() as conn:
            users = await conn.fetch("SELECT user_id FROM users WHERE is_banned = FALSE")
        
        success_count = 0
        for user_record in users:
            try:
                await context.bot.send_message(user_record['user_id'], f"📢 <b>Announcement</b>\n\n{message_text}", parse_mode='HTML')
                success_count += 1
            except TelegramError:
                pass
        
        await update.message.reply_text(f"✅ Broadcast completed!\n\n✅ Sent: {success_count}")
        return ConversationHandler.END

    async def admin_withdrawals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        withdrawals = await self.db.get_pending_withdrawals()
        
        if not withdrawals:
            await query.edit_message_text("✅ No pending withdrawals", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_withdrawals")],
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]
            ]))
            return
        
        keyboard = []
        for w in withdrawals:
            amount = float(w['amount'])
            button_text = f"ID: {w['withdrawal_id']} | {Formatting.format_balance(amount)}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_withdraw_{w['withdrawal_id']}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_back")])
        
        message = f"⏳ <b>Pending Withdrawals</b>\n\nTotal: {len(withdrawals)}\n\nClick on a withdrawal to approve or reject:"
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def admin_withdrawal_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        withdrawal_id = int(query.data.split('_')[3])
        await query.answer()
        
        withdrawal = await self.db.get_withdrawal(withdrawal_id)
        if not withdrawal:
            await query.answer("❌ Withdrawal not found", show_alert=True)
            return
        
        message = f"📋 <b>Withdrawal Details</b>\n\nID: <code>{withdrawal['withdrawal_id']}</code>\nUser: <code>{withdrawal['user_id']}</code>\nAmount: <code>{Formatting.format_balance(float(withdrawal['amount']))}</code>\nWallet: <code>{withdrawal['wallet_address']}</code>\nStatus: {withdrawal['status']}\nCreated: {withdrawal['created_at']}\n\nAction:"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{withdrawal_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{withdrawal_id}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_withdrawals")]
        ])
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    async def admin_approve_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        withdrawal_id = int(query.data.split('_')[2])
        await query.answer("Processing...")
        
        withdrawal = await self.db.get_withdrawal(withdrawal_id)
        await self.db.approve_withdrawal(withdrawal_id)
        
        try:
            user_message = f"✅ <b>Withdrawal Approved</b>\n\nAmount: {Formatting.format_balance(float(withdrawal['amount']))}\nWallet: <code>{withdrawal['wallet_address']}</code>\n\nProcessing will be completed within 48 hours."
            await context.bot.send_message(withdrawal['user_id'], user_message, parse_mode='HTML')
        except TelegramError:
            pass
        
        await query.edit_message_text("✅ Withdrawal approved!\n\nUser has been notified.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_withdrawals")]]))

    async def admin_reject_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        withdrawal_id = int(query.data.split('_')[2])
        context.user_data['rejection_withdrawal_id'] = withdrawal_id
        await query.answer()
        await query.edit_message_text("❌ <b>Reject Withdrawal</b>\n\nEnter reason for rejection:", parse_mode='HTML')
        return ADMIN_WITHDRAWAL_ACTION

    async def handle_rejection_reason(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        reason = update.message.text
        withdrawal_id = context.user_data.get('rejection_withdrawal_id')
        withdrawal = await self.db.get_withdrawal(withdrawal_id)
        
        await self.db.reject_withdrawal(withdrawal_id, reason)
        
        try:
            user_message = f"❌ <b>Withdrawal Rejected</b>\n\nAmount: {Formatting.format_balance(float(withdrawal['amount']))}\nReason: {reason}\n\n{Formatting.format_balance(float(withdrawal['amount']))} USDT has been refunded to your wallet."
            await context.bot.send_message(withdrawal['user_id'], user_message, parse_mode='HTML')
        except TelegramError:
            pass
        
        await update.message.reply_text("✅ Withdrawal rejected and balance refunded!")
        return ConversationHandler.END

    async def admin_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        stats = await self.db.get_performance_stats()
        
        message = "📊 <b>Performance Statistics</b>\n\n"
        message += f"👥 Total Users: {stats['total_users']}\n"
        message += f"🔗 Total Active Referrals: {stats['total_active_referrals']}\n"
        message += f"💸 Total Approved Withdrawals: {Formatting.format_balance(stats['total_approved_withdrawals'])}\n"
        message += f"⏳ Pending Withdrawals: {stats['pending_withdrawals']}\n"
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_performance")],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]
        ]), parse_mode='HTML')

    async def admin_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        message = "🔐 <b>Admin Panel</b>\n\nSelect an option:"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 Manage Channels", callback_data="admin_channels")],
            [InlineKeyboardButton("💎 Set Referral Bonus", callback_data="admin_bonus")],
            [InlineKeyboardButton("💵 Set Min Withdrawal", callback_data="admin_min_withdrawal")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⏳ Pending Withdrawals", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📊 Performance Stats", callback_data="admin_performance")]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')