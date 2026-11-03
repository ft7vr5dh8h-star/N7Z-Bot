import os
import asyncio
from collections import defaultdict
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select
import google.generativeai as genai

# إعداد مفتاح Gemini الرسمي
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)
    generation_config = {
        "temperature": 0.7,
    }
    # تعليمات النظام لنوجه البوت بدقة لمساعدة أعضاء السيرفر وتوجيههم للرومات
    system_instruction = (
        "أنت مشرف ذكي ومساعد احترافي لسيرفر ديسكورد. "
        "مهمتك هي مساعدة الأعضاء والإجابة على استفساراتهم باللغة العربية الفصحى وبطريقة ودية. "
        "إذا سألك عضو عن مكان روم معين في السيرفر (مثل روم التذاكر، روم الستريك، روم الفويس، إلخ)، "
        "أجب باختصار ووضح له اسم الروم أو أين يجدها بدقة."
    )
    ai_model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        system_instruction=system_instruction
    )
else:
    ai_model = None

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

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

TARGET_ROLE_IDS = [
    1563693370436751441, 1563683211266228374, 1563749745116053605,
    1563693266120216619, 1563690204932481165, 1563690329234866196,
    1563693109903097886, 1563692936368234599, 1563690405101310142,
    1563690490346348604, 1563692859377590342, 1563693032715591770,
    1563682396958621848, 1566075985022029826
]

REACTION_ROLES = {}

# ==================== 🤖 دالة ذكاء Gemini الاصطناعي وتوجيه الرومات ====================
async def get_gemini_response(prompt: str, guild: discord.guild = None) -> str:
    if not ai_model:
        return "⚠️ مفتاح GEMINI_API_KEY غير مضاف في إعدادات المنصة (Secrets)."
    try:
        # إذا سأل العضو عن الرومات، نعطي البوت قائمة بأسماء رومات السيرفر عشان يوجهه صح
        channels_info = ""
        if guild:
            channel_list = [c.name for c in guild.text_channels[:30]]
            channels_info = f"\n(معلومات سياقية: رومات السيرفر الحالية هي: {', '.join(channel_list)})"

        full_prompt = prompt + channels_info
        
        loop = asyncio.get_event_loop()
        response = await ai_model.generate_content_async(full_prompt)
        return response.text if response.text else "عذراً، لم أستطع صياغة إجابة."
    except Exception as e:
        print(f"Gemini AI Error: {e}")
        return "حدث خطأ مؤقت في الاتصال، يرجى المحاولة لاحقاً."

@bot.tree.command(name="ai", description="التحدث مع ذكاء Gemini الاصطناعي")
@app_commands.describe(prompt="اكتب سؤالك هنا")
async def ai_command(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    reply = await get_gemini_response(prompt, interaction.guild)
    
    if len(reply) > 2000:
        reply = reply[:1990] + "..."
        
    embed = discord.Embed(
        title="✨ إجابة المساعد الذكي",
        description=reply,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"السؤال: {prompt[:50]}")
    await interaction.followup.send(embed=embed)

# ==================== 💬 الرد عند المنشن والتوجيه التلقائي ====================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()

    # الرد التلقائي عند منشن البوت (يوجه العضو للروم المطلوب)
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        clean_content = content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        if clean_content:
            async with message.channel.typing():
                ai_reply = await get_gemini_response(clean_content, message.guild)
                if len(ai_reply) > 2000:
                    ai_reply = ai_reply[:1990] + "..."
                await message.reply(ai_reply)
            return

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

# ==================== 🎭 رولات الرياكشن ====================
@bot.tree.command(name="setup_reaction_roles", description="إرسال رسالة رولات الرياكشن التلقائية")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(role="الرتبة التي ستعطى للعضو", emoji="الإيموجي المطلوب")
async def setup_reaction_roles(interaction: discord.Interaction, role: discord.Role, emoji: str):
    embed = discord.Embed(
        title="✨ نظام رولات السيرفر ✨",
        description=f"للحصول على رول {role.mention} ، اضغط على التفاعل ({emoji}) أدناه!",
        color=discord.Color.gold()
    )
    message = await interaction.channel.send(embed=embed)
    try:
        await message.add_reaction(emoji)
        REACTION_ROLES[emoji] = role.id
        await interaction.response.send_message("✅ تم إنشاء رسالة رولات الرياكشن بنجاح!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot:
        return
    emoji = str(payload.emoji)
    if emoji in REACTION_ROLES:
        guild = bot.get_guild(payload.guild_id)
        if guild:
            role = guild.get_role(REACTION_ROLES[emoji])
            if role:
                try:
                    await payload.member.add_roles(role)
                except Exception as e:
                    print(f"Reaction add error: {e}")

@bot.event
async def on_raw_reaction_remove(payload):
    emoji = str(payload.emoji)
    if emoji in REACTION_ROLES:
        guild = bot.get_guild(payload.guild_id)
        if guild:
            member = guild.get_member(payload.user_id)
            if member and not member.bot:
                role = guild.get_role(REACTION_ROLES[emoji])
                if role:
                    try:
                        await member.remove_roles(role)
                    except Exception as e:
                        print(f"Reaction remove error: {e}")

# ==================== 🛡️ تأمين الرتب ====================
@bot.tree.command(name="setup_roles", description="تأمين وضبط صلاحيات الرتب المحددة")
@app_commands.checks.has_permissions(administrator=True)
async def setup_roles(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ جاري تأمين الرتب...", ephemeral=True)
    guild = interaction.guild
    success_count = 0
    try:
        default_role = guild.default_role
        await default_role.edit(permissions=discord.Permissions(
            send_messages=True, read_messages=True, connect=True, speak=True,
            add_reactions=True, read_message_history=True, kick_members=False,
            ban_members=False, manage_roles=False, manage_channels=False, administrator=False
        ))
    except Exception as e:
        print(f"Error updating @everyone: {e}")

    for role_id in TARGET_ROLE_IDS:
        role = guild.get_role(role_id)
        if role:
            try:
                await role.edit(permissions=discord.Permissions(
                    send_messages=True, read_messages=True, connect=True, speak=True,
                    add_reactions=True, read_message_history=True, kick_members=False,
                    ban_members=False, manage_roles=False, manage_channels=False, administrator=False
                ))
                success_count += 1
            except Exception as e:
                print(f"Failed to update role {role_id}: {e}")

    await interaction.followup.send(f"✅ تم تأمين: `{success_count}` رتبة بنجاح!", ephemeral=True)

# ==================== 🛡️ Anti-Nuke ====================
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
                    await user.timeout(discord.utils.utcnow() + discord.timedelta(hours=1), reason="حماية السيرفر: حذف رومات!")
                except:
                    pass
                if log_channel:
                    await log_channel.send(f"🚨 **Anti-Nuke:** {user.mention} تم إيقافه بسبب حذف رومات.")
                break
    except Exception as e:
        print(f"Anti-nuke error: {e}")

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
                    await user.timeout(discord.utils.utcnow() + discord.timedelta(hours=1), reason="حماية السيرفر: إنشاء رومات بكثرة!")
                except:
                    pass
                if log_channel:
                    await log_channel.send(f"🚨 **Anti-Nuke:** {user.mention} تم إيقافه بسبب إنشاء رومات كثيرة.")
                break
    except Exception as e:
        print(f"Anti-nuke create error: {e}")

# ==================== 📢 Broadcast ====================
@bot.tree.command(name="broadcast", description="إرسال برودكاست للأعضاء")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message="النص المراد إرساله")
async def broadcast(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("⏳ جاري إرسال البرودكاست...", ephemeral=True)
    success, failed = 0, 0
    for member in interaction.guild.members:
        if member.bot:
            continue
        try:
            await member.send(f"{message}\n\n{member.mention}")
            success += 1
            await asyncio.sleep(0.5)
        except Exception:
            failed += 1

    log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📢 **تقرير البرودكاست:** نجح: `{success}` | فشل: `{failed}`")

# ==================== 🎫 التذاكر والتقييم ====================
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

class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("جاري إغلاق التذكرة...", ephemeral=True)
        try:
            await interaction.user.send("كيف كانت تجربتك مع الدعم الفني؟", view=RatingView())
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
            discord.SelectOption(label="الدعم الفني العام", emoji="🛠️"),
            discord.SelectOption(label="قسم الشكاوى", emoji="⚠️"),
            discord.SelectOption(label="المبيعات والاشتراكات", emoji="💳"),
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
        await interaction.response.send_message(f"تم فتح تذكرتك: {ticket_channel.mention}", ephemeral=True)
        embed = discord.Embed(title=f"تذكرة: {select.values[0]}", description=f"أهلاً بك {interaction.user.mention}، اكتب مشكلتك هنا.", color=discord.Color.green())
        await ticket_channel.send(content=f"{interaction.user.mention} | {support_role.mention}", embed=embed, view=TicketControlView())

@bot.tree.command(name="setup_tickets", description="إرسال لوحة التذاكر")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(title="مركز الدعم الفني 🎫", description="اختر القسم المناسب لفتح تذكرة.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=TicketSelectView())
    await interaction.response.send_message("تم إرسال لوحة التذاكر بنجاح! ✅", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - Channel Guide AI Ready!')

bot.run(os.getenv('TOKEN'))
