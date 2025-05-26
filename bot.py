import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = int(os.environ.get("GUILD_ID"))

LOG_CHANNEL_NAME = "관리자-로그"
INVITE_EXPIRY_HOURS = 24

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

invite_guard = {}

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    for guild in bot.guilds:
        try:
            await bot.tree.sync(guild=guild)
            print(f"✅ [{guild.name}] 슬래시 명령어 등록 완료!")
        except Exception as e:
            print(f"❌ [{guild.name}] 명령어 등록 실패: {e}")

    check_invite_guard.start()
    print(f"🤖 봇 온라인: {bot.user}")

@tree.command(
    name="초대",
    description="24시간 동안 유효한 1회용 임시 초대링크를 생성합니다.",
    guild=discord.Object(id=GUILD_ID)
)
async def invite_command(interaction: discord.Interaction):
    invite = await interaction.channel.create_invite(
        max_age=INVITE_EXPIRY_HOURS * 3600,
        max_uses=1,
        unique=True,
        reason=f"{interaction.user} 생성"
    )
    await interaction.response.send_message(
        f"임시 초대링크: {invite.url}\n(24시간, 1회용)", ephemeral=True
    )
    log_channel = discord.utils.get(interaction.guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        await log_channel.send(f"🔗 {interaction.user.mention}님이 임시 초대링크를 생성했습니다.\n{invite.url}")

@bot.event
async def on_member_join(member):
    expire_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)
    invite_guard[member.id] = expire_at

    log_channel = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        await log_channel.send(f"👋 {member.mention}님이 입장했습니다. 24시간 내 역할 없으면 추방됩니다.")

@bot.event
async def on_member_update(before, after):
    if after.id in invite_guard and len(after.roles) > 1:
        invite_guard.pop(after.id, None)
        log_channel = discord.utils.get(after.guild.text_channels, name=LOG_CHANNEL_NAME)
        if log_channel:
            await log_channel.send(f"✅ {after.mention}님에게 역할이 부여되어 추방 감시 해제되었습니다.")

@tasks.loop(minutes=10)
async def check_invite_guard():
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    for guild in bot.guilds:
        for user_id, expire_at in list(invite_guard.items()):
            member = guild.get_member(user_id)
            if member and len(member.roles) <= 1 and now > expire_at:
                try:
                    await member.kick(reason="24시간 내 역할 미부여로 자동 추방")
                    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
                    if log_channel:
                        await log_channel.send(f"⛔️ {member.mention}님이 24시간 내 역할 미부여로 추방되었습니다.")
                except Exception as e:
                    print(f"추방 실패: {member} - {e}")
                invite_guard.pop(user_id, None)

if __name__ == "__main__":
    bot.run(TOKEN)
