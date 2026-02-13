from flask import Flask, request
from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, CommandHandler, MessageHandler, filters

app = Flask(__name__)
TOKEN = 'ZALO_BOT_TOKEN'
bot = Bot(token=TOKEN)

async def start(update: Update, context):
    await update.message.reply_text(f"Xin chào {update.effective_user.display_name}!")

async def echo(update: Update, context):
    await update.message.reply_text(f"Bạn vừa nói: {update.message.text}")

with app.app_context():
    webhook_url = 'your_webhook_url'
    bot.set_webhook(url=webhook_url, secret_token='your_secret_token_here')

    dispatcher = Dispatcher(bot, None, workers=0)
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True)['result'], bot)
    dispatcher.process_update(update)
    return 'ok'

if __name__ == '__main__':
    app.run(port=8443)