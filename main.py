import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio

# 봇 설정
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

# 하드코딩된 설정값
TOKEN = "MTMzMjY5OTI3Mzk4ODQxMTQ2Mg.Gm2K9q.FxdLFGoZgfsKk8xVmmjjmhcNKRR_LhPbxyJEdo"  # 여기에 디스코드 봇 토큰 입력
ADMIN_ROLE_ID = 1332938650228490361  # 관리자 역할 ID
LOG_CHANNEL_ID = 1332938688467832914  # 로그 채널 ID
DATA_FILE = "product_links.json"

# 제품 목록 로드 함수
def load_products():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# 제품 목록 저장 함수
def save_products():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(product_links, f, ensure_ascii=False, indent=4)

# 제품 목록 불러오기
product_links = load_products()

# 지급된 메시지를 추적하는 전역 변수
product_messages = {}  # {user_id: {product_name: message_id}}

@bot.event
async def on_ready():
    print(f'봇이 로그인되었습니다. {bot.user}')
    await bot.tree.sync()  # 슬래시 명령어 동기화

    async def change_status():
        while True:
            statuses = ["제품 지급", "제품 관리", "제품센터 관리"]
            for status in statuses:
                await bot.change_presence(
                    status=discord.Status.online,
                    activity=discord.Game(name=status)
                )
                await asyncio.sleep(10)

    bot.loop.create_task(change_status())

# 권한 체크 함수
def is_admin(interaction: discord.Interaction):
    return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)

# /제품등록 명령어 (관리자 전용, 파일 업로드 지원)
@bot.tree.command(name="제품등록", description="새로운 제품을 등록합니다. (파일 업로드 지원, 관리자 전용)")
async def register_product(interaction: discord.Interaction, product_name: str, file: discord.Attachment = None):
    if not is_admin(interaction):
        return await interaction.response.send_message("🚫 관리자만 사용할 수 있습니다.", ephemeral=True)

    if not file:
        return await interaction.response.send_message("⚠ 파일을 첨부해주세요.", ephemeral=True)

    upload_dir = "uploaded_products"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{product_name}_{file.filename}")

    await file.save(file_path)

    product_links[product_name] = file_path
    save_products()

    embed = discord.Embed(
        title="✅ 제품 등록 완료",
        description=f"**제품 이름**: `{product_name}`\n**저장 경로**: `{file_path}`",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        log_embed = discord.Embed(
            title="📌 제품 등록 로그",
            description=f"🛠️ {interaction.user.mention}님이 `{product_name}` 제품을 등록했습니다.",
            color=discord.Color.blue()
        )
        await log_channel.send(embed=log_embed)

# /제품지급 (관리자 전용)
@bot.tree.command(name="제품지급", description="특정 유저에게 제품을 지급합니다. (관리자 전용)")
async def give_product(interaction: discord.Interaction, member: discord.Member, product_name: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("🚫 관리자만 사용할 수 있습니다.", ephemeral=True)

    await interaction.response.defer()

    file_path = product_links.get(product_name)
    if file_path and os.path.exists(file_path):
        try:
            embed = discord.Embed(title="📦 제품 지급", description=f"{member.mention}님에게 `{product_name}` 제품이 지급되었습니다.", color=discord.Color.blue())
            message = await member.send(embed=embed)

            with open(file_path, "rb") as f:
                file_message = await member.send(file=discord.File(f, os.path.basename(file_path)))

            product_messages.setdefault(member.id, {})[product_name] = file_message.id

            await interaction.followup.send(f"✅ {member.mention}님에게 `{product_name}` 지급 완료!")

        except discord.Forbidden:
            await interaction.followup.send("🚫 해당 유저가 DM을 비활성화했습니다.")
    else:
        await interaction.followup.send("⚠ 제품을 찾을 수 없습니다.")

# /제품목록 명령어
@bot.tree.command(name="제품목록", description="등록된 모든 제품의 목록을 확인합니다.")
async def product_list(interaction: discord.Interaction):
    if product_links:
        embed = discord.Embed(
            title="📜 등록된 제품 목록",
            description="\n".join([f"- `{name}`" for name in product_links.keys()]),
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            title="❌ 등록된 제품 없음",
            description="현재 등록된 제품이 없습니다.",
            color=discord.Color.red()
        )
    await interaction.response.send_message(embed=embed)

# /제품삭제 명령어 (관리자 전용)
@bot.tree.command(name="제품삭제", description="등록된 제품을 삭제합니다. (관리자 전용)")
async def delete_product(interaction: discord.Interaction, product_name: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("🚫 관리자만 사용할 수 있습니다.", ephemeral=True)

    if product_name in product_links:
        file_path = product_links.pop(product_name, None)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        save_products()

        embed = discord.Embed(
            title="🗑️ 제품 삭제 완료",
            description=f"✅ `{product_name}` 삭제됨",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🛑 제품 삭제 로그",
                description=f"🛠️ {interaction.user.mention}님이 `{product_name}` 제품을 삭제했습니다.",
                color=discord.Color.blue()
            )
            await log_channel.send(embed=log_embed)
    else:
        await interaction.response.send_message("⚠ 등록되지 않은 제품입니다.")

# /지급취소 (관리자 전용)
@bot.tree.command(name="지급취소", description="특정 유저에게 지급된 제품을 취소합니다. (관리자 전용)")
async def cancel_give_product(interaction: discord.Interaction, member: discord.Member, product_name: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("🚫 관리자만 사용할 수 있습니다.", ephemeral=True)

    user_messages = product_messages.get(member.id, {})
    message_id = user_messages.get(product_name)

    if message_id:
        try:
            dm_channel = await member.create_dm()
            message = await dm_channel.fetch_message(message_id)
            await message.delete()

            del user_messages[product_name]
            if not user_messages:
                del product_messages[member.id]

            await interaction.response.send_message(f"🚨 {member.mention}님의 `{product_name}` 지급이 취소되었습니다.")

            dm_embed = discord.Embed(title="❌ 제품 지급 취소", description=f"`{product_name}` 지급이 취소되었습니다.", color=discord.Color.red())
            await member.send(embed=dm_embed)

        except discord.NotFound:
            await interaction.response.send_message("⚠ 지급된 제품 메시지를 찾을 수 없습니다.")
    else:
        await interaction.response.send_message("⚠ 해당 유저에게 지급된 제품이 없습니다.")

# 봇 실행
bot.run(TOKEN)
