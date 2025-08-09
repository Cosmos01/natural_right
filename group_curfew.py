import time
import hoshino
from hoshino import Service
from .core import *
from .config import CurfewConfig
from .utils import list_at_users

help_msg = '''【配置管理】
群宵禁 参数名 参数值
      - 开启/on/关闭/off
      - 类型 0-5
      - 时间 开始小时,结束小时
      - 字数限制 字数
      - 转发 目标群号/0
      - 违规警告 开启/on/关闭/off
【屏蔽词】
群屏蔽词 on/开启/off/关闭
群屏蔽词 添加/删除/清空 [屏蔽词]
【宵禁名单】
宵禁名单 [添加/删除 @user1@user2...]
【调试】
开始/结束群宵禁
'''

sv = Service('群宵禁', enable_on_default=False, help_=help_msg)

config = CurfewConfig()
target_groups = {}
curfew_type = {
    0: "全群禁言",
    1: "禁言部分成员",
    2: "禁止发送特定类型消息(部分成员)",
    3: "禁止发送特定类型消息",
    4: "禁止发送包含特定关键词的消息"
}

@sv.scheduled_job('cron',hour='*/1')
async def curfew():
    available_group = await sv.get_enable_groups()
    if len(available_group) == 0:
        return
    for group_id in available_group:
        group = get_group(group_id)
        if not group["curfew"]:
            continue
        await do_curfew(group_id)


async def do_curfew(gid):
    bot = hoshino.get_bot()
    hour = time.localtime(time.time()).tm_hour
    group = get_group(gid)

    if group["curfew_type"] == 0:
        if hour == group["start_time"] and not group["under_curfew"]:
            await bot.send_group_msg(group_id=gid, message='宵禁开始')
            group["under_curfew"] = True
            await bot.set_group_whole_ban(group_id=gid, enable=True)
            return
        elif hour == group["end_time"] and hour != group["start_time"]:
            await bot.send_group_msg(group_id=gid, message='宵禁结束')
            group["under_curfew"] = False
            await bot.set_group_whole_ban(group_id=gid, enable=False)
            save_all_data()
        return

    if group["curfew_type"] == 1:
        if hour == group["start_time"]:
            if "black_list" in group and len(group["black_list"]) > 0:
                await bot.send_group_msg(group_id=gid, message='宵禁开始')
                if group["start_time"] == group["end_time"]:
                    await bot.send_group_msg(group_id=gid, message='请配置正确的宵禁时间')
                    return
                for uid in group["black_list"]:
                    duration = abs(group["start_time"] - group["end_time"]) * 3600
                    await bot.set_group_ban(group_id=gid, user_id=uid, duration=duration)
        return

    if 2 <= group["curfew_type"] <= 4:
        if hour == group["start_time"] and not group["under_curfew"]:
            group["under_curfew"] = True
            await bot.send_group_msg(group_id=gid, message='宵禁开始')
            target_groups[gid] = {}
            if group["curfew_type"] == 2:
                for uid in group["black_list"]:
                    target_groups[gid][uid] = 0
                if len(group["black_list"]) == 0:
                    del target_groups[gid]
        elif hour == group["end_time"] and hour != group["start_time"]:
            group["under_curfew"] = False
            target_groups[gid] = {}
            await bot.send_group_msg(group_id=group['group_id'], message='宵禁结束')
            save_all_data()
        return


@sv.on_fullmatch("开始群宵禁")
async def curfew_start(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    gid = ev.group_id
    group = get_group(gid)
    await bot.send(ev, '宵禁开始')
    group["under_curfew"] = True
    if group["curfew_type"] == 0:
        await bot.set_group_whole_ban(group_id=gid, enable=True)
    elif group["curfew_type"] == 1:
        if "black_list" in group and len(group["black_list"]) > 0:
            for uid in group["black_list"]:
                duration = abs(group["start_time"] - group["end_time"]) * 3600
                await silence(ev, uid=uid, duration=duration)
    elif 2 <= group["curfew_type"] <= 4:
        target_groups[gid] = {}
        if group["curfew_type"] == 2:
            for uid in group["black_list"]:
                target_groups[gid][uid] = 0
            if len(group["black_list"]) == 0:
                del target_groups[gid]
    return


@sv.on_fullmatch("结束群宵禁")
async def curfew_stop(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    gid = ev.group_id
    group = get_group(gid)
    group["under_curfew"] = False
    save_all_data()
    await bot.send(ev, message='宵禁结束')
    if group["curfew_type"] == 0:
        await bot.set_group_whole_ban(group_id=gid, enable=False)
    elif group["curfew_type"] == 1:
        if "black_list" in group and len(group["black_list"]) > 0:
            for uid in group["black_list"]:
                await lift_silence(ev, uid=uid)
    elif group["curfew_type"] == 2 or group["curfew_type"] == 3:
        target_groups[gid] = {}
    return


@sv.on_message('group')
async def curfew_listener(bot, ev):
    gid = ev.group_id
    group = get_group(gid)

    # 上等人管不了
    if hoshino.priv.check_priv(ev, hoshino.priv.ADMIN) or get_user_level(gid, ev.user_id) > config.limit_level:
       return
    # 非宵禁中的屏蔽词检测
    if group["literary_inquisition"]:
        if len(group["keywords"]) == 0:
            return
        if keyword_in_msg(ev.message.extract_plain_text(), group["keywords"]):
            if group["curfew_msg_notice"]:
                await bot.send(ev, f"检测到[CQ:at,qq={ev.user_id}]发送违规消息")
            await bot.delete_msg(message_id=ev.message_id, self_id=ev.self_id)
            if config.speech_duration > 0:
                await silence(ev, config.increase)

    # 非目标群
    if ev.group_id not in target_groups.keys():
        return
    # 非宵禁状态或非有效类型
    if not group["curfew"] or not group["under_curfew"] or group["curfew_type"] < 2:
        return
    uid = ev.user_id
    # 黑名单模式但没有黑名单
    if group["curfew_type"] == 2 and uid not in group["black_list"]:
        return
    # 关键词模式
    if group["curfew_type"] == 4:
        # 没有关键词
        if len(group["keywords"]) == 0:
            return
        # 没匹配到关键词
        if not keyword_in_msg(ev.message.extract_plain_text(), group["keywords"]):
            return
    # 未触发消息类型、字数限制
    elif (msg_type_check(ev.message, group["curfew_msg_type"]) and
            (group["curfew_msg_len"] == 0 or len(ev.message.extract_plain_text().strip()) < group["curfew_msg_len"])):
        return
    # 计数+1
    if uid not in target_groups[gid]:
        target_groups[gid][uid] = 1
    else:
        target_groups[gid][uid] += 1
    # 计算时长
    ban_time = config.base_duration * (config.increase ** (target_groups[gid][uid] - 1) - 1)
    if group["curfew_msg_notice"]:
        await bot.send(ev, f"检测到[CQ:at,qq={uid}]第{target_groups[gid][uid]}次发送违规消息")
    # 转发到群聊
    if group["curfew_msg_forward"] > 0:
        user_name = await get_user_name(ev)
        forward_gid = 0
        if group["curfew_msg_forward"] != ev.group_id:
            group_list = await bot.get_group_list(self_id=ev.self_id)
            for g in group_list:
                if g['group_id'] == group["curfew_msg_forward"]:
                    forward_gid = g['group_id']
                    break
        else:
            forward_gid = ev.group_id
        if forward_gid != 0:
            forward_msg = [{
                "type": "node",
                "data": {
                    "name": user_name,
                    "uin": str(uid),
                    "content": ev.raw_message
                }
            }]
            await bot.send_group_forward_msg(group_id=forward_gid, messages=forward_msg)
    # 撤回并禁言
    await bot.delete_msg(message_id=ev.message_id, self_id=ev.self_id)
    if ban_time > 0:
        await silence(ev, ban_time)


def msg_type_check(msg, white_list):
    # https://docs.go-cqhttp.org/cqcode
    # white_list = "text,at,face,mface,reply,forward,record,poke,tts,gift,cardimage,redbag,music,location,share,rps,dice,video,image,file,json"
    for m in msg:
        if "type" not in m:
            continue
        if m['type'] not in white_list:
            return False
    return True


@sv.on_prefix('群宵禁')
async def curfew_cmd(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    args = ev.message.extract_plain_text().strip().split()
    group = get_group(str(ev.group_id))
    if len(args) == 1:
        if args[0] == '启用' or args[0] == 'on':
            group["curfew"] = True
            msg = "已启用宵禁，当前配置:\n"
            msg += f"类型：{curfew_type[group['curfew_type']]}\n"
            if group['curfew_type'] == 2 or group['curfew_type'] == 3:
                msg += f"允许消息类型：{group['curfew_msg_type']}\n"
            msg += f"时间：{group['start_time']}点-{group['end_time']}点\n"
            msg += f"字数限制：{group['curfew_msg_len']}\n"
            msg += f"消息转发：{group['curfew_msg_forward']}\n"
            msg += f"违规警告：{group['curfew_msg_notice']}"
            save_all_data()
            await bot.finish(ev, msg)
        elif args[0] == '禁用' or args[0] == 'off':
            group["curfew"] = False
            group["under_curfew"] = False
            save_all_data()
            await bot.finish(ev, "已禁用宵禁")
        else:
            await bot.finish(ev, "参数错误")

    if len(args) != 2:
        await bot.finish(ev, "参数错误")

    if args[0] == "类型" or args[0].lower() == "type":
        if args[1].isdigit():
            ctype = int(args[1])
            if 0 <= ctype < 5:
                group["curfew_type"] = ctype
                save_all_data()
                await bot.finish(ev,f"设置成功，当前宵禁类型为[{curfew_type[ctype]}]")
            else:
                await bot.finish(ev, "参数错误，宵禁类型取值范围：0-4")
        else:
            await bot.finish(ev, "参数错误，宵禁类型取值范围：0-4")

    if args[0] == "时间":
        time_split = args[1].replace('，', ',').split(",")
        if len(time_split) != 2:
            await bot.finish(ev, "参数错误，时间格式应为：起始小时,结束小时")
        try:
            start_time = int(time_split[0])
            end_time = int(time_split[1])
        except ValueError:
            await bot.send(ev, "参数错误，时间格式应为：起始小时,结束小时")
            return
        if 0 <= start_time <= 23 and 0 <= end_time <= 23:
            group["start_time"] = start_time
            group["end_time"] = end_time
            save_all_data()
            await bot.finish(ev, f"设置成功，当前时间段为{start_time}点-{end_time}点")
        else:
            await bot.finish(ev, "参数错误，时间格式应为：起始小时,结束小时")

    if args[0] == "字数限制":
        if args[1].isdigit():
            group["curfew_msg_len"] = int(args[1])
            save_all_data()
            await bot.finish(ev, f"设置成功，当前字数限制为{int(args[1])}")
        else:
            await bot.finish(ev, "参数错误，字数限制应为整数")

    if args[0] == "转发":
        if not args[1].isdigit():
            await bot.finish(ev, "参数错误，请输入0或转发目标群号")
        group["curfew_msg_forward"] = int(args[1])
        if args[1] == 0:
            await bot.send(ev, "已禁用消息转发")
        else:
            await bot.send(ev, f"设置成功，当前消息转发目标群为 {args[1]}")
        save_all_data()
        return

    if args[0] == "违规警告":
        if args[1] == "启用" or args[1] == "on":
            group["curfew_msg_notice"] = True
            await bot.send(ev, "已启用违规警告")
        elif args[1] == "禁用" or args[1] == "off":
            group["curfew_msg_notice"] = False
            await bot.send(ev, "已禁用违规警告")
        else:
            await bot.finish(ev, "参数错误，违规警告取值范围：启用/on、禁用/off")
        save_all_data()
        return


@sv.on_prefix("宵禁名单")
async def add_to_black_list(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    cmd = ev.message.extract_plain_text().strip()
    users = list_at_users(ev.message)
    msg = ""
    if cmd == "添加":
        users_id = add_black_list(ev.group_id, users)
        msg = "添加成功，"
    elif cmd == "删除":
        users_id = del_black_list(ev.group_id, users)
        msg = "删除成功，"
    else:
        users_id = get_black_list(ev.group_id)
    users_name = await get_users_name(ev, users_id)
    await bot.send(ev, msg + "当前宵禁名单：\n" + '\n'.join(users_name))


@sv.on_prefix("群屏蔽词")
async def literary_inquisition(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    group = get_group(ev.group_id)
    args = ev.message.extract_plain_text().strip().replace("  ", " ").split(" ", 1)
    if args[0] == "添加":
        if args[1] not in group["keywords"]:
            group["keywords"].append(args[1])
            await bot.send(ev, "添加成功")
        else:
            await bot.send(ev, "该关键词已存在")
    elif args[0] == "删除":
        if args[1] in group["keywords"]:
            group["keywords"].remove(args[1])
            await bot.send(ev, "删除成功")
        else:
            await bot.send(ev, "该关键词不存在")
    elif args[0] == "清空":
        group["keywords"] = []
        await bot.send(ev, "已清空")
    elif args[0] == "on" or args[0] == "开启":
        group["literary_inquisition"] = True
        await bot.send(ev, "已启用")
    elif args[0] == "off" or args[0] == "关闭":
        group["literary_inquisition"] = False
        await bot.send(ev, "已禁用")
    else:
        await bot.send(ev, f"【屏蔽词列表】\n{group['keywords']}")



def keyword_in_msg(msg, keywords):
    for kw in keywords:
        if kw in msg:
            return True
    return False

