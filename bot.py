import discord
from discord.ext import commands
import json
import os
import math
import asyncio
from datetime import datetime, timedelta

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# XP configuration
XP_PER_MESSAGE = 15
XP_PER_IMAGE = 25
XP_COOLDOWN = 60  # seconds between XP gains per user
LEVEL_MULTIPLIER = 100  # XP needed for level 1, then increases

# File to store user data
DATA_FILE = 'user_data.json'

# Load user data
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save user data
def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Calculate level from XP
def calculate_level(xp):
    return int(math.sqrt(xp / LEVEL_MULTIPLIER))

# Calculate XP needed for next level
def xp_for_next_level(level):
    return ((level + 1) ** 2) * LEVEL_MULTIPLIER

# Check if user is in cooldown
def is_in_cooldown(user_data):
    if 'last_xp_time' not in user_data or user_data['last_xp_time'] is None:
        return False
    
    try:
        last_time = datetime.fromisoformat(user_data['last_xp_time'])
        return datetime.now() - last_time < timedelta(seconds=XP_COOLDOWN)
    except:
        return False

# Add XP to user
def add_xp(user_id, guild_id, xp_amount):
    data = load_data()
    
    # Create nested structure if it doesn't exist
    if str(guild_id) not in data:
        data[str(guild_id)] = {}
    if str(user_id) not in data[str(guild_id)]:
        data[str(guild_id)][str(user_id)] = {
            'xp': 0,
            'level': 0,
            'last_xp_time': None
        }
    
    user_data = data[str(guild_id)][str(user_id)]
    
    # Check cooldown
    if is_in_cooldown(user_data):
        return None, None
    
    # Add XP
    old_level = user_data['level']
    user_data['xp'] += xp_amount
    user_data['last_xp_time'] = datetime.now().isoformat()
    user_data['level'] = calculate_level(user_data['xp'])
    
    save_data(data)
    
    # Check if leveled up
    leveled_up = user_data['level'] > old_level
    return user_data, leveled_up

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready and monitoring {len(bot.guilds)} servers')

@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Calculate XP for this message
    xp_gained = 0
    
    # XP for text content
    if message.content.strip():
        xp_gained += XP_PER_MESSAGE
    
    # XP for images/attachments
    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                xp_gained += XP_PER_IMAGE
    
    # Add XP if any was gained
    if xp_gained > 0:
        result = add_xp(message.author.id, message.guild.id, xp_gained)
        
        if result[0] is not None:  # Not in cooldown
            user_data, leveled_up = result
            
            # Send level up message
            if leveled_up:
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{message.author.mention} reached **Level {user_data['level']}**!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Total XP", 
                    value=f"{user_data['xp']:,}", 
                    inline=True
                )
                next_level_xp = xp_for_next_level(user_data['level'])
                embed.add_field(
                    name="Next Level", 
                    value=f"{next_level_xp - user_data['xp']:,} XP needed", 
                    inline=True
                )
                
                await message.channel.send(embed=embed)
    
    # Process commands
    await bot.process_commands(message)

@bot.command(name='rank')
async def show_rank(ctx, member: discord.Member = None):
    """Show your or another user's rank and level"""
    if member is None:
        member = ctx.author
    
    data = load_data()
    
    if str(ctx.guild.id) not in data or str(member.id) not in data[str(ctx.guild.id)]:
        embed = discord.Embed(
            title="No Data",
            description=f"{member.display_name} hasn't gained any XP yet!",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    user_data = data[str(ctx.guild.id)][str(member.id)]
    
    # Calculate progress to next level
    current_level_xp = (user_data['level'] ** 2) * LEVEL_MULTIPLIER
    next_level_xp = xp_for_next_level(user_data['level'])
    progress = user_data['xp'] - current_level_xp
    needed = next_level_xp - current_level_xp
    
    # Create progress bar
    bar_length = 20
    filled = int((progress / needed) * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    embed = discord.Embed(
        title=f"📊 {member.display_name}'s Rank",
        color=0x0099ff
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Level", value=f"**{user_data['level']}**", inline=True)
    embed.add_field(name="Total XP", value=f"**{user_data['xp']:,}**", inline=True)
    embed.add_field(name="Next Level", value=f"**{next_level_xp - user_data['xp']:,}** XP", inline=True)
    embed.add_field(
        name="Progress", 
        value=f"{bar} {progress}/{needed}", 
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def leaderboard(ctx, limit: int = 10):
    """Show the server leaderboard"""
    if limit > 20:
        limit = 20
    
    data = load_data()
    
    if str(ctx.guild.id) not in data:
        embed = discord.Embed(
            title="Empty Leaderboard",
            description="No one has gained XP yet!",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    # Sort users by XP
    guild_data = data[str(ctx.guild.id)]
    sorted_users = sorted(guild_data.items(), key=lambda x: x[1]['xp'], reverse=True)
    
    # Create leaderboard embed
    embed = discord.Embed(
        title=f"🏆 {ctx.guild.name} Leaderboard",
        color=0xffd700
    )
    
    description = ""
    for i, (user_id, user_data) in enumerate(sorted_users[:limit], 1):
        try:
            user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            description += f"{medal} **{user.display_name}** - Level {user_data['level']} ({user_data['xp']:,} XP)\n"
        except:
            description += f"{i}. Unknown User - Level {user_data['level']} ({user_data['xp']:,} XP)\n"
    
    embed.description = description
    await ctx.send(embed=embed)

@bot.command(name='xp-info')
async def xp_info(ctx):
    """Show information about the XP system"""
    embed = discord.Embed(
        title="📈 XP System Information",
        color=0x0099ff
    )
    embed.add_field(
        name="XP Gains",
        value=f"• Text message: **{XP_PER_MESSAGE} XP**\n• Image: **{XP_PER_IMAGE} XP**",
        inline=False
    )
    embed.add_field(
        name="Cooldown",
        value=f"**{XP_COOLDOWN} seconds** between XP gains",
        inline=False
    )
    embed.add_field(
        name="Level Formula",
        value=f"Level = √(Total XP ÷ {LEVEL_MULTIPLIER})",
        inline=False
    )
    embed.add_field(
        name="Commands",
        value="• `!rank` - View your rank\n• `!leaderboard` - Server leaderboard\n• `!xp-info` - This information",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument!")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided!")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        print(f"Unexpected error: {error}")

# Run the bot
if __name__ == "__main__":
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token
    bot.run(os.getenv('BOT_TOKEN'))