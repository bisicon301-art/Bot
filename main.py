#!/usr/bin/env python3
import os, logging, asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from database import Database
from handlers import UserHandlers, WALLET_ADDRESS_STATE, WITHDRAWAL_AMOUNT_STATE
from admin_handlers import AdminHandlers, ADMIN_CHANNEL_NAME, ADMIN_CHANNEL_USERNAME, ADMIN_BONUS_AMOUNT, ADMIN_MIN_WITHDRAWAL, ADMIN_BROADCAST_MESSAGE, ADMIN_WITHDRAWAL_ACTION

load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_ID = int(os.getenv('ADMIN_ID', '7503462902'))
BOT_TOKEN = os.getenv('BOT_TOKEN', '8962945474:AAHIAdRlPPM5p-yR26my3fn0ISTc9833FDs')
DATABASE_URL = os.getenv('DATABASE_URL', '')

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not set")
    raise ValueError("DATABASE_URL must be set")

async def main():
    db = Database(DATABASE_URL)
    await db.connect()
    
    app = Application.builder().token(BOT_TOKEN).build()
    user_handlers = UserHandlers(db)
    admin_handlers = AdminHandlers(db, ADMIN_ID)
    
    app.add_handler(CommandHandler("start", user_handlers.start, filters.ALL))
    app.add_handler(CommandHandler("adminpanel", admin_handlers.adminpanel))
    
    app.add_handler(CallbackQueryHandler(user_handlers.menu_wallet, pattern="^menu_wallet$"))
    app.add_handler(CallbackQueryHandler(user_handlers.menu_referral, pattern="^menu_referral$"))
    app.add_handler(CallbackQueryHandler(user_handlers.menu_settings, pattern="^menu_settings$"))
    app.add_handler(CallbackQueryHandler(user_handlers.menu_main, pattern="^menu_main$"))
    app.add_handler(CallbackQueryHandler(user_handlers.wallet_withdraw, pattern="^wallet_withdraw$"))
    app.add_handler(CallbackQueryHandler(user_handlers.referral_copy_link, pattern="^referral_copy_link$"))
    app.add_handler(CallbackQueryHandler(user_handlers.verify_ip, pattern="^verify_ip$"))
    app.add_handler(CallbackQueryHandler(user_handlers.verify_channels, pattern="^verify_channels$"))
    
    withdrawal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_handlers.wallet_withdraw, pattern="^wallet_withdraw$")],
        states={
            WITHDRAWAL_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.handle_withdrawal_amount)],
            WALLET_ADDRESS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.handle_wallet_address)]
        },
        fallbacks=[CommandHandler("cancel", user_handlers.cancel)]
    )
    app.add_handler(withdrawal_conv)
    
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_channels, pattern="^admin_channels$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_add_channel, pattern="^admin_add_channel$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_remove_channel, pattern="^admin_remove_channel$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.handle_remove_channel, pattern="^admin_remove_ch_"))
    
    channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_handlers.admin_add_channel, pattern="^admin_add_channel$")],
        states={
            ADMIN_CHANNEL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.handle_channel_name)],
            ADMIN_CHANNEL_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.handle_channel_username)]
        },
        fallbacks=[CommandHandler("cancel", user_handlers.cancel)]
    )
    app.add_handler(channel_conv)
    
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_bonus, pattern="^admin_bonus$"))
    bonus_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_handlers.admin_bonus, pattern="^admin_bonus$")],
        states={ADMIN_BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.handle_bonus_amount)]},
        fallbacks=[CommandHandler("cancel", user_handlers.cancel)]
    )
    app.add_handler(bonus_conv)
    
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_min_withdrawal, pattern="^admin_min_withdrawal$"))
    min_withdrawal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_handlers.admin_min_withdrawal, pattern="^admin_min_withdrawal$")],
        states={ADMIN_MIN_WITHDRAWAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.handle_min_withdrawal)]},
        fallbacks=[CommandHandler("cancel", user_handlers.cancel)]
    )
    app.add_handler(min_withdrawal_conv)
    
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_broadcast, pattern="^admin_broadcast$"))
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_handlers.admin_broadcast, pattern="^admin_broadcast$")],
        states={ADMIN_BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.handle_broadcast_message)]},
        fallbacks=[CommandHandler("cancel", user_handlers.cancel)]
    )
    app.add_handler(broadcast_conv)
    
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_withdrawals, pattern="^admin_withdrawals$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_withdrawal_details, pattern="^admin_withdraw_"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_approve_withdrawal, pattern="^admin_approve_"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_reject_withdrawal, pattern="^admin_reject_"))
    
    rejection_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_handlers.admin_reject_withdrawal, pattern="^admin_reject_")],
        states={ADMIN_WITHDRAWAL_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.handle_rejection_reason)]},
        fallbacks=[CommandHandler("cancel", user_handlers.cancel)]
    )
    app.add_handler(rejection_conv)
    
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_performance, pattern="^admin_performance$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_back, pattern="^admin_back$"))
    
    async def error_handler(update, context):
        logger.error(f"Exception: {context.error}")
    
    app.add_error_handler(error_handler)
    logger.info("Bot started...")
    await app.run_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY])
    await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())