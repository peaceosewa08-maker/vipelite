import os
import json
import logging
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify
import requests

TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DATA_FILE = 'elite_users.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === STORAGE ===
class Storage:
    def __init__(self, filename=DATA_FILE):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_data(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Save error: {e}")

    def get_user(self, user_id):
        if user_id not in self.data:
            self.data[user_id] = {
                'user_id': user_id,
                'points': 0,
                'total_earned': 0,
                'elite_level': 0,
                'elite_points': 0,
                'daily_streak': 0,
                'last_daily': None,
                'last_elite_claim': None,
                'referrals': [],
                'username': '',
                'first_name': '',
                'last_name': '',
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat()
            }
            self._save_data()
        return self.data[user_id]

    def save_user(self, user_id, data):
        self.data[user_id] = data
        self._save_data()

    def get_all_users(self):
        return self.data

storage = Storage()

# === TELEGRAM API ===
def send_message(chat_id, text, parse_mode='Markdown'):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }, timeout=10)
        if response.status_code == 200:
            logger.info(f"Message sent to {chat_id}")
        return response.json()
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return None

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {'timeout': 30}
    if offset:
        params['offset'] = offset
    try:
        response = requests.get(url, params=params, timeout=35)
        if response.status_code == 200:
            return response.json().get('result', [])
        return []
    except Exception as e:
        logger.error(f"Get updates error: {e}")
        return []

def delete_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    try:
        response = requests.get(url, timeout=10)
        logger.info(f"Webhook deleted: {response.json()}")
        return response.json().get('ok', False)
    except Exception as e:
        logger.error(f"Delete webhook error: {e}")
        return False

# === ELITE TIERS ===
ELITE_LEVELS = {
    0: {
        'name': 'Member',
        'emoji': '🔰',
        'points_required': 0,
        'multiplier': 1.0,
        'benefits': ['Basic rewards', 'Standard claims']
    },
    1: {
        'name': 'Bronze Elite',
        'emoji': '🥉',
        'points_required': 100,
        'multiplier': 1.15,
        'benefits': ['15% bonus on daily rewards', 'Bronze badge', 'Basic elite rewards']
    },
    2: {
        'name': 'Silver Elite',
        'emoji': '🥈',
        'points_required': 500,
        'multiplier': 1.30,
        'benefits': ['30% bonus on daily rewards', 'Weekly elite bonus', 'Silver badge', 'Priority queue']
    },
    3: {
        'name': 'Gold Elite',
        'emoji': '🥇',
        'points_required': 1000,
        'multiplier': 1.50,
        'benefits': ['50% bonus on daily rewards', 'Exclusive drops', 'Gold badge', 'Elite support']
    },
    4: {
        'name': 'Platinum Elite',
        'emoji': '💎',
        'points_required': 5000,
        'multiplier': 1.75,
        'benefits': ['75% bonus on daily rewards', 'VIP rewards club', 'Platinum badge', '24/7 support']
    },
    5: {
        'name': 'Diamond Elite',
        'emoji': '👑',
        'points_required': 10000,
        'multiplier': 2.0,
        'benefits': ['100% bonus on daily rewards', 'Elite rewards', 'Diamond badge', 'Personal offers', 'Free claims']
    }
}

def get_elite_level(user):
    points = user.get('elite_points', 0)
    for level in range(5, -1, -1):
        if points >= ELITE_LEVELS[level]['points_required']:
            return level
    return 0

def get_elite_info(level):
    return ELITE_LEVELS.get(level, ELITE_LEVELS[0])

def get_streak_emoji(streak):
    if streak >= 100:
        return "👑"
    elif streak >= 50:
        return "💎"
    elif streak >= 30:
        return "🌟"
    elif streak >= 14:
        return "⭐"
    elif streak >= 7:
        return "🔥"
    return "💪"

def get_time_until(iso_time):
    if not iso_time:
        return "Available now!"
    try:
        last = datetime.fromisoformat(iso_time)
        next_time = last + timedelta(hours=24)
        now = datetime.now()
        if now >= next_time:
            return "Available now!"
        diff = next_time - now
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    except:
        return "Available now!"

def get_week_number():
    return datetime.now().strftime('%Y_%W')

# === COMMANDS ===
def handle_start(chat_id, user_data):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    user['username'] = user_data.get('username', '')
    user['first_name'] = user_data.get('first_name', 'User')
    user['last_name'] = user_data.get('last_name', '')
    user['last_active'] = datetime.now().isoformat()
    storage.save_user(user_id, user)
    
    elite_level = get_elite_level(user)
    elite_info = get_elite_info(elite_level)
    
    welcome = f"""
💎 *WELCOME TO VIP ELITE REWARDS!*

👋 *Hello {user['first_name']}!*

{elite_info['emoji']} *Elite Level: {elite_info['name']}*
📊 *Elite Points: {user.get('elite_points', 0)}*
💰 *Points: {user['points']}*
📅 *Streak: {user['daily_streak']} days*

📋 *Available Commands:*
/elite - Check elite status 💎
/daily - Claim daily reward 📅
/claimelite - Claim elite rewards 🎁
/upgrade - Track progress 📈
/profile - View your profile 👤
/leaderboard - Top elites 🏆
/help - All commands 📚

🔥 *Elite Benefits:*
• Higher multipliers per tier
• Exclusive elite rewards
• Up to 2x bonus points

*Use /elite to see your benefits!*
    """
    send_message(chat_id, welcome)

def handle_help(chat_id):
    help_text = """
📚 *VIP ELITE COMMANDS*
━━━━━━━━━━━━━━━━

💎 *Elite Commands:*
/elite - Check elite status
/daily - Claim daily reward
/claimelite - Claim elite rewards
/upgrade - Track progress

📊 *Info Commands:*
/profile - View profile
/leaderboard - Top elites
/help - This menu

⭐ *Elite Levels:*
🔰 Member → 🥉 Bronze → 🥈 Silver → 🥇 Gold → 💎 Platinum → 👑 Diamond

💰 *Multipliers:*
• Bronze: 1.15x
• Silver: 1.30x
• Gold: 1.50x
• Platinum: 1.75x
• Diamond: 2.00x

💡 *Earn elite points by:*
• Daily claims (+1 each)
• Streaks (+1 per week)
• Referrals (+10 each)
    """
    send_message(chat_id, help_text)

def handle_daily(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    now = datetime.now()
    
    if user.get('last_daily'):
        try:
            last = datetime.fromisoformat(user['last_daily'])
            if now - last < timedelta(hours=24):
                time_left = get_time_until(user['last_daily'])
                send_message(
                    chat_id,
                    f"""
⏳ *Already Claimed Today!*
━━━━━━━━━━━━━━━━
🕐 Next claim in: {time_left}

📅 Streak: {user['daily_streak']} days
💎 Elite: {get_elite_info(get_elite_level(user))['emoji']} {get_elite_info(get_elite_level(user))['name']}
                    """
                )
                return
        except:
            pass
    
    # Update streak
    if user.get('last_daily'):
        try:
            last = datetime.fromisoformat(user['last_daily'])
            if now - last < timedelta(hours=48):
                user['daily_streak'] += 1
            else:
                user['daily_streak'] = 1
        except:
            user['daily_streak'] = 1
    else:
        user['daily_streak'] = 1
    
    # Calculate reward with elite multiplier
    base = 10
    elite_level = get_elite_level(user)
    elite_info = get_elite_info(elite_level)
    multiplier = elite_info['multiplier']
    streak_bonus = (user['daily_streak'] // 7) * 5
    
    total_reward = int(base * multiplier) + streak_bonus
    
    # Update user
    user['points'] += total_reward
    user['total_earned'] = user.get('total_earned', 0) + total_reward
    user['elite_points'] = user.get('elite_points', 0) + 1
    user['last_daily'] = now.isoformat()
    storage.save_user(user_id, user)
    
    # Check level up
    new_elite_level = get_elite_level(user)
    level_up = new_elite_level > elite_level
    new_elite_info = get_elite_info(new_elite_level)
    
    emoji = get_streak_emoji(user['daily_streak'])
    
    message = f"""
🎉 *Daily Reward Claimed!*
━━━━━━━━━━━━━━━━
{emoji} *Reward: +{total_reward} points*
📊 *Base: {base}*
💎 *Elite Bonus: {multiplier}x*
📅 *Streak: {user['daily_streak']} days*

{new_elite_info['emoji']} *Elite: {new_elite_info['name']}*
💰 *Total: {user['points']} points*
⭐ *Elite Points: {user['elite_points']}*
    """
    
    if level_up:
        message += f"""
━━━━━━━━━━━━━━━━
🎊 *LEVEL UP!*
You are now {new_elite_info['emoji']} *{new_elite_info['name']}*!

New benefits unlocked! 🌟
        """
    
    message += "\nCome back tomorrow! 🚀"
    
    send_message(chat_id, message)

def handle_elite(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    
    elite_level = get_elite_level(user)
    elite_info = get_elite_info(elite_level)
    benefits = elite_info['benefits']
    
    next_level = elite_level + 1 if elite_level < 5 else None
    
    message = f"""
💎 *VIP ELITE STATUS*
━━━━━━━━━━━━━━━━
{elite_info['emoji']} *Level: {elite_info['name']}*
📊 *Elite Points: {user.get('elite_points', 0)}*
💰 *Points: {user['points']}*
📅 *Streak: {user['daily_streak']} days*

🎁 *Your Benefits:*
{chr(10).join([f'• {b}' for b in benefits])}
    """
    
    if next_level:
        next_info = get_elite_info(next_level)
        points_required = ELITE_LEVELS[next_level]['points_required']
        current = user.get('elite_points', 0)
        needed = max(0, points_required - current)
        progress = min(100, (current / points_required) * 100) if points_required > 0 else 0
        
        message += f"""
━━━━━━━━━━━━━━━━
📈 *Next: {next_info['emoji']} {next_info['name']}*
🎯 *Progress: {int(progress)}%*
💪 *Points needed: {needed}*
📊 *Multiplier: {next_info['multiplier']}x*
        """
    else:
        message += """
━━━━━━━━━━━━━━━━
🏆 *MAX ELITE LEVEL!*
You are a Diamond Elite! 👑
        """
    
    send_message(chat_id, message)

def handle_claimelite(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    
    elite_level = get_elite_level(user)
    
    if elite_level < 1:
        send_message(
            chat_id,
            """
🔓 *Elite Rewards Locked!*
━━━━━━━━━━━━━━━━
You need at least Bronze Elite to claim elite rewards!

💎 *How to unlock:*
• Earn 100 elite points
• Use /daily to start earning
• Build your streak

Current: {elite_level} elite points
            """
        )
        return
    
    # Check weekly claim
    now = datetime.now()
    week_num = get_week_number()
    elite_rewards = user.get('elite_rewards_claimed', [])
    weekly_key = f"elite_{week_num}"
    
    if weekly_key in elite_rewards:
        send_message(
            chat_id,
            f"""
⏳ *Elite Reward Already Claimed!*
━━━━━━━━━━━━━━━━
📅 Week: {week_num}
💎 Tier: {get_elite_info(elite_level)['emoji']} {get_elite_info(elite_level)['name']}

Come back next week! 📆
            """
        )
        return
    
    # Calculate elite reward based on tier
    rewards = {1: 25, 2: 50, 3: 75, 4: 100, 5: 150}
    reward_amount = rewards.get(elite_level, 0)
    
    user['points'] += reward_amount
    user['total_earned'] = user.get('total_earned', 0) + reward_amount
    elite_rewards.append(weekly_key)
    user['elite_rewards_claimed'] = elite_rewards
    user['last_elite_claim'] = now.isoformat()
    storage.save_user(user_id, user)
    
    elite_info = get_elite_info(elite_level)
    
    send_message(
        chat_id,
        f"""
🎉 *Elite Reward Claimed!*
━━━━━━━━━━━━━━━━
{elite_info['emoji']} *Tier: {elite_info['name']}*
💰 *Reward: +{reward_amount} points*
📅 *Week: {week_num}*

💵 *Total Points: {user['points']}*

See you next week! 🚀
        """
    )

def handle_upgrade(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    
    elite_level = get_elite_level(user)
    
    if elite_level >= 5:
        send_message(chat_id, "👑 You're already Diamond Elite - max level!")
        return
    
    next_level = elite_level + 1
    next_info = get_elite_info(next_level)
    points_required = ELITE_LEVELS[next_level]['points_required']
    current = user.get('elite_points', 0)
    needed = max(0, points_required - current)
    progress = min(100, (current / points_required) * 100) if points_required > 0 else 0
    
    # Progress bar
    bar_length = 20
    filled = int((progress / 100) * bar_length)
    bar = '▓' * filled + '░' * (bar_length - filled)
    
    send_message(
        chat_id,
        f"""
📈 *ELITE UPGRADE PROGRESS*
━━━━━━━━━━━━━━━━

{get_elite_info(elite_level)['emoji']} *Current: {get_elite_info(elite_level)['name']}*
{next_info['emoji']} *Next: {next_info['name']}*

📊 Progress: [{bar}] {int(progress)}%
💪 Points needed: {needed}
📈 Current multiplier: {get_elite_info(elite_level)['multiplier']}x
📈 Next multiplier: {next_info['multiplier']}x

🎁 *New benefits at {next_info['name']}:*
{chr(10).join([f'• {b}' for b in next_info['benefits']])}

💡 *Earn elite points by:*
• Daily claims (+1)
• Weekly streaks (+1)
• Referrals (+10)
        """
    )

def handle_profile(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    
    elite_level = get_elite_level(user)
    elite_info = get_elite_info(elite_level)
    emoji = get_streak_emoji(user['daily_streak'])
    
    all_users = storage.get_all_users()
    sorted_users = sorted(
        [(uid, data) for uid, data in all_users.items()],
        key=lambda x: x[1].get('elite_points', 0),
        reverse=True
    )
    
    rank = 1
    for i, (uid, data) in enumerate(sorted_users, 1):
        if uid == user_id:
            rank = i
            break
    
    profile_text = f"""
👤 *ELITE PROFILE*
━━━━━━━━━━━━━━━━

👤 *Name:* {user.get('first_name', 'User')}
📛 *Username:* @{user.get('username', 'N/A')}

💎 *Elite Status:*
• Level: {elite_info['emoji']} {elite_info['name']}
• Elite Points: {user.get('elite_points', 0)}
• Multiplier: {elite_info['multiplier']}x
• Rank: #{rank} of {len(sorted_users)}

💰 *Balance:*
• Points: {user['points']}
• Total Earned: {user.get('total_earned', 0)}
• Streak: {user['daily_streak']} days {emoji}
    """
    send_message(chat_id, profile_text)

def handle_leaderboard(chat_id):
    all_users = storage.get_all_users()
    
    sorted_users = sorted(
        [(uid, data) for uid, data in all_users.items()],
        key=lambda x: x[1].get('elite_points', 0),
        reverse=True
    )[:10]
    
    if not sorted_users:
        send_message(chat_id, "No elite users yet! Be the first! 🏆")
        return
    
    message = "💎 *ELITE LEADERBOARD* 💎\n━━━━━━━━━━━━━━━━\n\n"
    
    for i, (uid, data) in enumerate(sorted_users, 1):
        medal = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else f"{i}."
        name = data.get('username', data.get('first_name', f"User{uid}"))
        elite_level = get_elite_level(data)
        elite_info = get_elite_info(elite_level)
        elite_points = data.get('elite_points', 0)
        
        message += f"{medal} @{name} {elite_info['emoji']}\n"
        message += f"   Elite: {elite_points} pts | {elite_info['name']}\n"
    
    send_message(chat_id, message)

# === POLLING ===
def process_updates():
    last_update_id = 0
    logger.info("Starting polling loop...")
    
    delete_webhook()
    
    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            
            for update in updates:
                update_id = update.get('update_id')
                if update_id:
                    last_update_id = update_id
                
                if 'message' in update:
                    msg = update['message']
                    chat_id = msg['chat']['id']
                    user_data = msg.get('from', {})
                    
                    if 'text' in msg:
                        text = msg['text']
                        logger.info(f"Command from {chat_id}: {text}")
                        
                        if text.startswith('/start'):
                            handle_start(chat_id, user_data)
                        elif text.startswith('/help'):
                            handle_help(chat_id)
                        elif text.startswith('/daily'):
                            handle_daily(chat_id)
                        elif text.startswith('/elite'):
                            handle_elite(chat_id)
                        elif text.startswith('/claimelite'):
                            handle_claimelite(chat_id)
                        elif text.startswith('/upgrade'):
                            handle_upgrade(chat_id)
                        elif text.startswith('/profile'):
                            handle_profile(chat_id)
                        elif text.startswith('/leaderboard'):
                            handle_leaderboard(chat_id)
                        else:
                            send_message(
                                chat_id,
                                "❓ Unknown command. Use /help to see available commands."
                            )
            
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Process updates error: {e}")
            time.sleep(5)

# === FLASK ===
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    all_users = storage.get_all_users()
    elite_users = sum(1 for data in all_users.values() if get_elite_level(data) > 0)
    total_elite_points = sum(data.get('elite_points', 0) for data in all_users.values())
    
    return f"""
    <h1>💎 VIP Elite Rewards Bot</h1>
    <p>Bot is running!</p>
    <p>Users: {len(all_users)}</p>
    <p>Elite Users: {elite_users}</p>
    <p>Total Elite Points: {total_elite_points}</p>
    <p>Status: ✅ Active</p>
    <p>Bot: @vipeliterewards_bot</p>
    """

@app.route('/stats', methods=['GET'])
def stats_route():
    all_users = storage.get_all_users()
    return jsonify({
        'users': len(all_users),
        'elite_users': sum(1 for data in all_users.values() if get_elite_level(data) > 0),
        'total_elite_points': sum(data.get('elite_points', 0) for data in all_users.values()),
        'total_points': sum(data.get('points', 0) for data in all_users.values())
    })

# === MAIN ===
def main():
    logger.info("=" * 50)
    logger.info("Starting VIP Elite Rewards Bot...")
    logger.info("Bot: @vipeliterewards_bot")
    logger.info(f"Data File: {DATA_FILE}")
    logger.info("=" * 50)
    
    poll_thread = threading.Thread(target=process_updates, daemon=True)
    poll_thread.start()
    logger.info("Polling thread started")
    
    logger.info(f"Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()
