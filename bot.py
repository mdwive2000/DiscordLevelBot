@bot.command(name='xp-info')
async def xp_info(ctx):
    """Show information about the XP system"""
    xp_settings = get_xp_settings(ctx.guild.id)
    
    embed = discord.Embed(
        title="📈 XP System Information",
        color=0x0099ff
    )
    embed.add_field(
        name="XP Gains",
        value=f"• Text message: **{xp_settings['text_min']}-{xp_settings['text_max']} XP** (random)\n• Image (png/jpg/webp): **{xp_settings['image']} XP**\n• GIF: **{xp_settings['gif']} XP**\n• Video (mp4/mov/etc): **{xp_settings['video']} XP**\n• Other files: **{xp_settings['other_file']} XP**",
        inline=False
    )
    embed.add_field(
        name="Cooldown",
        value=f"**{xp_settings['cooldown']} seconds** between XP gains",
        inline=False
    )
    
    if XP_BOOST_CHANNELS:
        boost_info = ""
        for channel_id, multiplier in XP_BOOST_CHANNELS.items():
            channel = bot.get_channel(channel_id)
            if channel and channel.guild.id == ctx.guild.id:
                boost_info += f"• {channel.mention}: **{multiplier}x** XP\n"
        if boost_info:
            embed.add_field(name="Channel Boosts", value=boost_info, inline=False)
    
    if LEVEL_ROLES:
        roles_info = ""
        for level, role_name in sorted(LEVEL_ROLES.items()):
            roles_info += f"• Level {level}: **{role_name}** role\n"
        embed.add_field(name="Role Rewards", value=roles_info, inline=False)
    
    embed.add_field(
        name="User Commands",
        value="• `!rank` - View your custom rank card\n• `!leaderboard` - Server leaderboard\n• `!xp-info` - This information",
        inline=False
    )
    embed.add_field(
        name="Admin Commands",
        value="• `!give-xp @user amount` - Give XP\n• `!set-level @user level` - Set level\n• `!give-hp @user amount` - Modify HP\n• `!reset-user @user` - Reset progress\n• `!set-levelup-channel #channel` - Set announcement channel",
        inline=False
    )
    embed.add_field(
        name="XP System Admin Commands",
        value="• `!add-channel-boost #channel 2.0` - Add channel XP boost\n• `!set-xp-amounts text 20 40` - Set XP amounts\n• `!set-cooldown 15` - Set XP cooldown\n• `!add-role-multiplier @role 2.0` - Add role XP boost\n• `!xp-settings` - View XP settings",
        inline=False
    )
    embed.add_field(
        name="Rank Card Customization",
        value="• `!set-rank-colors #primary #background` - Set colors\n• `!set-rank-emoji :emoji:` - Set server emoji\n• `!set-rank-font bold/normal/italic` - Set font\n• `!rank-settings` - View current settingsimport discord
from discord.ext import commands
import json
import os
import math
import asyncio
import random
import aiohttp
import io
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# XP configuration (per server - will be customizable)
DEFAULT_XP_SETTINGS = {
    'text_min': 15,
    'text_max': 35,
    'image': 25,
    'gif': 35,
    'video': 50,
    'other_file': 15,
    'cooldown': 10
}

# Role XP multipliers (per server)
ROLE_XP_MULTIPLIERS = {
    # Will store role_id: multiplier pairs per server
}
LEVEL_MULTIPLIER = 100         # XP needed for level 1, then increases

# Channel XP boosts (channel_id: multiplier)
XP_BOOST_CHANNELS = {
    # Add your channel IDs here like: 123456789012345678: 2.0  # 2x XP boost
}

# Level up announcement channel
LEVELUP_CHANNEL_ID = None

# Role rewards for reaching certain levels
LEVEL_ROLES = {
    5: "Apprentice",  # Level 5 gets "Apprentice" role
    10: "Devotee",    # Level 10 gets "Devotee" role
    20: "Expert",     # Level 20 gets "Expert" role
    35: "Master",     # Level 35 gets "Master" role
    50: "Legend"      # Level 50 gets "Legend" role
}

# Rank card customization settings (per server)
RANK_CARD_SETTINGS = {
    # Default settings - will be loaded/saved per server
    'font_style': 'bold',  # 'normal', 'bold', 'italic'
    'primary_color': '#00D4AA',  # Teal color like in the image
    'secondary_color': '#FFFFFF',  # White color
    'background_color': '#2C2F33',  # Dark Discord color
    'server_emoji': None,  # Custom emoji ID or None
    'card_style': 'modern'  # 'modern', 'classic', 'minimal'
}

# Files to store data
DATA_FILE = 'user_data.json'
SETTINGS_FILE = 'server_settings.json'
XP_SETTINGS_FILE = 'xp_settings.json'

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

# Load/Save XP settings
def load_xp_settings():
    if os.path.exists(XP_SETTINGS_FILE):
        with open(XP_SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_xp_settings(settings):
    with open(XP_SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def get_xp_settings(guild_id):
    settings = load_xp_settings()
    return settings.get(str(guild_id), DEFAULT_XP_SETTINGS.copy())

def update_xp_settings(guild_id, new_settings):
    settings = load_xp_settings()
    if str(guild_id) not in settings:
        settings[str(guild_id)] = DEFAULT_XP_SETTINGS.copy()
    settings[str(guild_id)].update(new_settings)
    save_xp_settings(settings)

def get_role_multiplier(member):
    """Get the highest XP multiplier from user's roles"""
    settings = load_xp_settings()
    guild_multipliers = settings.get(str(member.guild.id), {}).get('role_multipliers', {})
    
    highest_multiplier = 1.0
    for role in member.roles:
        multiplier = guild_multipliers.get(str(role.id), 1.0)
        if multiplier > highest_multiplier:
            highest_multiplier = multiplier
    
    return highest_multiplier

# Load server settings
def load_server_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save server settings
def save_server_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

# Get server rank card settings
def get_server_settings(guild_id):
    settings = load_server_settings()
    return settings.get(str(guild_id), RANK_CARD_SETTINGS.copy())

# Update server rank card settings
def update_server_settings(guild_id, new_settings):
    settings = load_server_settings()
    if str(guild_id) not in settings:
        settings[str(guild_id)] = RANK_CARD_SETTINGS.copy()
    settings[str(guild_id)].update(new_settings)
    save_server_settings(settings)

# Calculate level from XP
def calculate_level(xp):
    return int(math.sqrt(xp / LEVEL_MULTIPLIER))

# Calculate XP needed for next level
def xp_for_next_level(level):
    return ((level + 1) ** 2) * LEVEL_MULTIPLIER

# Check if user is in cooldown
def is_in_cooldown(user_data, guild_id):
    if 'last_xp_time' not in user_data or user_data['last_xp_time'] is None:
        return False
    
    try:
        last_time = datetime.fromisoformat(user_data['last_xp_time'])
        xp_settings = get_xp_settings(guild_id)
        cooldown = xp_settings.get('cooldown', 10)
        return datetime.now() - last_time < timedelta(seconds=cooldown)
    except:
        return False

# Add XP to user
def add_xp(user_id, guild_id, xp_amount):
    data = load_data()
    
    if str(guild_id) not in data:
        data[str(guild_id)] = {}
    if str(user_id) not in data[str(guild_id)]:
        data[str(guild_id)][str(user_id)] = {
            'xp': 0,
            'level': 0,
            'last_xp_time': None,
            'hp': 100
        }
    
    user_data = data[str(guild_id)][str(user_id)]
    
    if is_in_cooldown(user_data, guild_id):
        return None, None
    
    old_level = user_data['level']
    user_data['xp'] += xp_amount
    user_data['last_xp_time'] = datetime.now().isoformat()
    user_data['level'] = calculate_level(user_data['xp'])
    
    if 'hp' not in user_data:
        user_data['hp'] = 100
    
    save_data(data)
    
    leveled_up = user_data['level'] > old_level
    return user_data, leveled_up

# Check admin permissions
def has_admin_permission(ctx):
    return ctx.author.guild_permissions.administrator or any(role.name.lower() in ['moderator', 'admin', 'mod'] for role in ctx.author.roles)

# Download user avatar
async def get_user_avatar(user):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(user.display_avatar.url)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(io.BytesIO(data)).convert('RGBA')
    except:
        pass
    # Return default avatar if failed
    default = Image.new('RGBA', (128, 128), (255, 255, 255, 255))
    return default

# Create gradient background
def create_gradient(width, height, color1, color2):
    base = Image.new('RGB', (width, height), color1)
    top = Image.new('RGB', (width, height), color2)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        mask_data.extend([int(255 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base

# Get server emoji as image
async def get_server_emoji(guild, emoji_id):
    if not emoji_id:
        return None
    try:
        emoji = discord.utils.get(guild.emojis, id=int(emoji_id))
        if emoji:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(emoji.url)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return Image.open(io.BytesIO(data)).convert('RGBA')
    except:
        pass
    return None

# Create custom rank card
async def create_rank_card(user, user_data, guild, rank_position=0):
    settings = get_server_settings(guild.id)
    
    # Card dimensions
    width, height = 800, 200
    
    # Create gradient background
    try:
        primary = tuple(int(settings['primary_color'][i:i+2], 16) for i in (1, 3, 5))
        background = tuple(int(settings['background_color'][i:i+2], 16) for i in (1, 3, 5))
    except:
        primary = (0, 212, 170)  # Default teal
        background = (44, 47, 51)  # Default dark
    
    # Create base image
    img = Image.new('RGBA', (width, height), background + (255,))
    draw = ImageDraw.Draw(img)
    
    # Add gradient overlay
    gradient = create_gradient(width, height//3, primary, background)
    img.paste(gradient, (0, 0), Image.new('L', (width, height//3), 128))
    
    # Get user avatar
    try:
        avatar = await get_user_avatar(user)
        avatar = avatar.resize((120, 120), Image.Resampling.LANCZOS)
        
        # Create circular mask for avatar
        mask = Image.new('L', (120, 120), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 120, 120), fill=255)
        
        # Create circular avatar
        avatar_pos = (20, 40)
        img.paste(avatar, avatar_pos, mask)
        
        # Add avatar border
        draw.ellipse([avatar_pos[0]-2, avatar_pos[1]-2, avatar_pos[0]+122, avatar_pos[1]+122], 
                    outline=primary + (255,), width=3)
    except Exception as e:
        print(f"Avatar error: {e}")
    
    # Try to load custom font
    try:
        if settings['font_style'] == 'bold':
            font_large = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 32)
            font_medium = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 20)
            font_small = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 16)
        else:
            font_large = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 32)
            font_medium = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 20)
            font_small = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 16)
    except:
        # Fallback to default font
        try:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        except:
            font_large = font_medium = font_small = None
    
    # Username
    username = f"@{user.display_name}"
    if font_large:
        draw.text((160, 30), username, fill=(255, 255, 255, 255), font=font_large)
    
    # Level, XP, Rank info
    level_text = f"Level: {user_data['level']}"
    current_level_xp = (user_data['level'] ** 2) * LEVEL_MULTIPLIER
    next_level_xp = xp_for_next_level(user_data['level'])
    xp_text = f"XP: {user_data['xp'] - current_level_xp} / {next_level_xp - current_level_xp}"
    rank_text = f"Rank: #{rank_position}" if rank_position > 0 else "Rank: N/A"
    
    if font_medium:
        draw.text((160, 75), level_text, fill=(255, 255, 255, 255), font=font_medium)
        draw.text((280, 75), xp_text, fill=(255, 255, 255, 255), font=font_medium)
        draw.text((520, 75), rank_text, fill=(255, 255, 255, 255), font=font_medium)
    
    # Progress bar
    bar_x, bar_y, bar_width, bar_height = 160, 110, 500, 25
    progress = (user_data['xp'] - current_level_xp) / (next_level_xp - current_level_xp) if next_level_xp > current_level_xp else 1
    
    # Progress bar background
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], 
                          radius=12, fill=(100, 100, 100, 255))
    
    # Progress bar fill
    fill_width = int(bar_width * progress)
    if fill_width > 0:
        # Create gradient for progress bar
        progress_gradient = create_gradient(fill_width, bar_height, primary, 
                                          tuple(min(255, c + 50) for c in primary))
        progress_img = Image.new('RGBA', (fill_width, bar_height))
        progress_img.paste(progress_gradient, (0, 0))
        
        # Create rounded rectangle mask
        mask = Image.new('L', (fill_width, bar_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, fill_width, bar_height], radius=12, fill=255)
        
        img.paste(progress_img, (bar_x, bar_y), mask)
    
    # HP bar (smaller, below progress bar)
    hp_bar_y = bar_y + 35
    hp_bar_height = 8
    hp_progress = user_data.get('hp', 100) / 100
    
    # HP bar background
    draw.rounded_rectangle([bar_x, hp_bar_y, bar_x + bar_width, hp_bar_y + hp_bar_height], 
                          radius=4, fill=(60, 60, 60, 255))
    
    # HP bar fill (red to green gradient based on HP)
    if hp_progress > 0:
        hp_fill_width = int(bar_width * hp_progress)
        hp_color = (int(255 * (1 - hp_progress)), int(255 * hp_progress), 0)  # Red to green
        draw.rounded_rectangle([bar_x, hp_bar_y, bar_x + hp_fill_width, hp_bar_y + hp_bar_height], 
                              radius=4, fill=hp_color + (255,))
    
    # HP text
    hp_text = f"HP: {user_data.get('hp', 100)}/100"
    if font_small:
        draw.text((bar_x, hp_bar_y + 12), hp_text, fill=(200, 200, 200, 255), font=font_small)
    
    # Server emoji/decoration
    try:
        if settings['server_emoji']:
            emoji_img = await get_server_emoji(guild, settings['server_emoji'])
            if emoji_img:
                emoji_img = emoji_img.resize((60, 60), Image.Resampling.LANCZOS)
                img.paste(emoji_img, (720, 20), emoji_img)
    except Exception as e:
        print(f"Emoji error: {e}")
    
    # Add subtle border
    draw.rectangle([0, 0, width-1, height-1], outline=primary + (100,), width=2)
    
    return img

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready and monitoring {len(bot.guilds)} servers')
    print(f'XP Cooldown set to {XP_COOLDOWN} seconds')
    print('Custom rank cards enabled! 🎨')

async def give_role_reward(member, level):
    """Give role reward for reaching certain level"""
    if level in LEVEL_ROLES:
        role_name = LEVEL_ROLES[level]
        guild = member.guild
        
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try:
                colors = [0xff6b6b, 0x4ecdc4, 0x45b7d1, 0xf9ca24, 0xf0932b, 0xeb4d4b, 0x6c5ce7]
                color = colors[level % len(colors)]
                role = await guild.create_role(name=role_name, color=discord.Color(color), reason="Level reward role")
            except discord.Forbidden:
                print(f"Cannot create role {role_name} - missing permissions")
                return None
        
        try:
            await member.add_roles(role, reason=f"Reached level {level}")
            return role
        except discord.Forbidden:
            print(f"Cannot assign role {role_name} to {member}")
            return None
    return None

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Get XP settings for this server
    xp_settings = get_xp_settings(message.guild.id)
    
    xp_gained = 0
    media_types = []
    
    # XP for text content (random between min-max)
    if message.content.strip():
        text_xp = random.randint(xp_settings['text_min'], xp_settings['text_max'])
        xp_gained += text_xp
        media_types.append(f"text({text_xp})")
    
    # XP for attachments based on file type
    if message.attachments:
        for attachment in message.attachments:
            filename = attachment.filename.lower()
            
            if filename.endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                xp_gained += xp_settings['image']
                media_types.append("image")
            elif filename.endswith('.gif'):
                xp_gained += xp_settings['gif']
                media_types.append("GIF")
            elif filename.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v')):
                xp_gained += xp_settings['video']
                media_types.append("video")
            else:
                xp_gained += xp_settings['other_file']
                media_types.append("file")
    
    # Apply channel XP boost
    if message.channel.id in XP_BOOST_CHANNELS:
        multiplier = XP_BOOST_CHANNELS[message.channel.id]
        xp_gained = int(xp_gained * multiplier)
    
    # Apply role XP multiplier
    role_multiplier = get_role_multiplier(message.author)
    if role_multiplier > 1.0:
        xp_gained = int(xp_gained * role_multiplier)
    
    if xp_gained > 0:
        result = add_xp(message.author.id, message.guild.id, xp_gained)
        
        if result[0] is not None:
            user_data, leveled_up = result
            
            role_given = None
            if leveled_up:
                role_given = await give_role_reward(message.author, user_data['level'])
            
            if leveled_up:
                # Create custom rank card for level up
                try:
                    rank_card = await create_rank_card(message.author, user_data, message.guild)
                    
                    # Save image to bytes
                    img_bytes = io.BytesIO()
                    rank_card.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    
                    # Create file and embed
                    file = discord.File(img_bytes, filename='levelup.png')
                    
                    embed = discord.Embed(
                        title="🎉 Level Up Achievement!",
                        description=f"**{message.author.display_name}** reached Level **{user_data['level']}**!",
                        color=0x00D4AA
                    )
                    
                    # Show XP breakdown
                    xp_breakdown = f"+{xp_gained} XP from: {', '.join(media_types)}"
                    if message.channel.id in XP_BOOST_CHANNELS:
                        xp_breakdown += f" (Channel: x{XP_BOOST_CHANNELS[message.channel.id]})"
                    if role_multiplier > 1.0:
                        xp_breakdown += f" (Role: x{role_multiplier})"
                    
                    embed.add_field(name="XP Earned", value=xp_breakdown, inline=False)
                    
                    if role_given:
                        embed.add_field(
                            name="🏆 Role Reward", 
                            value=f"You earned the **{role_given.name}** role!", 
                            inline=False
                        )
                    
                    embed.set_image(url="attachment://levelup.png")
                    embed.set_footer(text=f"Leveled up in #{message.channel.name}")
                    
                    # Send to levelup channel or current channel
                    target_channel = message.channel
                    if LEVELUP_CHANNEL_ID:
                        levelup_channel = bot.get_channel(LEVELUP_CHANNEL_ID)
                        if levelup_channel:
                            target_channel = levelup_channel
                    
                    await target_channel.send(embed=embed, file=file)
                    
                except Exception as e:
                    print(f"Error creating rank card: {e}")
                    # Fallback to simple embed
                    embed = discord.Embed(
                        title="🎉 Level Up!",
                        description=f"{message.author.mention} reached **Level {user_data['level']}**!",
                        color=0x00ff00
                    )
                    await message.channel.send(embed=embed)
    
    await bot.process_commands(message)

@bot.command(name='rank')
async def show_rank(ctx, member: discord.Member = None):
    """Show custom rank card for user"""
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
    
    # Calculate rank position
    guild_data = data[str(ctx.guild.id)]
    sorted_users = sorted(guild_data.items(), key=lambda x: x[1]['xp'], reverse=True)
    rank_position = next((i+1 for i, (uid, _) in enumerate(sorted_users) if uid == str(member.id)), 0)
    
    try:
        # Create custom rank card
        rank_card = await create_rank_card(member, user_data, ctx.guild, rank_position)
        
        # Save image to bytes
        img_bytes = io.BytesIO()
        rank_card.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # Send as file
        file = discord.File(img_bytes, filename='rank.png')
        await ctx.send(file=file)
        
    except Exception as e:
        print(f"Error creating rank card: {e}")
        # Fallback to embed
        embed = discord.Embed(
            title=f"📊 {member.display_name}'s Rank",
            color=0x0099ff
        )
        embed.add_field(name="Level", value=f"**{user_data['level']}**", inline=True)
        embed.add_field(name="Total XP", value=f"**{user_data['xp']:,}**", inline=True)
        embed.add_field(name="HP", value=f"**{user_data.get('hp', 100)}/100**", inline=True)
        await ctx.send(embed=embed)

# XP SETTINGS ADMIN COMMANDS
@bot.command(name='add-channel-boost')
async def add_channel_boost(ctx, channel: discord.TextChannel, multiplier: float):
    """Add XP boost to a channel (Admin only) - Usage: !add-channel-boost #general 2.0"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    if multiplier <= 0 or multiplier > 10:
        await ctx.send("❌ Multiplier must be between 0.1 and 10.0!")
        return
    
    global XP_BOOST_CHANNELS
    XP_BOOST_CHANNELS[channel.id] = multiplier
    
    # Save to server settings
    settings = load_server_settings()
    if str(ctx.guild.id) not in settings:
        settings[str(ctx.guild.id)] = {}
    if 'channel_boosts' not in settings[str(ctx.guild.id)]:
        settings[str(ctx.guild.id)]['channel_boosts'] = {}
    settings[str(ctx.guild.id)]['channel_boosts'][str(channel.id)] = multiplier
    save_server_settings(settings)
    
    await ctx.send(f"✅ Added **{multiplier}x** XP boost to {channel.mention}!")

@bot.command(name='remove-channel-boost')
async def remove_channel_boost(ctx, channel: discord.TextChannel):
    """Remove XP boost from a channel (Admin only)"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    global XP_BOOST_CHANNELS
    if channel.id in XP_BOOST_CHANNELS:
        del XP_BOOST_CHANNELS[channel.id]
        
        # Remove from server settings
        settings = load_server_settings()
        if (str(ctx.guild.id) in settings and 
            'channel_boosts' in settings[str(ctx.guild.id)] and
            str(channel.id) in settings[str(ctx.guild.id)]['channel_boosts']):
            del settings[str(ctx.guild.id)]['channel_boosts'][str(channel.id)]
            save_server_settings(settings)
        
        await ctx.send(f"✅ Removed XP boost from {channel.mention}!")
    else:
        await ctx.send(f"❌ {channel.mention} doesn't have an XP boost!")

@bot.command(name='set-xp-amounts')
async def set_xp_amounts(ctx, media_type: str, amount: int, max_amount: int = None):
    """Set XP amounts for different media types (Admin only)
    Usage: !set-xp-amounts text 20 40 (for random 20-40)
           !set-xp-amounts image 30 (for fixed 30)
    Types: text, image, gif, video, file"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    if amount <= 0 or amount > 1000:
        await ctx.send("❌ XP amount must be between 1 and 1000!")
        return
    
    media_type = media_type.lower()
    if media_type not in ['text', 'image', 'gif', 'video', 'file']:
        await ctx.send("❌ Media type must be: text, image, gif, video, or file")
        return
    
    settings_update = {}
    
    if media_type == 'text':
        if max_amount is None:
            max_amount = amount
        if max_amount < amount:
            await ctx.send("❌ Maximum XP must be greater than or equal to minimum XP!")
            return
        settings_update['text_min'] = amount
        settings_update['text_max'] = max_amount
        await ctx.send(f"✅ Text XP set to **{amount}-{max_amount}** (random)!")
    elif media_type == 'image':
        settings_update['image'] = amount
        await ctx.send(f"✅ Image XP set to **{amount}**!")
    elif media_type == 'gif':
        settings_update['gif'] = amount
        await ctx.send(f"✅ GIF XP set to **{amount}**!")
    elif media_type == 'video':
        settings_update['video'] = amount
        await ctx.send(f"✅ Video XP set to **{amount}**!")
    elif media_type == 'file':
        settings_update['other_file'] = amount
        await ctx.send(f"✅ Other files XP set to **{amount}**!")
    
    update_xp_settings(ctx.guild.id, settings_update)

@bot.command(name='set-cooldown')
async def set_cooldown(ctx, seconds: int):
    """Set XP cooldown in seconds (Admin only) - Usage: !set-cooldown 15"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    if seconds < 1 or seconds > 300:
        await ctx.send("❌ Cooldown must be between 1 and 300 seconds!")
        return
    
    update_xp_settings(ctx.guild.id, {'cooldown': seconds})
    await ctx.send(f"✅ XP cooldown set to **{seconds} seconds**!")

@bot.command(name='add-role-multiplier')
async def add_role_multiplier(ctx, role: discord.Role, multiplier: float):
    """Add XP multiplier to a role (Admin only) - Usage: !add-role-multiplier @VIP 2.0"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    if multiplier <= 0 or multiplier > 10:
        await ctx.send("❌ Multiplier must be between 0.1 and 10.0!")
        return
    
    # Load current settings
    settings = load_xp_settings()
    if str(ctx.guild.id) not in settings:
        settings[str(ctx.guild.id)] = DEFAULT_XP_SETTINGS.copy()
    if 'role_multipliers' not in settings[str(ctx.guild.id)]:
        settings[str(ctx.guild.id)]['role_multipliers'] = {}
    
    settings[str(ctx.guild.id)]['role_multipliers'][str(role.id)] = multiplier
    save_xp_settings(settings)
    
    await ctx.send(f"✅ Added **{multiplier}x** XP multiplier to {role.mention}!")

@bot.command(name='remove-role-multiplier')
async def remove_role_multiplier(ctx, role: discord.Role):
    """Remove XP multiplier from a role (Admin only)"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    settings = load_xp_settings()
    if (str(ctx.guild.id) in settings and 
        'role_multipliers' in settings[str(ctx.guild.id)] and
        str(role.id) in settings[str(ctx.guild.id)]['role_multipliers']):
        
        del settings[str(ctx.guild.id)]['role_multipliers'][str(role.id)]
        save_xp_settings(settings)
        await ctx.send(f"✅ Removed XP multiplier from {role.mention}!")
    else:
        await ctx.send(f"❌ {role.mention} doesn't have an XP multiplier!")

@bot.command(name='xp-settings')
async def show_xp_settings(ctx):
    """Show current XP settings (Admin only)"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    xp_settings = get_xp_settings(ctx.guild.id)
    
    embed = discord.Embed(
        title="⚙️ XP System Settings",
        color=0x0099ff
    )
    
    # XP amounts
    embed.add_field(
        name="XP Amounts",
        value=f"• Text: **{xp_settings['text_min']}-{xp_settings['text_max']}** XP\n"
              f"• Image: **{xp_settings['image']}** XP\n"
              f"• GIF: **{xp_settings['gif']}** XP\n"
              f"• Video: **{xp_settings['video']}** XP\n"
              f"• Other files: **{xp_settings['other_file']}** XP",
        inline=False
    )
    
    embed.add_field(
        name="Cooldown",
        value=f"**{xp_settings['cooldown']} seconds**",
        inline=True
    )
    
    # Channel boosts
    if XP_BOOST_CHANNELS:
        boost_info = ""
        for channel_id, multiplier in XP_BOOST_CHANNELS.items():
            channel = bot.get_channel(channel_id)
            if channel and channel.guild.id == ctx.guild.id:
                boost_info += f"• {channel.mention}: **{multiplier}x**\n"
        if boost_info:
            embed.add_field(name="Channel Boosts", value=boost_info, inline=False)
    
    # Role multipliers
    role_multipliers = xp_settings.get('role_multipliers', {})
    if role_multipliers:
        role_info = ""
        for role_id, multiplier in role_multipliers.items():
            role = ctx.guild.get_role(int(role_id))
            if role:
                role_info += f"• {role.mention}: **{multiplier}x**\n"
        if role_info:
            embed.add_field(name="Role Multipliers", value=role_info, inline=False)
    
    await ctx.send(embed=embed)
async def set_rank_colors(ctx, primary_color: str, background_color: str = None):
    """Set rank card colors (Admin only) - Usage: !set-rank-colors #00D4AA #2C2F33"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    # Validate hex colors
    if not primary_color.startswith('#') or len(primary_color) != 7:
        await ctx.send("❌ Primary color must be in hex format (e.g., #00D4AA)")
        return
    
    if background_color and (not background_color.startswith('#') or len(background_color) != 7):
        await ctx.send("❌ Background color must be in hex format (e.g., #2C2F33)")
        return
    
    settings_update = {'primary_color': primary_color}
    if background_color:
        settings_update['background_color'] = background_color
    
    update_server_settings(ctx.guild.id, settings_update)
    
    embed = discord.Embed(
        title="✅ Rank Card Colors Updated!",
        description=f"Primary: `{primary_color}`" + (f"\nBackground: `{background_color}`" if background_color else ""),
        color=int(primary_color[1:], 16)
    )
    await ctx.send(embed=embed)

@bot.command(name='set-rank-emoji')
async def set_rank_emoji(ctx, emoji: discord.Emoji = None):
    """Set server emoji for rank cards (Admin only) - Usage: !set-rank-emoji :custom_emoji:"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    emoji_id = None
    if emoji:
        emoji_id = emoji.id
    
    update_server_settings(ctx.guild.id, {'server_emoji': emoji_id})
    
    if emoji:
        await ctx.send(f"✅ Rank card emoji set to {emoji}!")
    else:
        await ctx.send("✅ Rank card emoji removed!")

@bot.command(name='set-rank-font')
async def set_rank_font(ctx, font_style: str):
    """Set rank card font style (Admin only) - Usage: !set-rank-font bold/normal/italic"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    if font_style.lower() not in ['bold', 'normal', 'italic']:
        await ctx.send("❌ Font style must be: bold, normal, or italic")
        return
    
    update_server_settings(ctx.guild.id, {'font_style': font_style.lower()})
    await ctx.send(f"✅ Rank card font set to **{font_style}**!")

@bot.command(name='rank-settings')
async def show_rank_settings(ctx):
    """Show current rank card settings (Admin only)"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    settings = get_server_settings(ctx.guild.id)
    
    embed = discord.Embed(
        title="🎨 Rank Card Settings",
        color=int(settings['primary_color'][1:], 16)
    )
    embed.add_field(name="Primary Color", value=settings['primary_color'], inline=True)
    embed.add_field(name="Background Color", value=settings['background_color'], inline=True)
    embed.add_field(name="Font Style", value=settings['font_style'].title(), inline=True)
    
    if settings['server_emoji']:
        emoji = discord.utils.get(ctx.guild.emojis, id=settings['server_emoji'])
        embed.add_field(name="Server Emoji", value=str(emoji) if emoji else "Not found", inline=True)
    else:
        embed.add_field(name="Server Emoji", value="None", inline=True)
    
    await ctx.send(embed=embed)

# Keep all other existing commands (leaderboard, give-xp, etc.)
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
    
    guild_data = data[str(ctx.guild.id)]
    sorted_users = sorted(guild_data.items(), key=lambda x: x[1]['xp'], reverse=True)
    
    embed = discord.Embed(
        title=f"🏆 {ctx.guild.name} Leaderboard",
        color=0xffd700
    )
    
    description = ""
    for i, (user_id, user_data) in enumerate(sorted_users[:limit], 1):
        try:
            user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            hp = user_data.get('hp', 100)
            description += f"{medal} **{user.display_name}** - Level {user_data['level']} ({user_data['xp']:,} XP) | HP: {hp}\n"
        except:
            hp = user_data.get('hp', 100)
            description += f"{i}. Unknown User - Level {user_data['level']} ({user_data['xp']:,} XP) | HP: {hp}\n"
    
    embed.description = description
    await ctx.send(embed=embed)

@bot.command(name='give-xp')
async def give_xp_command(ctx, member: discord.Member, amount: int):
    """Give XP to a user (Admin only)"""
    if not has_admin_permission(ctx):
        await ctx.send("❌ You need administrator permissions to use this command!")
        return
    
    if amount <= 0:
        await ctx.send("❌ XP amount must be positive!")
        return
    
    data = load_data()
    
    if str(ctx.guild.id) not in data:
        data[str(ctx.guild.id)] = {}
    if str(member.id) not in data[str(ctx.guild.id)]:
        data[str(ctx.guild.id)][str(member.id)] = {
            'xp': 0,
            'level': 0,
            'last_xp_time': None,
            'hp': 100
        }
    
    user_data = data[str(ctx.guild.id)][str(member.id)]
    old_level = user_data['level']
    user_data['xp'] += amount
    user_data['level'] = calculate_level(user_data['xp'])
