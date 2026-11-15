import os
import discord
from discord import app_commands
from discord.ext import commands
import io
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from protectbot.config import Config

# جلب التوكن من متغيرات البيئة في رايلواي (أو من ملف .env محليًا)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

PROTECT_EXTENSIONS = [
    "protectbot.cogs.antilink",
    "protectbot.cogs.antispam",
    "protectbot.cogs.antiraid",
    "protectbot.cogs.antinuke",
    "protectbot.cogs.admin",
]


class N7ZBot(commands.Bot):
    async def setup_hook(self) -> None:
        # تحميل وحدات الحماية قبل جاهزية البوت حتى تُزامَن أوامر السلاش معها
        for ext in PROTECT_EXTENSIONS:
            await self.load_extension(ext)


bot = N7ZBot(command_prefix="!", intents=intents)
bot.config = Config(Path(__file__).resolve().parent / "config.json")

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
            file = discord.File(io.BytesIO(transcript.encode('utf-8')), filename=f"transcript-{interaction.channel.name}.txt")
            await interaction.response.send_message("📋 تفضل نسخة من سجلات هذه التذكرة:", file=file, ephemeral=True)

class TicketManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketManagementSelect())

# أزرار تحكم المشرفين داخل التذكرة (Ticket Options و Claim)
class InsideTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket Options", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="ticket_options_btn")
    async def ticket_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎫 **Ticket Management**\n• Select an option from the dropdown menu below", view=TicketManagementView(), ephemeral=True)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="💼", custom_id="claim_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"💼 تم استلام التذكرة بواسطة المشرف: {interaction.user.mention}")

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
    # تسجيل الViews لكي تعمل الأزرار والقوائم دائماً بشكل دائم
    bot.add_view(TicketView())
    bot.add_view(InsideTicketView())
    bot.add_view(TicketManagementView())
    
    try:
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            synced = await bot.tree.sync(guild=discord.Object(id=int(guild_id)))
        else:
            synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands successfully.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
    print(f'Logged in as {bot.user} successfully, N7Z-Bot is online!')


def check_admin_or_streamer(interaction: discord.Interaction) -> bool:
    is_admin = interaction.user.guild_permissions.administrator
    has_streamer_role = any(role.name.lower() in ["streamer", "ستريمر"] for role in interaction.user.roles)
    return is_admin or has_streamer_role


# 1. أمر إرسال لوحة التذاكر (بدون صورة)
@bot.tree.command(name="setup-tickets", description="إرسال لوحة التذاكر إلى الروم المخصص بدون صورة")
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
        await interaction.response.send_message("✅ تم إرسال لوحة التذاكر بدون صورة إلى روم التذاكر المحدد بنجاح!", ephemeral=True)
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

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("خطأ: لم يتم العثور على متغير البيئة DISCORD_TOKEN.")
    bot.run(DISCORD_TOKEN)
"""تحميل إعدادات السيرفر وحفظها في ملف JSON."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_ALLOWED_DOMAINS = [
    "youtube.com",
    "youtu.be",
    "tenor.com",
    "giphy.com",
    "media.discordapp.net",
    "cdn.discordapp.com",
    "discord.com",
    "discordapp.com",
]

DEFAULT_GUILD: dict[str, Any] = {
    "log_channel_id": None,
    "whitelist_users": [],
    "whitelist_roles": [],
    "allowed_domains": list(DEFAULT_ALLOWED_DOMAINS),
    "protections": {
        "antilink": True,
        "antispam": True,
        "antiraid": True,
        "antinuke": True,
    },
    "antilink": {
        "max_warnings": 2,
        "timeout_minutes": 10,
    },
    "antispam": {
        "max_messages": 6,
        "window_seconds": 5,
        "duplicate_count": 3,
        "max_mentions": 6,
        "timeout_minutes": 10,
    },
    "antiraid": {
        "join_threshold": 8,
        "window_seconds": 12,
        "kick_new_accounts": True,
        "min_account_age_days": 7,
        "lockdown_on_raid": True,
    },
    "antinuke": {
        "window_seconds": 20,
        "channel_delete_limit": 3,
        "channel_create_limit": 5,
        "role_delete_limit": 3,
        "role_create_limit": 5,
        "ban_limit": 3,
        "kick_limit": 4,
        "webhook_limit": 3,
        "bot_add_limit": 1,
        "dangerous_perm_limit": 1,
        "restore": True,
    },
    "lockdown": {
        "active": False,
        "previous_verification": None,
        "channel_overwrites": {},
    },
}

_LOCK = threading.Lock()


def _deep_merge(base: dict, incoming: dict) -> dict:
    out = deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


class Config:
    """إعدادات لكل سيرفر، تُحفظ تلقائيًا في JSON."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, Any] = {"guilds": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError):
            raw = {"guilds": {}}
        if not isinstance(raw, dict):
            raw = {"guilds": {}}
        raw.setdefault("guilds", {})
        self._data = raw

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with _LOCK:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2)
            tmp.replace(self.path)

    def guild(self, guild_id: int) -> dict[str, Any]:
        key = str(guild_id)
        guilds = self._data.setdefault("guilds", {})
        if key not in guilds:
            guilds[key] = deepcopy(DEFAULT_GUILD)
            self.save()
        else:
            merged = _deep_merge(DEFAULT_GUILD, guilds[key])
            # Keep list fields from saved data rather than merging uniquely
            for list_key in ("whitelist_users", "whitelist_roles", "allowed_domains"):
                if list_key in guilds[key]:
                    merged[list_key] = list(guilds[key][list_key])
            if merged != guilds[key]:
                guilds[key] = merged
                self.save()
        return guilds[key]

    def update_guild(self, guild_id: int) -> dict[str, Any]:
        """أعد المرجع ثم احفظ بعد تعديل المتصل للقواميس المتداخلة."""
        data = self.guild(guild_id)
        self.save()
        return data

    def is_protection_on(self, guild_id: int, name: str) -> bool:
        return bool(self.guild(guild_id)["protections"].get(name, False))

    def set_protection(self, guild_id: int, name: str, enabled: bool) -> None:
        self.guild(guild_id)["protections"][name] = bool(enabled)
        self.save()
"""دوال مساعدة: القائمة البيضاء، السجلات، المهلة الزمنية، والصلاحيات."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from protectbot.config import Config

log = logging.getLogger("protectbot")

DANGEROUS_PERMISSIONS = (
    "administrator",
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
    "mention_everyone",
    "manage_expressions",
    "moderate_members",
)

PROTECTION_NAMES = {
    "antilink": "مكافحة الروابط",
    "antispam": "مكافحة الإزعاج",
    "antiraid": "مكافحة الغارات",
    "antinuke": "مكافحة التخريب",
}


def is_guild_owner(guild: discord.Guild, user: discord.abc.User) -> bool:
    return guild.owner_id is not None and user.id == guild.owner_id


def is_whitelisted(config: Config, member: discord.Member) -> bool:
    data = config.guild(member.guild.id)
    if member.id in data["whitelist_users"]:
        return True
    role_ids = set(data["whitelist_roles"])
    return any(role.id in role_ids for role in member.roles)


def is_exempt(config: Config, guild: discord.Guild, user: discord.abc.User, *, bot_user: discord.ClientUser | None = None) -> bool:
    """المالك، البوت نفسه، والأعضاء/الرتب في القائمة البيضاء مستثنون من العقوبات التلقائية."""
    if bot_user is not None and user.id == bot_user.id:
        return True
    if is_guild_owner(guild, user):
        return True
    member = user if isinstance(user, discord.Member) else guild.get_member(user.id)
    if member is None:
        data = config.guild(guild.id)
        return user.id in data["whitelist_users"]
    return is_whitelisted(config, member)


def has_dangerous_permissions(perms: discord.Permissions) -> bool:
    return any(getattr(perms, name, False) for name in DANGEROUS_PERMISSIONS)


async def apply_timeout(
    member: discord.Member,
    minutes: int,
    reason: str,
) -> bool:
    if minutes <= 0:
        return False
    try:
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        return True
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning("تعذر إعطاء مهلة لـ %s: %s", member.id, exc)
        return False


async def strip_roles(member: discord.Member, reason: str) -> list[str]:
    """يزيل كل الرتب التي يستطيع البوت إدارتها. يعيد أسماء الرتب المُزالة."""
    removable = [role for role in member.roles if role != member.guild.default_role and role.is_assignable()]
    if not removable:
        return []
    try:
        await member.remove_roles(*removable, reason=reason)
        return [role.name for role in removable]
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning("تعذر نزع رتب %s: %s", member.id, exc)
        # حاول واحدة تلو الأخرى
        removed: list[str] = []
        for role in removable:
            try:
                await member.remove_roles(role, reason=reason)
                removed.append(role.name)
            except (discord.Forbidden, discord.HTTPException):
                continue
        return removed


async def ban_or_kick(guild: discord.Guild, user: discord.abc.User, reason: str) -> str:
    """يحاول الحظر، وإن تعذر يطرد العضو إن كان موجودًا. يعيد وصف النتيجة."""
    try:
        await guild.ban(user, reason=reason, delete_message_seconds=0)
        return "ban"
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning("تعذر حظر %s: %s", user.id, exc)
        member = user if isinstance(user, discord.Member) else guild.get_member(user.id)
        if member is not None:
            try:
                await member.kick(reason=reason)
                return "kick"
            except (discord.Forbidden, discord.HTTPException) as exc2:
                log.warning("تعذر طرد %s: %s", user.id, exc2)
        return "failed"


def user_mention(user: discord.abc.User | None) -> str:
    if user is None:
        return "غير معروف"
    return f"{user.mention} (`{user}`, ID: `{user.id}`)"


async def send_log(
    bot: discord.Client,
    guild: discord.Guild,
    *,
    title: str,
    description: str,
    color: discord.Color = discord.Color.orange(),
    fields: list[tuple[str, str, bool]] | None = None,
) -> None:
    config: Config = bot.config  # type: ignore[attr-defined]
    channel_id = config.guild(guild.id).get("log_channel_id")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id) or bot.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return
    embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
    embed.set_footer(text="بوت الحماية")
    for name, value, inline in fields or []:
        embed.add_field(name=name, value=value[:1024], inline=inline)
    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning("تعذر إرسال السجل في %s: %s", guild.id, exc)


async def notify_user(user: discord.abc.User, message: str) -> None:
    try:
        await user.send(message)
    except (discord.Forbidden, discord.HTTPException):
        return
"""تفعيل وضع الإغلاق وإلغاؤه: رفع التحقق وقفل القنوات."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord

from protectbot.utils import send_log

if TYPE_CHECKING:
    from protectbot.config import Config

log = logging.getLogger("protectbot")

# القيم التي نقيّدها أثناء الإغلاق
LOCK_PERMS = (
    "send_messages",
    "send_messages_in_threads",
    "create_public_threads",
    "create_private_threads",
    "add_reactions",
    "connect",
    "speak",
)


def _serialize_overwrite(overwrite: discord.PermissionOverwrite | None) -> dict[str, bool | None]:
    if overwrite is None:
        return {name: None for name in LOCK_PERMS}
    return {name: getattr(overwrite, name) for name in LOCK_PERMS}


def _apply_saved(overwrite: discord.PermissionOverwrite, saved: dict[str, Any]) -> discord.PermissionOverwrite:
    for name in LOCK_PERMS:
        setattr(overwrite, name, saved.get(name))
    return overwrite


async def enable_lockdown(
    bot: discord.Client,
    guild: discord.Guild,
    reason: str,
) -> bool:
    """يقفل القنوات ويرفع مستوى التحقق. يحفظ الحالة السابقة للاستعادة."""
    config: Config = bot.config  # type: ignore[attr-defined]
    data = config.guild(guild.id)
    lockdown = data["lockdown"]
    if lockdown.get("active"):
        return False

    previous_verification = guild.verification_level.value
    target_level = discord.VerificationLevel.high
    if guild.verification_level < target_level:
        try:
            await guild.edit(verification_level=target_level, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("تعذر رفع مستوى التحقق في %s: %s", guild.id, exc)

    saved: dict[str, dict[str, bool | None]] = {}
    everyone = guild.default_role
    for channel in guild.channels:
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
            continue
        try:
            current = channel.overwrites_for(everyone)
            saved[str(channel.id)] = _serialize_overwrite(current)
            new_ow = channel.overwrites_for(everyone)
            if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                new_ow.send_messages = False
                new_ow.send_messages_in_threads = False
                new_ow.create_public_threads = False
                new_ow.create_private_threads = False
                new_ow.add_reactions = False
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                new_ow.connect = False
                new_ow.speak = False
            await channel.set_permissions(everyone, overwrite=new_ow, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("تعذر قفل القناة %s: %s", channel.id, exc)

    lockdown["active"] = True
    lockdown["previous_verification"] = previous_verification
    lockdown["channel_overwrites"] = saved
    config.save()

    await send_log(
        bot,
        guild,
        title="تم تفعيل وضع الإغلاق",
        description=f"تم قفل القنوات ورفع مستوى التحقق.\n**السبب:** {reason}",
        color=discord.Color.red(),
    )
    return True


async def disable_lockdown(
    bot: discord.Client,
    guild: discord.Guild,
    reason: str = "إلغاء وضع الإغلاق",
) -> bool:
    config: Config = bot.config  # type: ignore[attr-defined]
    data = config.guild(guild.id)
    lockdown = data["lockdown"]
    if not lockdown.get("active"):
        return False

    prev = lockdown.get("previous_verification")
    if prev is not None:
        try:
            level = discord.VerificationLevel(prev)
            await guild.edit(verification_level=level, reason=reason)
        except (ValueError, discord.Forbidden, discord.HTTPException) as exc:
            log.warning("تعذر استعادة مستوى التحقق في %s: %s", guild.id, exc)

    saved: dict[str, dict[str, Any]] = lockdown.get("channel_overwrites") or {}
    everyone = guild.default_role
    for channel in guild.channels:
        raw = saved.get(str(channel.id))
        if raw is None:
            continue
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
            continue
        try:
            current = channel.overwrites_for(everyone)
            restored = _apply_saved(current, raw)
            # إذا صارت كل القيم فارغة ولا توجد قيود أخرى ذات معنى، أزل الاستثناء
            pair = restored.pair()
            if pair[0].value == 0 and pair[1].value == 0:
                await channel.set_permissions(everyone, overwrite=None, reason=reason)
            else:
                await channel.set_permissions(everyone, overwrite=restored, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("تعذر فك قفل القناة %s: %s", channel.id, exc)

    lockdown["active"] = False
    lockdown["previous_verification"] = None
    lockdown["channel_overwrites"] = {}
    config.save()

    await send_log(
        bot,
        guild,
        title="تم إلغاء وضع الإغلاق",
        description=f"أُعيدت القنوات ومستوى التحقق قدر الإمكان.\n**السبب:** {reason}",
        color=discord.Color.green(),
    )
    return True
