# -*- coding: utf-8 -*-
"""
بوت N7Z — نظام التذاكر + حماية السيرفر
=======================================
هذا ملف واحد يجمع كل كود البوت، حتى يسهل قراءته وتشغيله.

ماذا يفعل البوت؟
  1) نظام التذاكر: لوحة أزرار لفتح تذكرة، وإدارتها، وتصدير سجلها.
  2) أمر /broadcast: إرسال رسالة لجميع الأعضاء في الخاص.
  3) حماية السيرفر:
       - مكافحة الروابط ودعوات ديسكورد
       - مكافحة الإزعاج (رسائل سريعة / مكررة / منشن جماعي)
       - مكافحة الغارات (انضمام جماعي ثم إغلاق السيرفر)
       - مكافحة التخريب Anti-Nuke عبر سجل التدقيق، مع محاولة الاستعادة

كيف تشغّله؟
  1) ثبّت المكتبات:   pip install -r requirements.txt
  2) ضع توكن البوت في متغير البيئة DISCORD_TOKEN
     أو أنشئ ملف .env بجانب هذا الملف وفيه: DISCORD_TOKEN=التوكن
  3) شغّل الملف:       python bot.py

ملاحظات سريعة للمبتدئ:
  - أوامر السلاش تظهر بعد مزامنتها عند التشغيل (انظر on_ready).
  - الإعدادات تُحفظ تلقائيًا في ملف config.json بجانب هذا الملف.
  - لا تضع التوكن داخل الكود أبدًا.
  - رتبة البوت يجب أن تكون أعلى من الرتب التي يراد محاسبتها.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# المكتبات المستخدمة
# ---------------------------------------------------------------------------
# os / Path : قراءة التوكن ومسار الملفات
# json      : حفظ الإعدادات في config.json
# discord   : مكتبة ديسكورد الرسمية لبايثون (discord.py 2.x)
# app_commands : أوامر السلاش (التي تظهر عند كتابة / )
# commands.Cog : نقسم الحماية إلى "كلاسات" منظمة داخل نفس الملف
# ---------------------------------------------------------------------------
import asyncio
import io
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

# نحاول تحميل ملف .env إن وُجد (مفيد على جهازك). في Railway يكفي متغير البيئة.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    # المكتبة غير مثبتة؟ لا بأس، سنقرأ التوكن من نظام التشغيل مباشرة.
    pass

# مسجّل الأحداث في الطرفية (تحذيرات الصلاحيات مثلًا)
log = logging.getLogger("n7z")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# =============================================================================
# القسم 1: التوكن وصلاحيات البوت (Intents)
# -----------------------------------------------------------------------------
# التوكن هو "مفتاح" البوت. نقرأه من الخارج حتى لا يُسرق إن شاركت الملف.
# الـ Intents تخبر ديسكورد أي أحداث نحتاجها:
#   message_content : قراءة نص الرسائل (للكشف عن الروابط والإزعاج)
#   members         : معرفة الأعضاء والانضمام (للغارات والبرودكاست)
#   guilds          : بيانات السيرفر والقنوات
# =============================================================================

# التوكن من متغير البيئة، أو من ملف .env إن وُجد. لا نكتب التوكن هنا.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# صلاحيات البوت على البوابة (Gateway). يجب تفعيل Members و Message Content
# أيضًا من صفحة البوت في Discord Developer Portal.
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# مسار ملف الإعدادات بجانب bot.py (يُنشأ تلقائيًا عند أول تشغيل)
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


# =============================================================================
# القسم 2: الإعدادات الافتراضية وحفظها في config.json
# -----------------------------------------------------------------------------
# كل سيرفر له إعداداته: تشغيل/إيقاف الحماية، القائمة البيضاء، الحدود، قناة السجلات.
# عند أي تعديل عبر الأوامر (مثل /whitelist أو /protection) يُحفظ الملف تلقائيًا.
# يمكنك لاحقًا تعديل الأرقام أيضًا يدويًا في config.json أو عبر أمر /setprotect.
# =============================================================================

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


# =============================================================================
# القسم 3: دوال مساعدة مشتركة
# -----------------------------------------------------------------------------
# هذه الدوال تُستخدم في أكثر من قسم:
#   - معرفة إن كان العضو مستثنى (المالك / البوت / القائمة البيضاء)
#   - إعطاء مهلة زمنية (Timeout)، نزع الرتب، الحظر أو الطرد
#   - إرسال سجل جميل (Embed) إلى قناة سجلات الحماية
# =============================================================================

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


# =============================================================================
# القسم 4: وضع الإغلاق (Lockdown)
# -----------------------------------------------------------------------------
# عند اكتشاف غارة — أو عند استخدام أمر /lockdown on — نرفع مستوى التحقق
# ونقفل الكتابة/الاتصال في القنوات. الإعدادات السابقة تُحفظ حتى /lockdown off.
# =============================================================================

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


# =============================================================================
# القسم 5: مكافحة الروابط ودعوات ديسكورد
# -----------------------------------------------------------------------------
# إذا أرسل عضو غير مستثنى رابطًا أو دعوة سيرفر، تُحذف الرسالة.
# يُعطى تحذيران ثم مهلة زمنية. النطاقات المسموحة تُدار بأمر /allowdomain.
# نراقب أيضًا تعديل الرسالة حتى لا يُلتف على الفلتر بعد الإرسال.
# =============================================================================

# أحرف خفية تُستخدم أحيانًا للالتفاف على الفلتر
_ZW = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")

INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:discord(?:app)?\.com/invite|discord\.gg|discord\.com/invite|discord\.me)/"
    r"[a-zA-Z0-9\-]+",
    re.IGNORECASE,
)

# روابط http/https وwww، أو نطاق ظاهر متبوع بمسار اختياري
URL_RE = re.compile(
    r"(?:(?:https?://)|(?:www\.))"
    r"[^\s<>\]\)\"']+"
    r"|(?:[a-zA-Z0-9-]+\.)+(?:com|net|org|io|gg|co|me|tv|xyz|app|dev|info|biz|online|site|shop|pro|ai|ph|sa|ae|uk|us|ly|to|cc|ru|de|fr|es|it|c
    