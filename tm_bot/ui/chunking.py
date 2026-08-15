"""Discord 訊息長度限制的處理。"""

# Discord 單則訊息上限 2000 字，留一點餘裕給 mention 與換行
CHUNK_SIZE = 1900


async def send_in_chunks(channel, content, chunk_size=CHUNK_SIZE, reply_to=None):
    """超過長度上限就分段送出。

    reply_to 指定時，第一段以「回覆」形式呈現（多人頻道中對話脈絡更清楚）。
    """
    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        if reply_to is not None and i == 0:
            await reply_to.reply(chunk)
        else:
            await channel.send(chunk)
