from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import Database
from utils import *
import logging

logger = logging.getLogger(__name__)

WALLET_ADDRESS_STATE = 1
WITHDRAWAL_AMOUNT_STATE = 2

class UserHandlers:
    def __init__(self, db: Database):
        self.db = db

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat_id = update.effective_chat.id
        ip_address = IPVerification.get_user_ip_sync()
        
        db_user = await self.db.get_or_create_user(user.id, user.username, user.first_name, user.last_name, ip_address)
        
        if await self.db.is_user_banned(user.id):
            await context.bot.send_message(chat_id, f"❌ Your account has been banned: {db_user.get('ban_reason', 'Unknown reason')}")
            return
        
        if context.args and context.args[0].startswith('ref_'):
            try:
                referrer_id = int(context.args[0].split('_')[1])
                if referrer_id != user.id:
                    await self.db.add_referral(referrer_id, user.id)
            except:
                pass
        
        await self.show_main_menu(update, context, db_user)

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, db_user: dict):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        ip_verified = db_user.get('ip_verified', False)
        channels_verified = db_user.get('channels_verified', False)
        
        message = "🤖 <b>Referral Bot Menu</b>\n\n"
        
        if not ip_verified or not channels_verified:
            message += "⚠️ <b>Verification Required</b>\n"
            if not ip_verified:
                message += "• ❌ IP Verification\n"
            if not channels_verified:
                message += "• ❌ Channel Verification\n"
            message += "\nPlease complete verification to use all features.\n\n"
        else:
            message += "✅ <b>Verification Complete</b>\n\n"
        
        balance = await self.db.get_balance(user_id)
        message += f"💰 Balance: {Formatting.format_balance(balance)}\n\n"
        
        referral_stats = await self.db.get_user_referrals(user_id)
        message += f"🔗 Active Referrals: {referral_stats.get('active_referrals', 0)}\n"
        message += f"📊 Total Referrals: {referral_stats.get('total_referrals', 0)}\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Wallet", callback_data="menu_wallet"),
             InlineKeyboardButton("🔗 Referral", callback_data="menu_referral")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")]
        ])
        
        await context.bot.send_message(chat_id, message, reply_markup=keyboard, parse_mode='HTML')

    async def menu_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer()
        
        balance = await self.db.get_balance(user_id)
        message = f"💰 <b>Wallet</b>\n\n"
        message += f"Balance: {Formatting.format_balance(balance)}\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Withdraw", callback_data="wallet_withdraw")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="menu_wallet"),
             InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
        ])
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    async def wallet_withdraw(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        chat_id = query.message.chat_id
        
        await query.answer()
        
        settings = await self.db.get_admin_settings()
        min_withdrawal = float(settings.get('min_withdrawal', 10))
        balance = await self.db.get_balance(user_id)
        
        if balance < min_withdrawal:
            await context.bot.send_message(
                chat_id,
                f"❌ Insufficient balance.\nCurrent balance: {Formatting.format_balance(balance)}\nMinimum withdrawal: {Formatting.format_balance(min_withdrawal)}"
            )
            return ConversationHandler.END
        
        message = f"💳 <b>Withdrawal</b>\n\nAvailable balance: {Formatting.format_balance(balance)}\nMinimum withdrawal: {Formatting.format_balance(min_withdrawal)}\n\nEnter the amount you want to withdraw (in USDT):"
        await context.bot.send_message(chat_id, message, parse_mode='HTML')
        return WITHDRAWAL_AMOUNT_STATE

    async def handle_withdrawal_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        try:
            amount = float(update.message.text)
            
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be positive")
                return WITHDRAWAL_AMOUNT_STATE
            
            balance = await self.db.get_balance(user_id)
            if amount > balance:
                await update.message.reply_text(f"❌ Insufficient balance.\nAvailable: {Formatting.format_balance(balance)}")
                return WITHDRAWAL_AMOUNT_STATE
            
            settings = await self.db.get_admin_settings()
            min_withdrawal = float(settings.get('min_withdrawal', 10))
            if amount < min_withdrawal:
                await update.message.reply_text(f"❌ Minimum withdrawal: {Formatting.format_balance(min_withdrawal)}")
                return WITHDRAWAL_AMOUNT_STATE
            
            context.user_data['withdrawal_amount'] = amount
            await update.message.reply_text("💼 Enter your BSC/BEP20 wallet address (e.g., 0x...):")
            return WALLET_ADDRESS_STATE
            
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return WITHDRAWAL_AMOUNT_STATE

    async def handle_wallet_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        wallet_address = update.message.text.strip()
        
        if not WalletUtils.validate_address(wallet_address):
            await update.message.reply_text("❌ Invalid wallet address format.\nPlease provide a valid BSC/BEP20 address (0x...)")
            return WALLET_ADDRESS_STATE
        
        amount = context.user_data.get('withdrawal_amount')
        success = await self.db.subtract_balance(user_id, amount)
        
        if not success:
            await update.message.reply_text("❌ Error processing withdrawal. Please try again.")
            return ConversationHandler.END
        
        withdrawal_id = await self.db.create_withdrawal(user_id, amount, wallet_address)
        
        message = f"✅ <b>Withdrawal Request Created</b>\n\nID: <code>{withdrawal_id}</code>\nAmount: {Formatting.format_balance(amount)}\nWallet: <code>{wallet_address}</code>\n\nYour request will be processed within 48 hours.\nYou will receive a notification when approved or rejected."
        await update.message.reply_text(message, parse_mode='HTML')
        
        return ConversationHandler.END

    async def menu_referral(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer()
        
        referral_link = await self.db.get_referral_link(user_id)
        stats = await self.db.get_user_referrals(user_id)
        
        message = f"🔗 <b>Referral Link</b>\n\nShare your link:\n{Formatting.format_referral_link(referral_link)}\n\n📊 <b>Statistics</b>\nTotal Referrals: {stats.get('total_referrals', 0)}\nActive Referrals: {stats.get('active_referrals', 0)}\nTotal Earned: {Formatting.format_balance(float(stats.get('total_earned', 0)))}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy Link", callback_data="referral_copy_link")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="menu_referral"),
             InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
        ])
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    async def referral_copy_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer("Link copied! Share it to earn bonuses.", show_alert=False)

    async def menu_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer()
        
        db_user = await self.db.get_user(user_id)
        
        message = "⚙️ <b>Settings</b>\n\n<b>Verification Status:</b>\n"
        message += f"• IP Verification: {'✅' if db_user.get('ip_verified') else '❌'}\n"
        message += f"• Channel Verification: {'✅' if db_user.get('channels_verified') else '❌'}\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Verify IP", callback_data="verify_ip")],
            [InlineKeyboardButton("📺 Verify Channels", callback_data="verify_channels")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
        ])
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    async def verify_ip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer()
        
        ip_address = IPVerification.get_user_ip_sync()
        success = await self.db.verify_user_ip(user_id, ip_address)
        
        if success:
            await query.edit_message_text("✅ IP verified successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_settings")]]))
        else:
            await query.edit_message_text("❌ IP verification failed - duplicate IP detected.\nYour account has been banned.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_settings")]]))

    async def verify_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer()
        
        channels = await self.db.get_mandatory_channels()
        
        if not channels:
            await query.edit_message_text("ℹ️ No mandatory channels configured yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_settings")]]))
            return
        
        all_subscribed = await ChannelVerification.verify_all_mandatory_channels(context, user_id, [ch['channel_name'] for ch in channels])
        channel_list = "\n".join([f"• {ch['channel_username']}" for ch in channels])
        
        if all_subscribed:
            await self.db.mark_channels_verified(user_id)
            message = "✅ All mandatory channels verified!\n\n<b>Subscribed channels:</b>\n" + channel_list
        else:
            message = "❌ Please subscribe to all mandatory channels:\n\n" + channel_list
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Retry", callback_data="verify_channels")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_settings")]
        ]), parse_mode='HTML')

    async def menu_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.answer()
        db_user = await self.db.get_user(user_id)
        await self.show_main_menu(update, context, db_user)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END