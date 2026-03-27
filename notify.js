const TelegramBot = require('node-telegram-bot-api');
const token = process.env.TELEGRAM_TOKEN;
let chatId = process.env.TELEGRAM_CHAT_ID; // может быть пустым
const CHAT_LIST_SECRET = process.env.TELEGRAM_CHAT_LIST; // опционально: CSV или JSON списка

if (!token) {
  console.error('TELEGRAM_TOKEN not set');
  process.exit(1);
}

const bot = new TelegramBot(token, { polling: false });

// Если задан список в секретах (CSV: "id1,id2" или JSON: '["id1","id2"]'), используем его
let targets = [];
if (CHAT_LIST_SECRET) {
  try {
    targets = CHAT_LIST_SECRET.trim().startsWith('[')
      ? JSON.parse(CHAT_LIST_SECRET)
      : CHAT_LIST_SECRET.split(',').map(s => s.trim()).filter(Boolean);
  } catch (e) {
    console.error('Invalid TELEGRAM_CHAT_LIST format');
    process.exit(1);
  }
}

// Если TELEGRAM_CHAT_ID задан — добавляем в targets
if (chatId) targets.push(chatId);

// Если нет ни одного target — ошибка с подсказкой
if (targets.length === 0) {
  console.error('No chat IDs provided. Set TELEGRAM_CHAT_ID or TELEGRAM_CHAT_LIST secret.');
  console.error('To send to a channel, use its @username (as a string) or channel id (-100...)');
  process.exit(1);
}

(async () => {
  try {
    const text = `Авто-уведомление: ${new Date().toUTCString()}`;
    for (const id of targets) {
      // подсказка: для каналов используйте "@channelusername" или "-1001234567890"
      await bot.sendMessage(id, text, { parse_mode: 'HTML' });
      console.log('Sent to', id);
    }
    process.exit(0);
  } catch (err) {
    console.error('Send failed:', err);
    process.exit(1);
  }
})();
