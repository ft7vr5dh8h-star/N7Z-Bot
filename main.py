import os
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
            
            # جلب روم السجلات
            logs_channel = interaction.guild.get_channel(LOGS_CHANNEL_ID)
            
            # جمع رسائل التذكرة وتصديرها كملف
            messages = [f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author}: {msg.content}" async for msg in interaction.channel.history(limit=500)]
            transcript_text = f"--- سجلات تذكرة: {interaction.channel.name} ---\nأغلق بواسطة: {interaction.user}\n\n" + "\n".join(reversed(messages))
            file = discord.File(io.BytesIO(transcript_text.encode('utf-8')), filename=f"transcript-{interaction.channel.name}.txt")
            
            if logs_channel:
                await logs_channel.send(content=f"📁 **سجلات التذكرة المغلقة:** `{interaction.channel.name}`\nبواسطة المشرف: {interaction.user.mention}", file=file)
            
            # تنفيذ أمر الحذف الفوري للروم
            await interaction.channel.delete(reason=f"Closed by {interaction.user}")

        elif val == "add_user":
            await interaction.response.send_message("👥 لاستخدام إضافة عضو، قم بمنشن العضو المطلوب داخل التذكرة.", ephemeral=True)
        elif val == "pm_reminder":
            await interaction.response.send_message("✉️ تم إرسال تذكير خاص لصاحب التذكرة بنجاح.", ephemeral=True)
        elif val == "ticket_copy":
            messages = [f"{msg.author}: {msg.content}" async for msg in interaction.channel.history(limit=100)]
            transcript = "\n".join(reversed(messages))
            file = discord.File(io.BytesIO(transcript.encode('utf-8')), filename=f"
