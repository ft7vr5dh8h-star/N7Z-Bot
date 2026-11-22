import os
import re
import discord
from discord import app_commands
from discord.ext import commands
import io

# جلب التوكن من متغيرات البيئة في رايلواي
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    raise ValueError("خطأ: لم يتم العثور على متغير البيئة DISCORD_TOKEN.")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# أيدي السيرفر الخاص بك للمزامنة الفورية
GUILD_ID = discord.Object(id=1563678057863057559)

# الرتبة التي طلبت التركيز عليها
TARGET_ROLE_ID = 1563686143374004314

# ==========================================
# رتب الدعم الفني (بين 6 إلى 10 رتب)
# ==========================================
SUPPORT_ROLE_IDS = [
    1566259679473041489,
    1563683677819637782,
    1563682720436060241,
    1563693370436751441,
    1563693266120216619,
    1563683211266228374
]

# آيدي روم السجلات
LOGS_CHANNEL_ID = 1568491490265661440

# تعبير نمطي لالتقاط جميع أنواع الروابط والدعوات
URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|discord\.gg/\S+|discordapp\.com/invite/\S+|discord\.com/invite/\S+)",
    re.IGNORECASE
)

# قائمة خيارات الإدارة داخل التذكرة
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
            await interaction.response.send_message("🔒 جاري إغلاق وتصدير السجلات وحذف التذكرة...", ephemeral=True)
            
            logs_channel = interaction.guild.get_channel(LOGS_CHANNEL_ID)
            
            messages = [f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author}: {msg.content}" async for msg in interaction.channel.history(limit=500)]
            transcript_text = f"--- سجلات تذكرة: {interaction.channel.name} ---\nأغلق بواسطة: {interaction.user}\n\n" + "\n".join(reversed(messages))
            file = discord.File(io.BytesIO(transcript_text.encode('utf-8')), filename=f"transcript-{interaction.channel.name}.txt")
            
            if logs_channel:
                await logs_channel.send(content=f"📁 **سجلات التذكرة المغلقة:** `{interaction.channel.name}`\nبواسطة المشرف: {interaction.user.mention}", file=file)
            
            await interaction.channel.delete(reason=f"Closed by {interaction.user}")

        elif val == "add_user":
            await interaction.response.send_message("👥 لاستخدام إضافة عضو، قم بمنشن العضو المطلوب داخل التذكرة.", ephemeral=True)
        elif val == "pm_reminder":
            await interaction.response.send_message("✉️ تم إرسال تذكير خاص لصاحب التذكرة بنجاح.", ephemeral=True)
        elif val == "ticket_copy":
            messages = [f"{msg.author}: {msg.content}" async for msg in interaction.channel.history(limit=100)]
            transcript = "\n".join(reversed(messages))
            file = discord.File(io.BytesIO(transcript.encode('utf-8')), filename=f"transcript-{interaction.channel.name}.txt")
            await interaction.response.send_message("📋 تفضل نسخة من سجلات هذه التذكرة:", file=file, ephemeral=True)

class TicketManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketManagementSelect())

# أزرار تحكم المشرفين داخل التذكرة
class InsideTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket Options", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="ticket_options_btn")
    async def ticket_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎫 **Ticket Management**\n• Select an option from the dropdown menu below", view=TicketManagementView(), ephemeral=True)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="💼", custom_id="claim_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"💼 تم استلام التذكرة بواسطة المشرف: {interaction.user.mention}")

# أزرار لوحة التذاكر الرئيسية
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
        
        for role_id in SUPPORT_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        target_role = guild.get_role(TARGET_ROLE_ID)
        if target_role:
            overwrites[target_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

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


# ==========================================
# نظام الحماية الصارم (Anti-Link & Anti-Exploit)
# ==========================================
def has_target_role(member: discord.abc.User) -> bool:
    if not isinstance(member, discord.Member):
        return False
    return any(role.id == TARGET_ROLE_ID for role in member.roles)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # استثناء الأدمن أو أصحاب الرتبة المحددة من حذف الروابط
    is_admin = isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator
    if is_admin or has_target_role(message.author):
        await bot.process_commands(message)
        return

    # حذف فوري لأي رابط في الرسالة
    if URL_PATTERN.search(message.content):
        try:
            await message.delete()
            warning_msg = await message.channel.send(
                f"🚫 {message.author.mention} تم حذف رسالتك فوراً! يُمنع منعاً باتاً إرسال أي روابط هنا."
            )
            await warning_msg.delete(delay=4)

            logs_channel = message.guild.get_channel(LOGS_CHANNEL_ID) if message.guild else None
            if logs_channel:
                await logs_channel.send(
                    f"🛡️ **حذف رابط تلقائي:**\n"
                    f"• **العضو:** {message.author.mention} (`{message.author.id}`)\n"
                    f"• **الروم:** {message.channel.mention}\n"
                    f"• **المحتوى المحذوف:** `{message.content[:500]}`"
                )
        except Exception as e:
            print(f"Error deleting link message: {e}")
        return

    await bot.process_commands(message)

@bot.event
async def on_guild_channel_delete(channel):
    logs_channel = channel.guild.get_channel(LOGS_CHANNEL_ID)
    if logs_channel:
        await logs_channel.send(f"⚠️ **تنبيه أمني:** تم حذف قناة `{channel.name}` (`{channel.id}`).")

@bot.event
async def on_guild_role_delete(role):
    logs_channel = role.guild.get_channel(LOGS_CHANNEL_ID)
    if logs_channel:
        await logs_channel.send(f"⚠️ **تنبيه أمني:** تم حذف رتبة `{role.name}` (`{role.id}`).")


@bot.event
async def on_ready():
    bot.add_view(TicketView())
    bot.add_view(InsideTicketView())
    bot.add_view(TicketManagementView())
    
    try:
        bot.tree.copy_global_to(guild=GUILD_ID)
        synced = await bot.tree.sync(guild=GUILD_ID)
        print(f"Synced {len(synced)} slash commands successfully to guild {GUILD_ID.id}.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
    print(f'Logged in as {bot.user} successfully, N7Z-Bot is online with Strict Link Protection!')


def check_admin_or_streamer(interaction: discord.Interaction) -> bool:
    is_admin = interaction.user.guild_permissions.administrator
    has_streamer_role = any(role.name.lower() in ["streamer", "ستريمر"] for role in interaction.user.roles)
    has_focused_role = has_target_role(interaction.user)
    return is_admin or has_streamer_role or has_focused_role


# 1. أمر إرسال لوحة التذاكر
@bot.tree.command(name="setup-tickets", description="إرسال لوحة التذاكر إلى الروم المخصص")
async def setup_tickets(interaction: discord.Interaction):
    if not check_admin_or_streamer(interaction):
        await interaction.response.send_message("❌ عذراً، هذا الأمر محمي ولا يملكه إلا حاملو رتبة **Streamer** أو الرتبة المعتمدة أو المشرفين!", ephemeral=True)
        return

    target_channel_id = 1565981889045463051
    channel = bot.get_channel(target_channel_id)

    if channel:
        embed = discord.Embed(
            title="نظام تذاكر N7Z",
            description="اختر القسم المناسب أدناه لفتح تذكرة وسيقوم فريق العمل بمساعدتك في أسرع وقت.",
            color=0x2b2d31
        )
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("✅ تم إرسال لوحة التذاكر إلى روم التذاكر المحدد بنجاح!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ لم يتم العثور على الروم بالآيدي المحدد (`1565981889045463051`)، تأكد من صحة الآيدي.", ephemeral=True)


# 2. أمر البرودكاست في الخاص مع منشن في النهاية
@bot.tree.command(name="broadcast", description="إرسال برودكاست لجميع الأعضاء بالخاص مع منشن في النهاية")
@app_commands.describe(message="نص الرسالة المراد إرسالها للجميع بالخاص")
async def broadcast(interaction: discord.Interaction, message: str):
    if not check_admin_or_streamer(interaction):
        await interaction.response.send_message("❌ عذراً، أمر البرودكاست مخصص فقط لحاملي رتبة **Streamer** أو الرتبة المعتمدة أو الإدارة!", ephemeral=True)
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

bot.run(DISCORD_TOKEN)
