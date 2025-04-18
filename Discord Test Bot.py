import discord
import yt_dlp as youtube_dl
import logging
import os
import asyncio
from discord.ext import commands, tasks
import asyncio
from yt_dlp import YoutubeDL
import random
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = discord.Bot(intents=intents, auto_sync_commands=True)
intents.voice_states = True  # 음성 상태 이벤트 활성화
intents.messages = True


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

import random
from yt_dlp import YoutubeDL

RANDOM_KEYWORDS = [
    "pop-song", "k-pop", "케이팝", "팝송", "핫한 노래", "Hit song"
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
            # 30분 이하인 노래를 찾아서 재생생
            for entry in info['entries']:
                if entry['duration'] <= MAX_DURATION:
                    return entry['title'], entry['url']

        # 30분 이하의 노래가 없다면 첫 번째 노래 재생
        entry = info['entries'][0]
        return entry['title'], entry['url']
    
@bot.event
async def on_ready():
    print(f"{bot.user} 준비 완료!")
    try:
        synced = await bot.tree.sync()
        print(f"명령어 동기화 완료: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"명령어 동기화 실패: {e}")


# 퇴장 처리 추적 변수
is_disconnected = False

@bot.event
async def on_voice_state_update(member, before, after):
    global loop, queue, is_disconnected

    if member.id == bot.user.id:  # 봇 자신에 대해서만 처리
        if before.channel is not None and after.channel is None:  # 강제 퇴장된 경우
            if not is_disconnected:  # 퇴장이 이미 처리되지 않았으면
                print(f"⚠️ 봇이 강제로 음성 채널에서 끊겼습니다. before.channel: {before.channel}, after.channel: {after.channel}")
                loop = False
                queue.clear()

                # 음성 클라이언트가 존재하는지 확인하고 퇴장 처리
                if member.guild.voice_client:
                    await member.guild.voice_client.disconnect()
                    await member.guild.voice_client.cleanup()

                is_disconnected = True  # 퇴장 처리된 상태로 설정
                print("👋 봇이 음성 채널에서 퇴장했어요.")

        elif before.channel is None and after.channel is not None:  # 봇이 음성 채널에 입장한 경우
            if is_disconnected:
                is_disconnected = False  # 봇이 다시 음성 채널에 입장했으므로, 퇴장 상태 초기화

    elif member.guild.voice_client:  # 봇이 접속 중이고, 사용자가 음성 채널에 참여하거나 나갈 때
        vc = member.guild.voice_client

        # 혼자 남았을 경우 퇴장 처리
        if len(vc.channel.members) == 1 and not is_disconnected:  # 혼자 남았을 때만
            print("🚶‍♂️ 아무도 없어서 음성 채널에서 나갈게요.")
            loop = False
            queue.clear()

            # 음성 클라이언트가 존재하는지 확인하고 퇴장 처리
            if member.guild.voice_client:
                await vc.disconnect()
            is_disconnected = True
            print("👋 봇이 음성 채널에서 퇴장했어요.")
            return




# 퇴장 명령어
async def leave(ctx):
    global loop, is_disconnected
    loop = False  # 반복 끄기

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        is_disconnected = True  # 퇴장 처리 상태 업데이트
        print("👋 음성 채널에서 나갔어요! 반복 모드가 해제되었습니다.")
    else:
        print("⛔ 음성 채널에 있지 않아요!")

# 퇴장 처리 후 `is_disconnected` 초기화
@bot.event
async def on_ready():
    global is_disconnected
    is_disconnected = False


queue = []
loop = False  

#재생 명령어어
@bot.slash_command(name="재생", description="유튜브에서 노래를 검색해서 재생해요!")
async def play(ctx, search: str):
    await ctx.defer(ephemeral=True)  # ⬅️ 이걸 썼으니까, 아래는 followup으로 응답해야 돼

    if not ctx.author.voice:
        await ctx.followup.send("⛔ 먼저 음성 채널에 들어가 주세요!")
        return

    # 유튜브 링크 추출
    if "youtube.com" in search or "youtu.be" in search:
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(search, download=False)
            if not info:
                await ctx.followup.send("❌ 링크에서 정보를 찾을 수 없어요!")
                return

            url = info["url"]
            title = info["title"]
    else:
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(f"ytsearch:{search}", download=False)
            if not info["entries"]:
                await ctx.followup.send("❌ 검색 결과가 없어요!")
                return

            url = info["entries"][0]["url"]
            title = info["entries"][0]["title"]

    if not ctx.voice_client:
        vc = await ctx.author.voice.channel.connect()
    else:
        vc = ctx.voice_client

    queue.append((title, url))

    if not vc.is_playing():
        await play_song(ctx, vc)
        await ctx.followup.send(f"🎶 `{title}`을(를) 재생할게요!")  # ✅ followup.send 사용!
    else:
        await ctx.followup.send(f"📌 `{title}`을(를) 대기열에 추가했어요!")  # ✅ 여기도!
 


# 반복 모드를 켜는 명령어
@bot.slash_command(name="반복켜기", description="현재 노래를 반복 재생해요!")
async def repeat_on(ctx):
    global loop
    loop = True
    # 만약 이미 노래가 재생 중이라면, 반복을 즉시 적용
    if ctx.voice_client and ctx.voice_client.is_playing():
        await ctx.respond("🔁 반복 모드를 활성화했어요! 현재 노래가 반복 재생됩니다.", ephemeral=True)
    else:
        await ctx.respond("🔁 반복 모드를 활성화했어요!", ephemeral=True)

#반복 모드를 끄는 명령어어
@bot.slash_command(name="반복끄기", description="반복 재생을 해제해요!")
async def repeat_off(ctx):
    global loop
    loop = False  # 반복 비활성화

    if ctx.voice_client and ctx.voice_client.is_playing():
        await ctx.respond("⏹️ 반복 모드를 비활성화했어요! 현재 노래는 계속 재생되며, 끝난 후에는 반복되지 않아요.", ephemeral=True)
    else:
        await ctx.respond("⛔ 현재 재생 중인 노래가 없어요!", ephemeral=True)

    title, url = queue[0] if loop else queue.pop(0)

    if not vc.is_playing():
        def after_playback(error):
            if loop:
                fut = asyncio.run_coroutine_threadsafe(play_song(ctx, vc), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"오류 발생: {e}")
            else:
                fut = asyncio.run_coroutine_threadsafe(play_next(ctx, vc), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"오류 발생: {e}")

        if not ctx.voice_client:
            vc = await ctx.author.voice.channel.connect()
    else:
        vc = ctx.voice_client

    queue.append((title, url))

    vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=after_playback)
        

async def play_song(ctx, vc):
    global loop

    if not queue:
        # 대기열이 비었으면 무조건 추천곡 추가
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

        vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=after_playback)


async def play_next(ctx, vc):
    global loop

    if not queue:
        # 대기열이 비었으니 추천곡 재생생
        title, url = get_recommended_song()
        queue.append((title, url))

    if loop:
        title, url = queue[0]
    else:
        title, url = queue.pop(0)

    vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx, vc), bot.loop))



#노래를 스킵하는 명령어
@bot.slash_command(name="스킵", description="현재 노래를 건너뛰어요!")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.respond("⏭️ 다음 곡으로 넘어갈게요!", ephemeral=True)  # 응답을 ephemeral=True로 변경
    else:
        await ctx.respond("⛔ 현재 재생 중인 노래가 없어요!", ephemeral=True)  # 응답을 ephemeral=True 로 변경

#봇이 통화방에서 나가게하는 명령어
@bot.slash_command(name="퇴장", description="봇을 음성 채널에서 내보내요!")
async def leave(ctx):
    global loop
    loop = False  # 반복 끄기
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.respond("👋 음성 채널에서 나갔어요! 반복 모드가 해제되었습니다.", ephemeral=True)  # 응답을 ephemeral=True 로 변경
    else:
        await ctx.respond("⛔ 음성 채널에 있지 않아요!", ephemeral=True)   # 응답을 ephemeral=True 로 변경




# ffmpeg 경로 추가
os.environ["PATH"] += os.pathsep + "C:/ffmpeg/bin"  # ffmpeg 경로 추가


@bot.slash_command(name="help", description="사용 가능한 명령어 목록을 보여줘요!")
async def help_command(ctx):
    embed = discord.Embed(
        title="📌 제로 봇 명령어 도움말",
        description="사용 가능한 명령어 목록이에요!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎵 음악 관련 명령어",
        value=(
            "`/재생 [노래 제목 또는 유튜브 링크]` - 유튜브에서 노래를 검색해서 재생\n"
            "`/스킵` - 현재 노래를 건너뛰고 다음 곡 재생\n"
            "`/반복켜기` - 현재 노래를 반복 재생\n"
            "`/반복끄기` - 반복 재생 해제\n"
            "`/퇴장` - 봇을 음성 채널에서 내보내기\n \n"
            "***Last Update*** - ***4/12/2025*** "
            ),

        inline=False
    )

    embed.set_footer(text="\n 다양한 기능 추가 중입니다! \n"
                    "좋은 하루 되세요❤️"
                    )
    
    await ctx.respond(embed=embed, ephemeral=True)  # 사용자에게만 보이게 응


from dotenv import load_dotenv
import os


# 환경 변수에서 DISCORD_TOKEN 가져오기
TOKEN = os.getenv('discord_zero_bot_token')

# 토큰 확인
if TOKEN is None:
    print("토큰을 환경 변수에서 제대로 불러오지 못했습니다. .env 파일과 환경 변수 설정을 다시 확인해보세요.")
else:
    print("토큰을 제대로 불러왔습니다.")
    bot.run(TOKEN)