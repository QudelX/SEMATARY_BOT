import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = ""

FONT_PATHS = [
    "font.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def load_font(size):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    lines = []
    words = text.split()
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip() if current_line else word
        if draw.textlength(test_line, font=font) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = ""

            if draw.textlength(word, font=font) > max_width:
                for char in word:
                    test_char = f"{current_line}{char}"
                    if draw.textlength(test_char, font=font) <= max_width:
                        current_line = test_char
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = char
            else:
                current_line = word

    if current_line:
        lines.append(current_line)
    return lines


def add_text(image_bytes, text):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    size = max(20, width // 10)
    max_text_width = width * 0.9
    max_text_height = height * 0.35

    while size > 12:
        font = load_font(size)
        lines = wrap_text(draw, text, font, max_text_width)

        total_text_height = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_h = bbox[3] - bbox[1] if bbox else size
            total_text_height += line_h + (size * 0.2)

        if total_text_height <= max_text_height:
            break
        size -= 2

    font = load_font(size)
    lines = wrap_text(draw, text, font, max_text_width)

    line_heights = []
    total_text_height = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1] if bbox else size
        line_heights.append(h)
        total_text_height += h

    spacing = size * 0.15
    total_text_height += spacing * (len(lines) - 1)

    y = height - total_text_height - (height * 0.05)

    for i, line in enumerate(lines):
        line_w = draw.textlength(line, font=font)
        x = (width - line_w) / 2

        draw.text(
            (x, y),
            line,
            font=font,
            fill="white",
            stroke_width=max(2, size // 10),
            stroke_fill="black",
        )
        y += line_heights[i] + spacing

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95)
    out.seek(0)
    return out


async def send_result(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str, text: str):
    try:
        tg_file = await context.bot.get_file(file_id)
        data = bytes(await tg_file.download_as_bytearray())
        processed_photo = add_text(data, text)
        await update.message.reply_photo(processed_photo)
    except Exception as e:
        await update.message.reply_text("Произошла ошибка при обработке изображения.")
        print(f"Ошибка: {e}", file=sys.stderr)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Пришли фото с подписью, и я напишу её на картинке. "
        "Или пришли фото без подписи, и я спрошу текст."
    )


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    caption = update.message.caption
    if caption:
        await send_result(update, context, photo.file_id, caption)
    else:
        context.user_data["photo_id"] = photo.file_id
        await update.message.reply_text("Теперь напиши текст для фотографии.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_id = context.user_data.pop("photo_id", None)
    if not photo_id:
        await update.message.reply_text("Сначала пришли фото.")
        return
    await send_result(update, context, photo_id, update.message.text)


def main():
    if not TOKEN:
        print("Ошибка: Переменная окружения BOT_TOKEN не установлена!", file=sys.stderr)
        sys.exit(1)

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Бот успешно запущен в режиме polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
