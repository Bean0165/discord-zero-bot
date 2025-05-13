import nextcord
from nextcord.ext import commands, tasks
import yt_dlp as youtube_dl
import logging
import os
import asyncio
from yt_dlp import YoutubeDL
import random
from dotenv import load_dotenv

intents = nextcord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.voice_states = True 
intents.messages = True
intents.presences = True 
bot = commands.Bot(command_prefix="!", intents=intents)

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'default_search': 'ytsearch',
    'noplaylist': True,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

RANDOM_KEYWORDS = [
    "calm pop song", "relaxing pop music", "soft pop", "chill pop", "acoustic pop",
    "calm k-pop", "slow k-pop", "soft k-pop", "ballad k-pop", "acoustic k-pop"
]
MAX_DURATION = 1800  # 30분

def get_recommended_song():
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
    }

    keyword = random.choice(RANDOM_KEYWORDS)
    query = f"ytsearch:{keyword}"

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)

        if 'entries' in info:
        
            for entry in info['entries']:
                if entry['duration'] <= MAX_DURATION:
                    return entry['title'], entry['url']

        entry = info['entries'][0]
        return entry['title'], entry['url']

@bot.event
async def on_ready():
    global is_disconnected
    is_disconnected = False  # 상태 변경 플래그
    check_reminder.start()
    # 상태 설정
    await bot.change_presence(status=nextcord.Status.online,
                    activity=nextcord.Game("빈이한테 학대 당하는 중...")
    )
    print(f"{bot.user} 준비 완료!")

is_disconnected = False

@bot.event
async def on_voice_state_update(member, before, after):
    global loop, queue, is_disconnected

    if member.id == bot.user.id:  
        if before.channel is not None and after.channel is None: 
            if not is_disconnected:  
                print(f"⚠️ 봇이 강제로 음성 채널에서 끊겼습니다. before.channel: {before.channel}, after.channel: {after.channel}")
                loop = False
                queue.clear()

                if member.guild.voice_client:
                    await member.guild.voice_client.disconnect()
                    await member.guild.voice_client.cleanup()

                is_disconnected = True  
                print("👋 봇이 음성 채널에서 퇴장했어요.")

        elif before.channel is None and after.channel is not None:  
            if is_disconnected:
                is_disconnected = False 

    elif member.guild.voice_client:  
        vc = member.guild.voice_client

        if len(vc.channel.members) == 1 and not is_disconnected:  
            print("🚶‍♂️ 아무도 없어서 음성 채널에서 나갈게요.")
            loop = False
            queue.clear()
        
            if member.guild.voice_client:
                await vc.disconnect()
            is_disconnected = True
            print("👋 봇이 음성 채널에서 퇴장했어요.")
            return

async def leave(ctx):
    global loop, is_disconnected
    loop = False 

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        is_disconnected = True 
        print("👋 음성 채널에서 나갔어요! 반복 모드가 해제되었습니다.")
    else:
        print("⛔ 음성 채널에 있지 않아요!")

queue = []
loop = False

@bot.slash_command(name="재생", description="유튜브에서 노래를 검색해서 재생해요!")
async def play(interaction, search: str):
    if not interaction.user.voice:
        await interaction.response.send_message("⛔ 먼저 음성 채널에 들어가 주세요!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        if not interaction.guild.voice_client:
            vc = await interaction.user.voice.channel.connect()
        else:
            vc = interaction.guild.voice_client

        if "youtube.com" in search or "youtu.be" in search:
            with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(search, download=False)
                if not info:
                    await interaction.followup.send("❌ 링크에서 정보를 찾을 수 없어요!")
                    return

                url = info["url"]
                title = info["title"]
        else:
            with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(f"ytsearch:{search}", download=False)
                if not info["entries"]:
                    await interaction.followup.send("❌ 검색 결과가 없어요!")
                    return

                url = info["entries"][0]["url"]
                title = info["entries"][0]["title"]

        queue.append((title, url))

        if not vc.is_playing():
            await play_song(interaction, vc)
            await interaction.followup.send(f"🎶 `{title}`을(를) 재생 중입니다!")

    except Exception as e:
        await interaction.followup.send(f"❌ 오류가 발생했어요: {str(e)}")

@bot.slash_command(name="반복켜기", description="현재 노래를 반복 재생해요!")
async def repeat_on(interaction):
    global loop
    loop = True

    vc = interaction.guild.voice_client 
    if vc and vc.is_playing():
        await interaction.response.send_message("🔁 반복 모드를 활성화했어요! 현재 노래가 반복 재생됩니다.", ephemeral=True)
    else:
        await interaction.response.send_message("🔁 반복 모드를 활성화했어요!", ephemeral=True)

@bot.slash_command(name="반복끄기", description="반복 재생을 해제해요!")
async def repeat_off(interaction):
    global loop
    loop = False  # ---> 반복 비활성화

    vc = interaction.guild.voice_client 

    if vc and vc.is_playing():
        await interaction.response.send_message("⏹️ 반복 모드를 비활성화했어요! 현재 노래는 계속 재생되며, 끝난 후에는 반복되지 않아요.", ephemeral=True)
    else:
        await interaction.response.send_message("⛔ 현재 재생 중인 노래가 없어요!", ephemeral=True)

    title, url = queue[0] if loop else queue.pop(0)

    if not vc.is_playing():
        def after_playback(error):
            if loop:
                fut = asyncio.run_coroutine_threadsafe(play_song(interaction, vc), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"오류 발생: {e}")
            else:
                fut = asyncio.run_coroutine_threadsafe(play_next(interaction, vc), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"오류 발생: {e}")

        vc.play(nextcord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=after_playback)

async def play_song(ctx, vc):
    global loop

    if not queue:
        title, url = get_recommended_song()
        queue.append((title, url))

    title, url = queue[0] if loop else queue.pop(0)

    if not vc.is_playing():
        def after_playback(error):
            if loop:
                queue.append((title, url))
                fut = asyncio.run_coroutine_threadsafe(play_song(ctx, vc), bot.loop)
            else:
                fut = asyncio.run_coroutine_threadsafe(play_next(ctx, vc), bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"오류 발생: {e}")

        vc.play(nextcord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=after_playback)

async def play_next(ctx, vc):
    global loop

    if not queue:
        title, url = get_recommended_song()
        queue.append((title, url))

    if loop:
        title, url = queue[0]
    else:
        title, url = queue.pop(0)

    vc.play(nextcord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx, vc), bot.loop))

@bot.slash_command(name="스킵", description="현재 노래를 건너뛰어요!")
async def skip(ctx):
    await ctx.response.defer(ephemeral=True)  

    voice = ctx.guild.voice_client

    if voice and voice.is_playing():
        voice.stop()

        await asyncio.sleep(1.5) 

        title, url = get_recommended_song()
        queue.clear()
        queue.append((title, url))

        await play_song(ctx, voice)
        await ctx.followup.send(f"⏭️ 다음 곡으로 넘어갈게요! `{title}`")
    else:
        await ctx.followup.send("⛔ 현재 재생 중인 노래가 없어요!")

@bot.slash_command(name="퇴장", description="봇을 음성 채널에서 내보내요!")
async def leave(interaction):
    global loop
    loop = False  
    
 
    await interaction.response.defer(ephemeral=True)
    
    voice_client = interaction.guild.voice_client
    
    if voice_client:
        await voice_client.disconnect()
        await interaction.followup.send("👋 음성 채널에서 나갔어요!")
    else:
        await interaction.followup.send("⛔ 음성 채널에 있지 않아요!")

import datetime
import time
from nextcord import SlashOption


reminder_list = []

@tasks.loop(seconds=10)
async def check_reminder():
    current_time = datetime.datetime.now().strftime("%H:%M")
    for user_id, channel_id, formatted_time, target_user_id in reminder_list.copy():
        if current_time == formatted_time:
            hour, minute = map(int, formatted_time.split(":"))
            if hour == 0:
                display_hour = 12
                period = "오전"
            elif hour < 12:
                display_hour = hour
                period = "오전"
            elif hour == 12:
                display_hour = 12
                period = "오후"
            else:
                display_hour = hour - 12
                period = "오후"

            display_time = f"{period} {display_hour}:{minute:02}"

            target_user = await bot.fetch_user(target_user_id)
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(
                    f"{target_user.mention} 알림 시간입니다! `{display_time}`에 설정한 알림입니다!"
                )
            reminder_list.remove((user_id, channel_id, formatted_time, target_user_id))

@bot.slash_command(name="timer", description="지정한 시간에 멘션을 보내는 명령어(예: 오후 5:12)")
async def timer(
    interaction: nextcord.Interaction,
    am_pm: str = SlashOption(
        name="am_pm",
        description="AM or PM selection",
        choices=["AM", "PM"] 
    ),
    time: str = SlashOption(
        name="time",  
        description="H:M (예: 1:21, 12:40)"
    ),
    mention: nextcord.Member = SlashOption(
        name="mention", 
        description="알림을 받을 유저를 선택하세요"
    )
):
    try:
        hour, minute = map(int, time.split(":"))

        if hour < 1 or hour > 12 or minute < 0 or minute > 59:
            raise ValueError("잘못된 시간 형식입니다.")

        if am_pm == "AM" and hour == 12:
            hour = 0  
        elif am_pm == "PM" and hour != 12:
            hour += 12

        compare_time = f"{hour:02}:{minute:02}"
        formatted_time = f"{'오전' if am_pm == 'AM' else '오후'} {hour % 12 if hour % 12 != 0 else 12}:{minute:02}"

        reminder_list.append((interaction.user.id, interaction.channel.id, compare_time, mention.id))

        await interaction.response.send_message(
            f"{interaction.user.mention}님, `{formatted_time}`에 {mention.mention}님에게 알림을 보냅니다!"
        )

    except ValueError:
        await interaction.response.send_message("올바른 시간을 입력해주세요. (예: 오전 10:30, 오후 3:45)")

from nextcord import Interaction

@bot.slash_command(name="setup", description="음성 채널 자동 생성 시스템을 셋업합니다.")
async def setup_voice_creator(interaction: nextcord.Interaction):
    guild = interaction.guild

    category = nextcord.utils.get(guild.categories, name="Create channel")
    if not category:
        category = await guild.create_category("Create channel")

    existing_channel = nextcord.utils.get(category.voice_channels, name="➕ Create")
    if not existing_channel:
        await guild.create_voice_channel("➕ Create", category=category)

    await interaction.response.send_message("✅ 자동 채널 시스템이 셋업되었습니다!", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.name == "➕ Create":
        category = after.channel.category

        existing = nextcord.utils.get(category.voice_channels, name=f"{member.name}'s Room")
        if existing:
            await existing.delete()
        
        overwrites = {
            member.guild.default_role: nextcord.PermissionOverwrite(
                view_channel=True, connect=True
            ),
            member: nextcord.PermissionOverwrite(
                view_channel=True, connect=True, manage_channels=True
            )
        }

        new_channel = await member.guild.create_voice_channel(
            name=f"{member.name}'s Room",
            category=category,
            overwrites=overwrites
        )

        await member.move_to(new_channel)

        await auto_delete_when_empty(new_channel)

async def auto_delete_when_empty(channel):
    await asyncio.sleep(2)  # 10초 뒤 확인
    if len(channel.members) == 0:
        await channel.delete()


#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------





@bot.slash_command(name="help", description="사용 가능한 명령어 목록을 보여줘요!")
async def help_command(ctx):
    embed = nextcord.Embed(
        title="📌 제로 봇 명령어 도움말",
        description="사용 가능한 명령어 목록이에요!",
        color=nextcord.Color.blue()
    )

    embed.add_field(
        name="🎵 음악 관련 명령어",
        value=(
            "`/재생 [노래 제목 또는 유튜브 링크]` - 유튜브에서 노래를 검색해서 재생\n"
            "`/스킵` - 현재 노래를 건너뛰고 다음 곡 재생\n"
            "`/반복켜기` - 현재 노래를 반복 재생\n"
            "`/반복끄기` - 반복 재생 해제\n"
            "`/퇴장` - 봇을 음성 채널에서 내보내기\n "
            "`/timer` - 지정한 시간에 멘션을 보내는 명령어 (예: /timer 17:30 @유저)\n \n"
            "***Last Update*** - ***4/20/2025*** "
            ),

        inline=False
    )

    embed.set_footer(text="\n 다양한 기능 추가 중입니다! \n"
                    "좋은 하루 되세요❤️" 
                    )
    
    await ctx.respond(embed=embed, ephemeral=True) 

from dotenv import load_dotenv
import os

TOKEN = os.getenv('discord_zero_bot_token')

if TOKEN is None:
    print("토큰을 환경 변수에서 제대로 불러오지 못했습니다. .env 파일과 환경 변수 설정을 다시 확인해보세요.")
else:
    print("토큰을 제대로 불러왔습니다.")
    bot.run(TOKEN)
else:
    print("토큰을 제대로 불러왔습니다.")
    bot.run(TOKEN)
