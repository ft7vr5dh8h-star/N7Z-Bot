import os
import asyncio
from collections import defaultdict
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

GUILD_ID = 1563678057863057559  # آيدي سيرفرك

class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print("Slash commands synced instantly to your server!")

bot = TicketBot()

SUPPORT_ROLE_ID = 1563683677819637782
LOG_CHANNEL_ID = 1565578863277248655
CATEGORY_ID = 1563682943333965884

# ==================== 🛡️ أمر ضبط وتأمين الصلاحيات للرتب ====================
@bot.tree.command(name="setup_roles", description="ضبط وتأمين صلاحيات الرتب العامة وإزالة الصلاحيات القوية")
@app_commands.checks.has_permissions(administrator=True)
async def setup_roles(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ جاري ضبط صلاحيات الرتب وتأمين السيرفر...", ephemeral=True)
    guild = interaction.guild

    try:
        # ضبط الصلاحيات القياسية لرتبة Everyone لغلق الثغرات ومنع الصلاحيات الخطيرة
        default_role = guild.default_role
        await default_role.edit(permissions=discord.Permissions(
            send_messages=True,
            read_messages=True,
            connect=True,
            speak=True,
            add_reactions=True,
            read_message_history=True,
            kick_members=False,      # منع الكيك
            ban_members=False,       # منع الباند
            manage_roles=False,      # منع تعديل الرتب
            manage_channels=False,   # منع تعديل الرومات
            administrator=False      # منع الصلاحية الكاملة
        ))

        await interaction.followup.send("✅ تم ضبط وتأمين صلاحيات الرتب بنجاح وأصبحت خالية من الصلاحيات الخطيرة! 🛡️", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ حدث خطأ أثناء ضبط الرتب: {e}", ephemeral=True)

# ==================== 💬 الردود والأوامر السريعة (Chat Commands) ====================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()

    if content == ".":
        await message.channel.send("ارحب")
        return

    if content == "السلام عليكم":
        await message.channel.send("عليكم السلام")
        return

    if content.startswith("بنعالي"):
        if not message.author.guild_permissions.kick_members:
            await message.channel.send("❌ ما عندك صلاحية استخدام هذا الأمر!")
            return

        if message.mentions:
            target = message.mentions[0]
            try:
                await target.kick(reason=f"تم الكيك بواسطة {message.author}")
                await message.channel.send(f"👞 تم معاطاة {target.mention} بنعالي (Kick) بنجاح!")
            except:
                await message.channel.send("❌ ما قدرت أعطيه كيك، ارفع رتبة البوت فوق رتبته.")
        else:
            await message.channel.send("⚠️ لازم تسوي منشن للشخص مع الأمر! مثال: `بنعالي @شخص`")
        return

    if content.startswith("اسكت"):
        if not message.author.guild_permissions.moderate_members:
            await message.channel.send("❌ ما عندك صلاحية استخدام هذا الأمر!")
            return

        if message.mentions:
            target = message.mentions[0]
            try:
                await target.timeout(discord.utils.utcnow() + discord.timedelta(minutes=1), reason=f"اسكت بواسطة {message.author}")
                await message.channel.send(f"🤫 تم إلقام {target.mention} تايم آوت لمدة دقيقة!")
            except:
                await message.channel.send("❌ ما قدرت أعطيه تايم آوت، ارفع رتبة البوت فوق رتبته.")
        else:
            await message.channel.send("⚠️ لازم تسوي منشن للشخص مع الأمر! مثال: `اسكت @شخص`")
        return

    await bot.process_commands(message)

# ==================== 🛡️ نظام الحماية (Anti-Nuke) ====================
deleted_channels_tracker = defaultdict(list)
created_channels_tracker = defaultdict(list)

@bot.event
async def on_guild_channel_delete(channel):
    if channel.category and channel.category.id == CATEGORY_ID:
        return

    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            user = entry.user
            if user.bot or user.guild_permissions.administrator:
                return

            now = asyncio.get_event_loop().time()
            deleted_channels_tracker[user.id] = [t for t in deleted_channels_tracker[user.id] if now - t < 60]
            deleted_channels_tracker[user.id].append(now)

            if len(deleted_channels_tracker[user.id]) >= 2:
                log_channel = channel.guild.get_channel(LOG_CHANNEL_ID)
                try:
                    await user.timeout(discord.utils.utcnow() + discord.timedelta(hours=1), reason="حماية السيرفر: محاولة حذف رومات جماعية!")
                except:
                    pass

                if log_channel:
                    await log_channel.send(f"🚨 **تنبيه حماية (Anti-Nuke):** قام العضو {user.mention} بحذف أكثر من رومين في وقت قصير! تم عمل TimeOut له.")
                break
    except Exception as e:
        print(f"Anti-nuke delete error: {e}")

@bot.event
async def on_guild_channel_create(channel):
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            user = entry.user
            if user.bot or user.guild_permissions.administrator:
                return

            now = asyncio.get_event_loop().time()
            created_channels_tracker[user.id] = [t for t in created_channels_tracker[user.id] if now - t < 60]
            created_channels_tracker[user.id].append(now)

            if len(created_channels_tracker[user.id]) >= 5:
                log_channel = channel.guild.get_channel(LOG_CHANNEL_ID)
                try:
                    await user.timeout(discord.utils.utcnow() + discord.timedelta(hours=1), reason="حماية السيرفر: إنشاء رومات بشكل مريب!")
                except:
                    pass

                if log_channel:
                    await log_channel.send(f"🚨 **تنبيه حماية (Anti-Nuke):** قام العضو {user.mention} بإنشاء 5 رومات أو أكثر في دقيقة! تم إيقافه.")
                break
    except Exception as e:
        print(f"Anti-nuke create error: {e}")

# ==================== 📢 أمر البرودكاست في الخاص (Broadcast) ====================
@bot.tree.command(name="broadcast", description="إرسال برودكاست في الخاص لجميع أعضاء السيرفر مع منشن")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message="النص المراد إرساله للأعضاء")
async def broadcast(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("⏳ جاري بدء إرسال البرودكاست...", ephemeral=True)
    
    success = 0
    failed = 0
    
    for member in interaction.guild.members:
        if member.bot:
            continue
        try:
            full_message = f"{message}\n\n{member.mention}"
            await member.send(full_message)
            success += 1
            await asyncio.sleep(0.5)
        except Exception:
            failed += 1

    log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📢 **تقرير البرودكاست:** تم الإرسال بواسطة {interaction.user.mention}\n✅ نجح الإرسال إلى: `{success}` عضو\n❌ فشل: `{failed}` عضو")

# ==================== 🎫 أزرار وقوائم التذاكر ====================
class RatingView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="تقييم خدمة الدعم الفني ⭐",
        options=[
            discord.SelectOption(label="ممتاز ⭐⭐⭐⭐⭐", value="5"),
            discord.SelectOption(label="جيد جداً ⭐⭐⭐⭐", value="4"),
            discord.SelectOption(label="مقبول ⭐⭐⭐", value="3"),
            discord.SelectOption(label="سيء ⭐", value="1"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        await interaction.response.send_message(f"شكراً لتقييمك: {select.values[0]} نجوم! ❤️", ephemeral=True)
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📊 **تقييم جديد:** قام {interaction.user.mention} بتقييم التذكرة بـ {select.values[0]}/5")

class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("جاري إغلاق التذكرة...", ephemeral=True)
        
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"🗑️ **تذكرة مغلقة:** تم إغلاق روم `{interaction.channel.name}` بواسطة {interaction.user.mention}")
        
        try:
            await interaction.user.send("كيف كانت تجربتك مع الدعم الفني؟ يرجى التقييم:", view=RatingView())
        except:
            pass
        
        await interaction.channel.delete()

class TicketSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="اختر قسم الدعم الفني...",
        custom_id="ticket_category_select",
        options=[
            discord.SelectOption(label="الدعم الفني العام", description="مساعدة في المشاكل العامة", emoji="🛠️"),
            discord.SelectOption(label="قسم الشكاوى", description="تقديم شكوى خاصة", emoji="⚠️"),
            discord.SelectOption(label="المبيعات والاشتراكات", description="استفسارات الشراء", emoji="💳"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        guild = interaction.guild
        category = guild.get_channel(CATEGORY_ID)
        support_role = guild.get_role(SUPPORT_ROLE_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            support_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        ticket_channel = await guild.create_text_channel(
            name=f"t-{select.values[0]}-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"تم فتح تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)

        embed = discord.Embed(
            title=f"تذكرة: {select.values[0]}",
            description=f"أهلاً بك {interaction.user.mention}، يرجى كتابة مشكلتك وسيقوم فريق الدعم الفني بالرد عليك.",
            color=discord.Color.green()
        )
        await ticket_channel.send(content=f"{interaction.user.mention} | {support_role.mention}", embed=embed, view=TicketControlView())

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📩 **تذكرة جديدة:** قام {interaction.user.mention} بفتح تذكرة في قسم `{select.values[0]}` ({ticket_channel.mention})")

@bot.tree.command(name="setup_tickets", description="إرسال لوحة تذاكر الدعم الفني")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="مركز الدعم الفني 🎫",
        description="يرجى اختيار القسم المناسب من القائمة أدناه لفتح تذكرة.",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=TicketSelectView())
    await interaction.response.send_message("تم إرسال لوحة التذاكر بنجاح! ✅", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - Roles Setup & All Systems Ready!')

bot.run(os.getenv('TOKEN'))
