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

# ==========================================
# إعدادات التذاكر واللوق
# ==========================================
SUPPORT_ROLE_IDS = [
    1566259679473041489,
    1563683677819637782,
    1563682720436060241,
    1563693370436751441,
    1563693266120216619,
    1563683211266228374
]

LOGS_CHANNEL_ID = 1568491490265661440

# ==========================================
# إعدادات التقديم (بنات / عيال)
# ==========================================
GIRLS_PANEL_CHANNEL_ID = 1565981859748257892
GIRLS_LOGS_CHANNEL_ID = 1566594318393675806

BOYS_PANEL_CHANNEL_ID = 1565981856598597634
BOYS_LOGS_CHANNEL_ID = 1566594185182576681

REVIEWER_ROLE_ID = 1574877821623472249


def can_review_application(member: discord.abc.User) -> bool:
    if not isinstance(member, discord.Member):
        return False
    return member.guild_permissions.administrator or any(r.id == REVIEWER_ROLE_ID for r in member.roles)


async def get_and_increment_ticket_number(guild: discord.Guild) -> int:
    max_num = 0
    logs_channel = guild.get_channel(LOGS_CHANNEL_ID)

    if logs_channel and logs_channel.topic:
        topic_match = re.search(r"TICKET_COUNTER:(\d+)", logs_channel.topic)
        if topic_match:
            max_num = max(max_num, int(topic_match.group(1)))

    for channel in guild.text_channels:
        match = re.search(r"(?:・|-)(\d+)$", channel.name)
        if match:
            max_num = max(max_num, int(match.group(1)))

    if logs_channel and max_num == 0:
        try:
            async for msg in logs_channel.history(limit=30):
                msg_match = re.search(r"🎟️・(\d+)", msg.content)
                if msg_match:
                    max_num = max(max_num, int(msg_match.group(1)))
        except Exception:
            pass

    next_num = max_num + 1

    if logs_channel:
        try:
            current_topic = logs_channel.topic or ""
            if "TICKET_COUNTER:" in current_topic:
                new_topic = re.sub(r"TICKET_COUNTER:\d+", f"TICKET_COUNTER:{next_num}", current_topic)
            else:
                new_topic = f"{current_topic} | TICKET_COUNTER:{next_num}".strip(" |")
            await logs_channel.edit(topic=new_topic)
        except Exception as e:
            print(f"Could not update logs channel topic counter: {e}")

    return next_num


# ==========================================
# نظام التقديم (Modal + أزرار القبول والرفض)
# ==========================================
class ApplicationDecisionView(discord.ui.View):
    def __init__(self, applicant_id: int = 0, category_label: str = ""):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.category_label = category_label

    async def handle_decision(self, interaction: discord.Interaction, accepted: bool):
        if not can_review_application(interaction.user):
            await interaction.response.send_message("❌ عذراً، القبول والرفض مخصص للرتبة المعتمدة فقط!", ephemeral=True)
            return

        # استخراج أيدي المقدم من الإيمبد لضمان عمل الأزرار حتى لو أعيد تشغيل البوت
        applicant_id = self.applicant_id
        original_embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if not applicant_id and original_embed and original_embed.description:
            id_match = re.search(r"`(\d+)`", original_embed.description)
            if id_match:
                applicant_id = int(id_match.group(1))

        status_text = "✅ مقبول" if accepted else "❌ مرفوض"
        embed_color = discord.Color.green() if accepted else discord.Color.red()

        if original_embed:
            updated_embed = original_embed.copy()
            updated_embed.color = embed_color
            updated_embed.add_field(name="الحالة", value=f"{status_text} بواسطة {interaction.user.mention}", inline=False)
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            await interaction.response.edit_message(embed=updated_embed, view=self)
        else:
            await interaction.response.send_message(f"تم التحديث إلى: {status_text}", ephemeral=True)

        # إرسال رسالة خاصة للشخص المقدم فقط مع منشن له
        if applicant_id:
            try:
                user = await bot.fetch_user(applicant_id)
                if user:
                    if accepted:
                        dm_msg = f"تم قبولك في سيرفر N7Z يا وحش فك تكت عشان تستلم رولك {user.mention}"
                    else:
                        dm_msg = f"تم رفضك من سيرفر N7Z {user.mention}"
                    await user.send(dm_msg)
            except Exception as e:
                print(f"Could not send DM to applicant {applicant_id}: {e}")

    @discord.ui.button(label="قبول", style=discord.ButtonStyle.success, emoji="✅", custom_id="app_accept_btn")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_decision(interaction, accepted=True)

    @discord.ui.button(label="رفض", style=discord.ButtonStyle.danger, emoji="❌", custom_id="app_reject_btn")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_decision(interaction, accepted=False)


class ApplicationModal(discord.ui.Modal):
    def __init__(self, category_label: str, logs_channel_id: int):
        super().__init__(title="Application Form")
        self.category_label = category_label
        self.logs_channel_id = logs_channel_id

        self.name_input = discord.ui.TextInput(
            label="اسمك",
            placeholder="اكتب اسمك...",
            required=True,
            max_length=100
        )
        self.age_input = discord.ui.TextInput(
            label="عمرك",
            placeholder="اكتب عمرك...",
            required=True,
            max_length=20
        )
        self.activity_q_input = discord.ui.TextInput(
            label="هل بتتفاعل في السيرفر",
            placeholder="نعم / لا مع توضيح...",
            required=True,
            max_length=200
        )
        self.experience_input = discord.ui.TextInput(
            label="خبراتك",
            placeholder="اذكر خبراتك السابقة...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.hours_input = discord.ui.TextInput(
            label="كم ساعات نشاطك",
            placeholder="مثال: 4 - 6 ساعات يومياً...",
            required=True,
            max_length=100
        )

        self.add_item(self.name_input)
        self.add_item(self.age_input)
        self.add_item(self.activity_q_input)
        self.add_item(self.experience_input)
        self.add_item(self.hours_input)

    async def on_submit(self, interaction: discord.Interaction):
        logs_channel = interaction.guild.get_channel(self.logs_channel_id)
        if not logs_channel:
            await interaction.response.send_message("❌ لم يتم العثور على روم السجلات المخصص!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 تقديم جديد — {self.category_label}",
            description=f"**المقدم:** {interaction.user.mention} (`{interaction.user.id}`)",
            color=0x2b2d31
        )
        embed.add_field(name="الاسم", value=self.name_input.value, inline=True)
        embed.add_field(name="العمر", value=self.age_input.value, inline=True)
        embed.add_field(name="ساعات النشاط", value=self.hours_input.value, inline=True)
        embed.add_field(name="هل بتتفاعل في السيرفر", value=self.activity_q_input.value, inline=False)
        embed.add_field(name="خبراتك", value=self.experience_input.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        view = ApplicationDecisionView(applicant_id=interaction.user.id, category_label=self.category_label)
        await logs_channel.send(content=f"<@&{REVIEWER_ROLE_ID}>", embed=embed, view=view)
        await interaction.response.send_message("✅ تم إرسال تقديمك بنجاح إلى الإدارة، سيتم مراجعته قريباً.", ephemeral=True)


class ApplyPanelView(discord.ui.View):
    def __init__(self, category_label: str, logs_channel_id: int, custom_id_prefix: str):
        super().__init__(timeout=None)
        self.category_label = category_label
        self.logs_channel_id = logs_channel_id

        apply_btn = discord.ui.Button(
            label="Apply",
            style=discord.ButtonStyle.primary,
            emoji="📝",
            custom_id=f"{custom_id_prefix}_apply_btn"
        )
        apply_btn.callback = self.on_apply_click
        self.add_item(apply_btn)

    async def on_apply_click(self, interaction: discord.Interaction):
        modal = ApplicationModal(category_label=self.category_label, logs_channel_id=self.logs_channel_id)
        await interaction.response.send_modal(modal)


# ==========================================
# نظام التذاكر
# ==========================================
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


class InsideTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket Options", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="ticket_options_btn")
    async def ticket_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎫 **Ticket Management**\n• Select an option from the dropdown menu below", view=TicketManagementView(), ephemeral=True)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="💼", custom_id="claim_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"💼 تم استلام التذكرة بواسطة المشرف: {interaction.user.mention}")


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

        for role in guild.roles:
            if role.name.lower() in ["streamer", "ستريمر", "admin", "administrator", "مشرف", "إدارة"]:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="التذاكر")
        if not category:
            category = await guild.create_category("التذاكر")

        ticket_number = await get_and_increment_ticket_number(guild)

        channel = await guild.create_text_channel(
            name=f"🎟️・{ticket_number}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)
        support_mentions = " ".join([f"<@&{rid}>" for rid in SUPPORT_ROLE_IDS if guild.get_role(rid)])
        welcome_text = f"{support_mentions} | 🎫 **TICKET STAFF**"

        embed = discord.Embed(
            title=f"تذكرة {ticket_type} #{ticket_number}",
            description=f"مرحباً {interaction.user.mention}! تم فتح التذكرة رقم **{ticket_number}** بنجاح. يرجى توضيح مشكلتك أو طلبك وسيتولى فريق العمل خدمتك.",
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
# نظام الحماية الصارم
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    if "http://" in message.content or "https://" in message.content or "discord.gg/" in message.content:
        try:
            await message.delete()
            warning_msg = await message.channel.send(f"⚠️ {message.author.mention}, ممنوع إرسال الروابط أو الدعوات هنا!")
            await warning_msg.delete(delay=5)
        except Exception as e:
            print(f"Error handling link deletion: {e}")
        return

    await bot.process_commands(message)


@bot.event
async def on_guild_channel_delete(channel):
    print(f"⚠️ تنبيه أمني خطير: تم حذف قناة {channel.name}")


@bot.event
async def on_guild_role_delete(role):
    print(f"⚠️ تنبيه أمني خطير: تم حذف رتبة {role.name}")


@bot.event
async def on_ready():
    bot.add_view(TicketView())
    bot.add_view(InsideTicketView())
    bot.add_view(TicketManagementView())
    bot.add_view(ApplyPanelView("تقديم بنات", GIRLS_LOGS_CHANNEL_ID, "girls_apply"))
    bot.add_view(ApplyPanelView("تقديم عيال", BOYS_LOGS_CHANNEL_ID, "boys_apply"))
    bot.add_view(ApplicationDecisionView())

    try:
        bot.tree.copy_global_to(guild=GUILD_ID)
        synced = await bot.tree.sync(guild=GUILD_ID)
        print(f"Synced {len(synced)} slash commands successfully to guild {GUILD_ID.id}.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
    print(f"Logged in as {bot.user} successfully, N7Z-Bot is online!")


def check_admin_or_streamer(interaction: discord.Interaction) -> bool:
    is_admin = interaction.user.guild_permissions.administrator
    has_streamer_role = any(role.name.lower() in ["streamer", "ستريمر"] for role in interaction.user.roles)
    return is_admin or has_streamer_role


@bot.tree.command(name="setup-tickets", description="إرسال لوحة التذاكر إلى الروم المخصص")
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
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("✅ تم إرسال لوحة التذاكر إلى روم التذاكر المحدد بنجاح!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ لم يتم العثور على الروم بالآيدي المحدد (`1565981889045463051`).", ephemeral=True)


@bot.tree.command(name="setup-apply-girls", description="إرسال لوحة تقديم البنات إلى الروم المخصص")
async def setup_apply_girls(interaction: discord.Interaction):
    if not check_admin_or_streamer(interaction):
        await interaction.response.send_message("❌ عذراً، هذا الأمر محمي ولا يملكه إلا حاملو رتبة **Streamer** أو المشرفين!", ephemeral=True)
        return

    channel = bot.get_channel(GIRLS_PANEL_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(f"❌ لم يتم العثور على روم لوحة تقديم البنات (`{GIRLS_PANEL_CHANNEL_ID}`).", ephemeral=True)
        return

    embed = discord.Embed(
        title="✦ N 7 Z",
        description="تقديم بنات",
        color=0x2b2d31
    )
    view = ApplyPanelView("تقديم بنات", GIRLS_LOGS_CHANNEL_ID, "girls_apply")
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ تم إرسال لوحة تقديم البنات بنجاح!", ephemeral=True)


@bot.tree.command(name="setup-apply-boys", description="إرسال لوحة تقديم العيال إلى الروم المخصص")
async def setup_apply_boys(interaction: discord.Interaction):
    if not check_admin_or_streamer(interaction):
        await interaction.response.send_message("❌ عذراً، هذا الأمر محمي ولا يملكه إلا حاملو رتبة **Streamer** أو المشرفين!", ephemeral=True)
        return

    channel = bot.get_channel(BOYS_PANEL_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(f"❌ لم يتم العثور على روم لوحة تقديم العيال (`{BOYS_PANEL_CHANNEL_ID}`).", ephemeral=True)
        return

    embed = discord.Embed(
        title="✦ N 7 Z",
        description="تقديم عيال",
        color=0x2b2d31
    )
    view = ApplyPanelView("تقديم عيال", BOYS_LOGS_CHANNEL_ID, "boys_apply")
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ تم إرسال لوحة تقديم العيال بنجاح!", ephemeral=True)


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


bot.run(DISCORD_TOKEN)
