from config_utils import read_config_file
import datetime
import asyncio

CONFIG = read_config_file()


async def send_morning_call(client, time_str, chat_gpt, yt_song):
    while True:
        now = datetime.datetime.now()
        target_time = datetime.datetime.strptime(time_str, "%H:%M")
        # 比對時間
        if now.hour == target_time.hour and now.minute == target_time.minute:
            morning_greeting = get_morning_greeting(
                now.weekday(), time_str, chat_gpt, yt_song
            )
            channel = client.get_channel(CONFIG.get("assistant_channel_id"))
            await channel.send(f"{morning_greeting}")
        # 暫停 1 分鐘
        await asyncio.sleep(60)


def get_morning_greeting(weekday, time_str, chat_gpt, yt_song):
    week_list = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    prompt = f"早安，現在時間是{week_list[weekday]}{time_str}，你可以給大家一個熱情且活力的招呼語嗎？請在五十字以內並"
    answer = chat_gpt.ask_question(prompt)
    song = yt_song.choose_one_song()
    morning_greeting = f"{answer}\n然後送上本日好歌精選給各位好虎粉\n{song}"
    return morning_greeting


def start_reminders(client, chat_gpt, yt_song):
    asyncio.ensure_future(send_morning_call(client, "7:30", chat_gpt, yt_song))
