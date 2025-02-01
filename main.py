import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 봇 설정
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

# 데이터 저장 경로
DATA_FILE = "product_links.json"

# 관리자 역할 ID 설정
ADMIN_ROLE_ID = 1332938650228490361  # 관리자 역할 ID로 변경
LOG_CHANNEL_ID = 1332938688467832914  # 로그를 보낼 채널 ID로 변경

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
            statuses = ["제품 지급", "제품 관리", "제품센터 관리"]  # 상태 메시지 리스트
            for status in statuses:
                await bot.change_presence(
                    status=discord.Status.online,  # 온라인 상태
                    activity=discord.Game(name=status)  # 상태 메시지 설정
                )
                await asyncio.sleep(10)  # 10초 대기

    bot.loop.create_task(change_status())  # 비동기 작업 추가

# 권한 체크 데코레이터
def admin_only(interaction: discord.Interaction):
    role_ids = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID in role_ids:
        return True
    return False

# /제품등록 명령어 (관리자 전용, 파일 업로드 지원)
@bot.tree.command(name="제품등록", description="새로운 제품을 등록합니다. (파일 업로드 지원, 관리자 전용)")
async def register_product(interaction: discord.Interaction, product_name: str, file: discord.Attachment = None):
    if not admin_only(interaction):
        embed = discord.Embed(
            title="권한 부족",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not file:
        embed = discord.Embed(
            title="파일 누락",
            description="제품 등록에는 파일이 필요합니다. 파일을 첨부해주세요.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # 저장 경로 설정
    upload_dir = "uploaded_products"
    os.makedirs(upload_dir, exist_ok=True)  # 디렉토리 생성
    file_path = os.path.join(upload_dir, f"{product_name}_{file.filename}")

    # 파일 다운로드 및 저장
    await file.save(file_path)

    # 제품 등록
    product_links[product_name] = file_path
    save_products()

    embed = discord.Embed(
        title="제품 등록 완료",
        description=f"제품 이름: {product_name}\n저장된 파일 경로: {file_path}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        log_embed = discord.Embed(
            title="제품 등록 로그",
            description=f"🛠️ {interaction.user}님이 {product_name} 제품을 등록했습니다.",
            color=discord.Color.blue()
        )
        await log_channel.send(embed=log_embed)

# /제품지급 (관리자 전용)
@bot.tree.command(name="제품지급", description="특정 유저에게 제품을 지급합니다. (관리자 전용)")
async def give_product(interaction: discord.Interaction, member: discord.Member, product_name: str):
    if not admin_only(interaction):
        return await interaction.response.send_message("🚫 권한이 없습니다.", ephemeral=True)

    await interaction.response.defer()

    file_path = product_links.get(product_name)
    if file_path and os.path.exists(file_path):
        try:
            embed = discord.Embed(title="구매 감사합니다.", description=f"{member.mention}님에게 '{product_name}' 제품이 지급되었습니다.", color=discord.Color.blue())
            message = await member.send(embed=embed)

            with open(file_path, "rb") as f:
                file_message = await member.send(file=discord.File(f, os.path.basename(file_path)))

            # 지급된 제품 메시지 저장
            if member.id not in product_messages:
                product_messages[member.id] = {}
            product_messages[member.id][product_name] = file_message.id

            await interaction.followup.send(f"✅ {member.mention}님에게 '{product_name}' 지급 완료!")

        except discord.Forbidden:
            await interaction.followup.send("🚫 해당 유저가 DM을 비활성화했습니다.")
    else:
        await interaction.followup.send("⚠ 제품을 찾을 수 없습니다.")

# /제품목록 명령어 (누구나 사용 가능)
@bot.tree.command(name="제품목록", description="등록된 모든 제품의 목록을 확인합니다.")
async def product_list(interaction: discord.Interaction):
    if product_links:
        embed = discord.Embed(
            title="등록된 제품 목록",
            description="\n".join([f"- {name}" for name in product_links.keys()]),
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            title="등록된 제품 없음",
            description="현재 등록된 제품이 없습니다.",
            color=discord.Color.red()
        )
    await interaction.response.send_message(embed=embed)

# /제품삭제 명령어 (관리자 전용)
@bot.tree.command(name="제품삭제", description="등록된 제품을 삭제합니다. (관리자 전용)")
async def delete_product(interaction: discord.Interaction, product_name: str):
    if not admin_only(interaction):
        embed = discord.Embed(
            title="권한 부족",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if product_name in product_links:
        # 파일 삭제
        file_path = product_links[product_name]
        if os.path.exists(file_path):
            os.remove(file_path)

        # 제품 목록에서 제거
        del product_links[product_name]
        save_products()

        embed = discord.Embed(
            title="제품 삭제 완료",
            description=f"제품 {product_name}이(가) 삭제되었습니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="제품 삭제 로그",
                description=f"🛠️ {interaction.user}님이 {product_name} 제품을 삭제했습니다.",
                color=discord.Color.blue()
            )
            await log_channel.send(embed=log_embed)
    else:
        embed = discord.Embed(
            title="제품 삭제 실패",
            description=f"'{product_name}'은(는) 등록되지 않은 제품입니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

# /지급취소 (관리자 전용)
@bot.tree.command(name="지급취소", description="특정 유저에게 지급된 제품을 취소합니다. (관리자 전용)")
async def cancel_give_product(interaction: discord.Interaction, member: discord.Member, product_name: str):
    if not admin_only(interaction):
        return await interaction.response.send_message("🚫 권한이 없습니다.", ephemeral=True)

    user_messages = product_messages.get(member.id, {})
    message_id = user_messages.get(product_name)

    if message_id:
        try:
            dm_channel = await member.create_dm()
            message = await dm_channel.fetch_message(message_id)
            await message.delete()  # 지급된 제품 메시지 삭제

            del user_messages[product_name]
            if not user_messages:
                del product_messages[member.id]

            await interaction.response.send_message(f"🚨 {member.mention}님의 {product_name} 지급이 취소되었습니다.")

            dm_embed = discord.Embed(title="제품 지급 취소", description=f"'{product_name}' 지급이 취소되었습니다.", color=discord.Color.red())
            await member.send(embed=dm_embed)

        except discord.NotFound:
            await interaction.response.send_message("⚠ 지급된 제품 메시지를 찾을 수 없습니다.")
    else:
        await interaction.response.send_message("⚠ 해당 유저에게 지급된 제품이 없습니다.")

# 봇 실행
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN:
    bot.run(TOKEN)
else:
    print("토큰이 설정되지 않았습니다. .env 파일을 확인하세요.")
