import os
import discord
from discord import app_commands
from discord.ext import commands
from google import genai
import io

# جلب التوكنات ومفاتيح البيئة من رايلواي
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("خطأ: لم يتم العثور على متغير البيئة DISCORD_TOKEN.")

if not GEMINI_API_KEY:
    raise ValueError("خطأ: لم يتم العثور على متغير البيئة GEMINI_API_KEY.")

# إعداد عميل Gemini الذكي
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# إرشادات النظام الأمنية والبرمجية
SYSTEM_INSTRUCTIONS = """
أنت مساعد ذكي ومخصص حصرياً لبوت ديسكورد (N7Z-Bot). مهامك وضوابطك هي:
1. الإجابة على الأسئلة العامة بدقة واحترافية عالية.
2. مساعدة المستخدمين في كتابة، شرح، وتصحيح أكواد بايثون (Python) وتطوير التطبيقات البرمجية.
3. [نظام الحماية والأمان]: يمنع منعاً باتاً تقديم أو توليد أو شرح أي أكواد أو أدوات تخص هجمات التعطيل (DDoS) أو الاختراق أو التخريب السيبراني.
"""

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# نظام أزرار التذاكر (5 أزرار بعد إزالة السجلات)
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        for role in guild.roles:
            if role.name.lower() in ["streamer", "ستريمر", "admin", "administrator", "مشرف", "إدارة"]:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="التذاكر")
        if not category:
            category = await guild.create_category("التذاكر")

        channel = await guild.create_text_channel(
            name=f"tkt-{ticket_type}-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)
        await channel.send(f"مرحباً {interaction.user.mention}! تم فتح تذكرة **{ticket_type}**. سيتولى فريق العمل الرد عليك قريباً.")

    @discord.ui.button(label="استفسار 🙋‍♂️", style=discord.ButtonStyle.primary, custom_id="tkt_inquiry")
    async def inquiry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "استفسار")

    @discord.ui.button(label="شراء 🛒", style=discord.ButtonStyle.secondary, custom_id="tkt_buy")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "شراء")

    @discord.ui.button(label="توثيق بنات ✔️", style=discord.ButtonStyle.success, custom_id="tkt_verify")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "توثيق-بنات")

    @discord.ui.button(label="طلب اونر 👑", style=discord.ButtonStyle.primary, custom_id="tkt_owner")
    async def owner_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "طلب-اونر")

    @discord.ui.button(label="شراكه 🤝", style=discord.ButtonStyle.blurple, custom_id="tkt_partnership")
    async def partnership_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "شراكه")


@bot.event
async def on_ready():
    bot.add_view(TicketView())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands successfully.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
    print(f'Logged in as {bot.user} successfully, N7Z-Bot is online!')


def check_admin_or_streamer(interaction: discord.Interaction) -> bool:
    is_admin = interaction.user.guild_permissions.administrator
    has_streamer_role = any(role.name.lower() in ["streamer", "ستريمر"] for role in interaction.user.roles)
    return is_admin or has_streamer_role


# 1. أمر إرسال لوحة التذاكر بالصورة المرفقة والآيدي الجديد
@bot.tree.command(name="setup-tickets", description="إرسال لوحة التذاكر إلى الروم المخصص بالصورة والأزرار الخمسة")
async def setup_tickets(interaction: discord.Interaction):
    if not check_admin_or_streamer(interaction):
        await interaction.response.send_message("❌ عذراً، هذا الأمر محمي ولا يملكه إلا حاملو رتبة **Streamer** أو المشرفين!", ephemeral=True)
        return

    # آيدي روم التذاكر الجديد الذي طلبته
    target_channel_id = 1565981889045463051
    channel = bot.get_channel(target_channel_id)

    if channel:
        # استخدام الصورة المرفقة مباشرة كملف مرسل مع الإمبد
        image_url = "https://cdn.discordapp.com/attachments/1234567890/image_2.png" # استبدل برابط الصورة المباشر أو استخدم الملف المرفق أدناه
        
        embed = discord.Embed(
            title="نظام تذاكر N7Z",
            description="اختر القسم المناسب أدناه لفتح تذكرة وسيقوم فريق العمل بمساعدتك في أسرع وقت.",
            color=0x2b2d31
        )
        
        # إرفاق الصورة التي أرسلتها في المحادثة مباشرة
        embed.set_image(url="attachment://n7z_banner.png")
        
        # تحميل الصورة المرفقة وإرسالها كملف داخل الرسالة لضمان ظهورها
        import urllib.request
        image_link = "https://raw.githubusercontent.com/..." # سيتم استخدام الصورة المحلية عبر discord.File
        
        # سنقوم بإرسالها مع الملف مباشرة لتظهر بدون مشاكل:
        # ملاحظة: قم برفع الصورة على ديسكورد وخذ رابطها المباشر أو استخدم الكود التالي:
        
        await interaction.response.send_message("⏳ جاري إرسال لوحة التذاكر...", ephemeral=True)
        
        # سنستخدم رابط الصورة المباشر أو ارفعها في روم وضع رابطها هنا:
        embed.set_image(url="https://media.discordapp.net/attachments/...") # ضع رابط صورتك المباشر هنا لضمان ظهورها
        
        await channel.send(embed=embed, view=TicketView())
        await interaction.edit_original_response(content="✅ تم إرسال لوحة التذاكر إلى الروم المحدد بالصورة والأزرار بنجاح!")
    else:
        await interaction.response.send_message("❌ لم يتم العثور على الروم بالآيدي المحدد (`1565981889045463051`)، تأكد من صحة الآيدي وتواجد البوت فيه.", ephemeral=True)


# 2. أمر البرودكاست في الخاص مع منشن في النهاية
@bot.tree.command(name="broadcast", description="إرسال برودكاست لجميع الأعضاء بالخاص مع منشن في النهاية")
@app_commands.describe(message="نص الرسالة المراد إرسالها للجميع بالخاص")
async def broadcast(interaction: discord.Interaction, message: str):
    if not check_admin_or_streamer(interaction):
        await interaction.response.send_message("❌ عذراً، أمر البرودكاست مخصص فقط لحاملي رتبة **Streamer** أو الإدارة!", ephemeral=True)
        return

    await interaction.response.send_message("⏳ جاري إرسال البرودكاست لجميع أعضاء السيرفر بالخاص...", ephemeral=True)

    success_count = 0
    fail_count = 0

    for member in interaction.guild.members:
        if member.bot:
            continue
        try:
            dm_text = f"{message}\n\n{member.mention}"
            await member.send(dm_text)
            success_count += 1
        except Exception:
            fail_count += 1

    await interaction.followup.send(f"✅ تم إرسال البرودكاست بنجاح!\n📤 تم الإرسال إلى: `{success_count}` عضو\n❌ فشل الإرسال (مغلق الخاص): `{fail_count}` عضو", ephemeral=True)


# 3. أمر الذكاء الاصطناعي /ai
@bot.tree.command(name="ai", description="طرح سؤال أو طلب مساعدة برمجية من Gemini الذكي")
@app_commands.describe(prompt="السؤال أو كود البايثون المراد شرحه أو الاستفسار عنه")
async def ai(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'system_instruction': SYSTEM_INSTRUCTIONS
            }
        )
        reply_text = response.text
        if len(reply_text) > 2000:
            for i in range(0, len(reply_text), 1900):
                await interaction.followup.send(reply_text[i:i+1900])
        else:
            await interaction.followup.send(reply_text)
    except Exception as e:
        print(f"Error connecting to Gemini: {e}")
        await interaction.followup.send("عذراً، حدث خطأ أثناء الاتصال بنظام الذكاء الاصطناعي.")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message):
        user_message = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
        if not user_message:
            await message.channel.send("أهلاً بك! يمكنك استخدام الأمر `/ai` أو كتابة سؤالك هنا.")
            return

        async with message.channel.typing():
            try:
                response = ai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_message,
                    config={
                        'system_instruction': SYSTEM_INSTRUCTIONS
                    }
                )
                reply_text = response.text
                if len(reply_text) > 2000:
                    for i in range(0, len(reply_text), 1900):
                        await message.channel.send(reply_text[i:i+1900])
                else:
                    await message.channel.send(reply_text)
            except Exception as e:
                print(f"Error: {e}")
                await message.channel.send("عذراً، حدث خطأ أثناء الاتصال بالذكاء الاصطناعي.")

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
