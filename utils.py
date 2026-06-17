import aiohttp
import requests
from typing import Optional, List

class IPVerification:
    """IP verification utilities"""
    
    @staticmethod
    def get_user_ip_sync() -> str:
        """Get user's IP address (synchronous)"""
        try:
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            return response.json().get('ip', 'unknown')
        except:
            return 'unknown'


class ChannelVerification:
    """Channel verification utilities"""
    
    @staticmethod
    async def check_user_subscription(context, user_id: int, channel_username: str) -> bool:
        """Check if user is subscribed to a channel"""
        try:
            member = await context.bot.get_chat_member(channel_username, user_id)
            return member.status not in ['left', 'kicked']
        except Exception as e:
            print(f"Error checking subscription: {e}")
            return False

    @staticmethod
    async def verify_all_mandatory_channels(context, user_id: int, channels: List[str]) -> bool:
        """Verify user is subscribed to all mandatory channels"""
        for channel in channels:
            is_subscribed = await ChannelVerification.check_user_subscription(
                context, user_id, channel
            )
            if not is_subscribed:
                return False
        return True


class WalletUtils:
    """Wallet address validation"""
    
    @staticmethod
    def validate_bep20_address(address: str) -> bool:
        """Validate BSC/BEP20 wallet address"""
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        try:
            int(address, 16)
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_address(address: str) -> bool:
        """Validate wallet address format"""
        return WalletUtils.validate_bep20_address(address)


class Formatting:
    """Text formatting utilities"""
    
    @staticmethod
    def format_balance(amount: float) -> str:
        """Format balance with proper decimal places"""
        return f"{amount:.8f} USDT"

    @staticmethod
    def format_referral_link(link: str) -> str:
        """Format referral link for display"""
        return f"<code>{link}</code>"


class ErrorMessages:
    """Error and status messages"""
    
    USER_BANNED = "❌ Your account has been banned: {reason}"
    NOT_VERIFIED = "❌ Please complete verification first (IP + Mandatory Channels)"
    IP_DUPLICATE = "❌ Multiple accounts detected from the same IP. Your account has been banned."
    CHANNEL_NOT_SUBSCRIBED = "❌ You must be subscribed to all mandatory channels:\n{channels}"
    INVALID_WALLET = "❌ Invalid wallet address. Please provide a valid BSC/BEP20 address."
    INSUFFICIENT_BALANCE = "❌ Insufficient balance. Required: {required}, Available: {available}"
    WITHDRAWAL_MIN = "❌ Minimum withdrawal is {min_amount} USDT"
    INVALID_AMOUNT = "❌ Invalid amount. Please enter a positive number."
    
    IP_VERIFIED = "✅ IP address verified successfully"
    CHANNELS_VERIFIED = "✅ All mandatory channels verified"
    WITHDRAWAL_CREATED = "✅ Withdrawal request created. Transaction ID: {withdrawal_id}\nPlease wait up to 48 hours for processing."
    WITHDRAWAL_APPROVED = "✅ Your withdrawal has been approved!\nTransaction Hash: {tx_hash}\nAmount: {amount} USDT"
    WITHDRAWAL_REJECTED = "❌ Your withdrawal was rejected.\nReason: {reason}\nAmount {amount} USDT has been refunded to your wallet."
    REFERRAL_BONUS_ADDED = "🎉 New active referral!\n+{bonus} USDT bonus added to your account"