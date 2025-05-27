import os
import discord
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = int(os.environ.get("GUILD_ID"))

LOG_CHANNEL_NAME = "관리자-로그"
INVITE_EXPIRY_HOURS = 24

intents = discord.Intents.all()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

invite_guard = {}

@bot.event
async def on_ready():
    try:
        # 한 길드에서만 동기화 (GUILD_ID 사용)
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ [Guild ID: {GUILD_ID}] 슬래시 명령어 등록 완료!")
    except Exception as e:
        print(f"❌ 슬래시 명령어 등록 실패: {e}")

    check_invite_guard.start()
    print(f"🤖 봇 온라인: {bot.user}")

@tree.command(
    name="초대",
    description="24시간 동안 유효한 1회용 임시 초대링크를 생성합니다.",
    guild=discord.Object(id=GUILD_ID)
)
@discord.app_commands.guild_only()
async def invite_command(interaction: discord.Interaction):
    # #가입신청 채널에서만 사용 가능하도록 제한
    if interaction.channel.name != "가입신청":
        await interaction.response.send_message(
            "❌ 이 명령어는 #가입신청 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    invite = await interaction.channel.create_invite(
        max_age=INVITE_EXPIRY_HOURS * 3600,
        max_uses=2,
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
    invite_list = await member.guild.invites()
    filtered_invites = [invite for invite in invite_list if invite.uses == 1]
    log_channel = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
    for invite in filtered_invites:
        await invite.delete(reason="초대가 사용되었으므로 삭제.")
        if log_channel:
            await log_channel.send(f"👋 {member.mention}님이 {invite.url} 로 입장했습니다. 24시간 내 역할 없으면 추방됩니다.")

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
            if member and len(member.roles) >= 2:
                invite_guard.remove(user_id)
            if member and len(member.roles) <= 1 and now > expire_at:
                try:
                    await member.kick(reason="24시간 내 역할 미부여로 자동 추방")
                    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
                    if log_channel:
                        await log_channel.send(f"⛔️ {member.mention}님이 24시간 내 역할 미부여로 추방되었습니다.")
                except Exception as e:
                    print(f"추방 실패: {member} - {e}")
                invite_guard.remove(user_id)

bot.run(TOKEN)
