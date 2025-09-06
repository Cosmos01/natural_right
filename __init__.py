from nonebot import on_command
import hoshino.priv
from hoshino.typing import NoticeSession
from hoshino import Service, priv
from .core import *
from .config import BasicConfig, Tags
from .utils import list_at_users, get_time
import datetime

help_msg = '''
查询圣盾术 [@user1@user2...] 
充值圣盾术 [数量] [@user1@user2...]
权限标签 [添加/删除 标签名[:标签值] @user1@user2...]
群友连结 [解除] @user1@user2...
群地位 +1/-1 [@user1@user2...]
屏蔽本群[X天|X小时|X分钟]
解除群屏蔽
屏蔽@user [X天|X小时|X分钟]
解除屏蔽@user
引用消息并回复【撤回】
'''

sv = Service('天赋人权', enable_on_default=False, help_=help_msg)

config = BasicConfig()

@sv.on_prefix("查询圣盾术")
async def query_indulgences(bot, ev):
    users = list_at_users(ev.message)
    if len(users) == 0:
        users = [ev.user_id]
    for uid in users:
        await bot.send(ev, f"[CQ:at,qq={uid}]剩余圣盾术{get_indulgences(ev.group_id, uid)}层")


@sv.on_prefix('充值圣盾术')
async def recharge_indulgences(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    try:
        num = int(ev.message.extract_plain_text())
    except:
        num = 1
    users = list_at_users(ev.message)
    if len(users) == 0:
        users = [ev.user_id]
    for uid in users:
        add_indulgences(ev.group_id, uid, num)
    await bot.send(ev, f"已经为{len(users)}位用户充值完毕！谢谢惠顾～")


@sv.on_notice('group_ban')
async def group_ban_indulgences(session: NoticeSession):
    ev = session.event
    if ev.sub_type != 'ban':
        return
    if ev.operator_id == ev.self_id:
        return
    if config.indulgences_time_limit == 0:
        return

    indulgences = get_indulgences(ev.group_id, ev.user_id)
    if indulgences <= 0:
        return
    deduction = False
    limit = config.indulgences_time_limit
    if limit < 0:
        deduction = True
        limit = -limit

    if ev.duration <= limit:
        if use_indulgence(ev.group_id, ev.user_id):
            await session.send(f"[CQ:at,qq={ev.user_id}]消耗了1层圣盾术，解除了禁言")
            await lift_silence(ev)
        return

    if deduction:
        use_num = int(ev.duration / limit)
        duration = ev.duration - indulgences * limit
        if use_num <= indulgences:
            if use_indulgence(ev.group_id, ev.user_id, use_num):
                await session.send(f"[CQ:at,qq={ev.user_id}]消耗了{use_num}层圣盾术，解除了禁言")
                await lift_silence(ev)
                return
        elif config.indulgences_deduct:
            if use_indulgence(ev.group_id, ev.user_id, indulgences):
                await session.send(
                    f"[CQ:at,qq={ev.user_id}]消耗了{indulgences}层圣盾术，抵消了{get_time_text(indulgences * limit)}禁言")
                await silence(ev, duration)


@sv.on_prefix("权限标签")
async def set_tags(bot, ev):
    if not priv.check_priv(ev, priv.OWNER):
        return
    args = ev.message.extract_plain_text().strip().replace("  ", " ").split(" ", 1)
    tag = args[1].replace(" ",":").replace("：",":").split(":", 1)
    tagName = tag[0]
    tagValue = ""
    if len(tag) > 1:
        tagValue = tag[1]
    if len(args) == 1:
        await bot.send(ev, "【权限标签】\n"+Tags.keys())
        return
    users = list_at_users(ev.message)
    if len(users) == 0:
        users = [ev.user_id]

    if args[0] == "添加":
        if tagName not in Tags:
            await bot.send(ev, "标签不存在")
            return
        if tagValue == "":
            tagValue = Tags[tagName]
        for uid in users:
            set_user_tag(ev.group_id, uid, tagName, tagValue)
        await bot.send(ev, "添加成功")
    elif args[0] == "删除":
        for uid in users:
            del_user_tag(ev.group_id, uid, tagName)
        await bot.send(ev, "删除成功")


@sv.on_prefix(("查询信息", "查询信息"))
async def show_info(bot, ev):
    users = list_at_users(ev.message)
    if len(users) == 0:
        users = [ev.user_id]
    for uid in users:
        user = get_user(ev.group_id, uid)
        name = await get_user_name(ev, uid)
        msg = f"【{name}】\n"
        msg += f"圣盾术：{user['indulgences']}\n"
        msg += f"群地位：{user['level']}\n"
        msg += f"违规次数：{user['ban_count']} (-{user['deduction_count']})\n"
        msg += "权限标签："
        if len(user["tags"]) > 0:
            for k, v in user["tags"].items():
                if v == "":
                    msg += "\n    " + k
                else:
                    msg += f"\n    {k}:{v}"
            msg += "\n"
        else:
            msg += "无\n"
        msg += "连结对象："
        if len(user["link_to"]) > 0:
            names = await get_users_name(ev, user["link_to"])
            msg += "\n" + "\n    ".join(names)
        else:
            msg += "无"
        await bot.send(ev, msg)


@sv.on_prefix("群友连结")
async def link_user(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    users = list_at_users(ev.message)
    cmd = ev.message.extract_plain_text().strip()
    if cmd == "" and len(users) <= 1:
        if len(users) == 0:
            uid = ev.user_id
        else:
            uid = users[0]
        users = list_link_users(ev.group_id, uid)
        if len(users) == 0:
            await bot.send(ev, "没有连结对象")
            return
        names = await get_users_name(ev, users)
        await bot.send(ev, "【连结对象】\n" + "\n".join(names))
        return
    if cmd == "解除":
        if len(users) == 0:
            users = [ev.user_id]
        del_link_user(ev.group_id, users)
        await bot.send(ev, "已解除连结")
        return

    add_link_user(ev.group_id, users)
    await bot.send(ev, "已建立连结")


@sv.on_prefix("群地位")
async def set_group_level(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    cmd = ev.message.extract_plain_text().strip()
    users = list_at_users(ev.message)
    if len(users) == 0:
        users.append(ev.user_id)
    n = 0
    if cmd in ["加一", "+1", "up", "加1"]:
        n = 1
    elif cmd in ["减一", "-1", "down", "减1"]:
        n = -1
    else:
        bot.send(ev, "参数错误")
        return
    msg = "设置完成\n"
    for uid in users:
        user_level = set_user_level(ev.group_id, uid, n)
        name = await get_user_name(ev, uid)
        msg += f"{name}: {user_level}\n"
    await bot.send(ev, msg.strip())



@sv.on_prefix('屏蔽')
async def block_on(bot, ev):
    if not await check_user_role(ev, role="admin"):  # 我要看到血流成河
        return
    t = get_time(ev.message.extract_plain_text().replace(' ', ''))
    if "本群" in ev.message.extract_plain_text() and len(ev.message.extract_plain_text()) < 12:
        if not await check_user_role(ev, role=config.manager):
            return
        await bot.send(ev, "收到")
        hoshino.priv.set_block_group(ev.group_id, t)
        return
    users = list_at_users(ev.message)
    if len(users) == 0:
        await bot.send(ev, "请指定要被屏蔽的目标")
        return
    for suid in hoshino.config.SUPERUSERS:
        if suid in users:
            hoshino.priv.set_block_user(ev.user_id,t)
            await bot.send(ev, "？")
            await bot.send(ev, f"已屏蔽[CQ:at,qq={ev.user_id}]")
            return
    await bot.send(ev, "收到")
    for uid in users:
        hoshino.priv.set_block_user(uid,t)
    return


@on_command('解除群屏蔽', only_to_me=False, shell_like=True)
async def block_off(session):
    ev = session.event
    if not await check_user_role(ev, role=config.manager):
        return
    if hoshino.priv.check_block_group(ev.group_id):
        hoshino.priv.set_block_group(ev.group_id, datetime.timedelta(seconds=-1))
        await session.send(f"我回来啦！")
    else :
        await session.send(f"我明明一直都在！")


@sv.on_prefix('解除屏蔽')
async def user_block_off(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    users = list_at_users(ev.message)
    if len(users) > 0:
        for uid in users:
            hoshino.priv.set_block_user(uid, datetime.timedelta(seconds=-1))
        await bot.send(ev, "已解除屏蔽")
    return


@sv.on_suffix("撤回")
async def del_message(bot, ev):
    msg_id = 0
    for i in ev.message:
        if i.type == 'reply':
            msg_id = i.data["id"]
            break
    if msg_id == 0:
        return
    source_msg = await bot.get_msg(message_id=msg_id)
    source_qq = source_msg['sender']['user_id']
    if source_qq != ev.user_id and source_qq != ev.self_id:
        return
    await bot.delete_msg(message_id=msg_id, self_id=ev.self_id)


