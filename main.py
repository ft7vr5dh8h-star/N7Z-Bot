import os
import discord
from discord import app_commands
from discord.ext import commands
from google import genai

# جلب التوكنات ومفاتيح البيئة من رايلواي
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("خطأ: لم يتم العثور على متغير البيئة DISCORD_TOKEN.")

if not GEMINI_API_KEY:
    raise ValueError("خطأ: لم يتم العثور على متغير البيئة GEMINI_API_KEY.")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

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

# ==========================================
# إعداد رتب الدعم الفني (بين 6 إلى 10 رتب)
# يمكنك وضع آيديات رتب الدعم الخاصة بك هنا مباشرة
# ==========================================
SUPPORT_ROLE_IDS = [
    1566259679473041489, # ضع آيدي رتبة الدعم 1 هنا
    1563683677819637782, # ضع آيدي رتبة الدعم 2 هنا
    1563682720436060241, # ضع آيدي رتبة الدعم 3 هنا
    1563693370436751441, # ضع آيدي رتبة الدعم 4 هنا
    1563693266120216619, # ضع آيدي رتبة الدعم 5 هنا
    1563683211266228374  # ضع آيدي رتبة الدعم 6 هنا (يمكنك إضافة حتى 10 رتب)
]

# قائمة خيارات الإدارة داخل التذكرة (مطابقة للصور التي أرفقتها)
class TicketManagementSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Close with Reason", description="Close the ticket with reason", emoji="🔒", value="close"),
            discord.SelectOption(label="Add User to Ticket", description="Add a user to the ticket", emoji="👥", value="add_user"),
            discord.SelectOption(label="Member PM Reminder", description="Send a PM reminder to the ticket creator", emoji="✉️", value="pm_reminder"),
            discord.SelectOption(label="Request Ticket Copy", description="Request a copy of the ticket", emoji="📋", value="ticket_copy"),
        ]
        super().__init__(placeholder="Choose a Ticket Action", min_values=1, max_values=1, options=options, custom_id="ticket_management_select")

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "close":
            await interaction.response.send_message("🔒 جاري إغلاق التذكرة...", ephemeral=True)
            await interaction.channel.delete(delay=3)
        elif val == "add_user":
            await interaction.response.send_message("👥 يرجى منشن العضو المراد إضافته للتذكرة.", ephemeral=True)
        elif val == "pm_reminder":
            await interaction.response.send_message("✉️ تم إرسال تذكير خاص لصاحب التذكرة.", ephemeral=True)
        elif val == "ticket_copy":
            await interaction.response.send_message("📋 جاري استخراج نسخة من السجلات...", ephemeral=True)

class TicketManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketManagementSelect())

# أزرار تحكم المشرفين داخل التذكرة (Ticket Options و Claim المطابقة للصورة)
class InsideTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket Options", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="ticket_options_btn")
    async def ticket_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎫 **Ticket Management**\n• Select an option from the dropdown menu below", view=TicketManagementView(), ephemeral=True)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="💼", custom_id="claim_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"💼 تم استلام التذكرة بواسطة: {interaction.user.mention}")

# أزرار لوحة التذاكر الرئيسية (5 أزرار)
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
        
        # منح الصلاحيات تلقائياً لصاحب رتبة Streamer / Administrator ورتب الدعم المحددة
        for role_id in SUPPORT_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

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
        
        # إرسال رسالة الترحيب داخل التذكرة مطابقة للصورة تماماً مع منشن فريق الدعم والأزرار الداخلية
        support_mentions = " ".join([f"<@&{rid}>" for rid in SUPPORT_ROLE_IDS if guild.get_role(rid)])
        welcome_text = f"{support_mentions} | 🎫 **TICKET STAFF**"
        
        embed = discord.Embed(
            title=f"تذكرة {ticket_type}",
            description=f"مرحباً {interaction.user.mention}! تم فتح التذكرة بنجاح. يرجى توضيح مشكلتك أو طلبك وسيتولى فريق العمل خدمتك.",
            color=0x2b2d31
        )
        await channel.send(content=welcome_text, embed=embed, view=InsideTicketView())

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
    bot.add_view(InsideTicketView())
    bot.add_view(TicketManagementView())
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


# 1. أمر إرسال لوحة التذاكر للروم المطلوب بالآيدي `1565981889045463051`
@bot.tree.command(name="setup-tickets", description="إرسال لوحة التذاكر إلى الروم المخصص بالصورة والأزرار الخمسة")
async def setup_tickets(interaction: discord.Interaction):
    if not check_admin_or_streamer(interaction):
        await interaction.response.send_message("❌ عذراً، هذا الأمر محمي ولا يملكه إلا حاملو رتبة **Streamer** أو المشرفين!", ephemeral=True)
        return

    target_channel_id = 1565981889045463051
    channel = bot.get_channel(target_channel_id)

    if channel:
        embed = discord.Embed(
            title="نظام تذاكر N7Z",
            description="اختر القسم المناسب أدناه لفتح تذكرة وسيقوم فريق العمل بمساعدتك في أسرع وقت.",
            color=0x2b2d31
        )
        embed.set_image(url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe") # ضع رابط صورتك المباشر هنا
        
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("✅ تم إرسال لوحة التذاكر إلى روم التذاكر المحدد بنجاح!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ لم يتم العثور على الروم بالآيدي المحدد (`1565981889045463051`)، تأكد من صحة الآيدي.", ephemeral=True)


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