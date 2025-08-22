import asyncio
from datetime import timedelta, datetime
from hoshino import Service, priv
from hoshino.util import DailyNumberLimiter
from .core import *
from .config import VoteConfig
from .utils import get_time_text, list_at_users

help_msg = '''
举报@对象[关键词]: 投票禁言
投反对票@对象: 消掉一票
查询举报关键词: 获取支持的举报关键词，在投票后加上关键词会计入严重违规
刷新cd/重置投票+@对象1@对象…
'''

sv = Service('德谟克拉西', enable_on_default=False, help_=help_msg)

config = VoteConfig()
votes_limit = DailyNumberLimiter(config.daily_limit)

group_data = {}


def is_serious_model(text):
    for word in config.serious_words:
        if word in text:
            return True
    return False


class Elect:
    def __init__(self):
        self.votes = []
        self.votes_count = 0
        self.serious_count = 0
        self.ban_duration = config.default_ban_duration
        self.timeout = datetime.now() + timedelta(seconds=config.default_timeout)
        self.executing = False


@sv.on_prefix('举报')
async def vote(bot, ev):
    if not votes_limit.check(ev.user_id) and not priv.check_priv(ev, priv.SUPERUSER) and not has_tag(ev.group_id, ev.user_id, "无限投票"):
        await bot.send(ev, f"你今天已经投过{config.daily_limit}票了", at_sender=True)
        return
    gid = ev.group_id
    if get_user_level(gid, ev.user_id) < config.voting_rights:
        await bot.send(ev, f'[CQ:reply,id={ev.message_id}]' + "你没有投票权")
        return
    uid = 0
    for m in ev.message:
        if m.type == 'at' and m.data['qq'] != 'all':
            uid = int(m.data['qq'])
            break
    if uid == 0:
        return
    if uid == ev.self_id or await check_user_role(ev, uid) or get_user_level(gid, uid) == 4:
        await bot.send(ev, f'[CQ:reply,id={ev.message_id}]' + "堂下何人状告本官？")
        return
    # 地位差2无法投票
    if get_user_level(gid, uid) > get_user_level(gid, ev.user_id) + 1:
        await bot.send(ev, f'[CQ:reply,id={ev.message_id}]' + "泥腿子反了天了？")
        return
    text = ev.message.extract_plain_text().strip()
    # 匹配严重违规关键词
    serious = is_serious_model(text)
    if gid not in group_data:
        group_data[gid] = {}
    # 发起新投票
    if uid not in group_data[gid]:
        if get_user_level(gid, ev.user_id) < config.initiate_voting_rights:
            await bot.send(ev, f'[CQ:reply,id={ev.message_id}]' + "以您的群地位无法发起投票")
            return
        group_data[gid][uid] = Elect()
        if config.votes_offset != 0 and not serious:
            group_data[gid][uid].votes_count += -1 * config.votes_offset * (get_user_level(gid, uid) - basic_config.default_level)
    elect = group_data[gid][uid]
    # 超时重新开始投票
    if not elect.executing:
        if elect.timeout <= datetime.now():
            dt = int((elect.timeout + timedelta(seconds=config.interval_time) - datetime.now()).total_seconds())
            if dt > 0:
                await bot.send(ev, f"投票CD中 ({get_time_text(dt)}/{get_time_text(config.interval_time)})")
                return
            if get_user_level(gid, ev.user_id) < config.initiate_voting_rights:
                await bot.send(ev, f'[CQ:reply,id={ev.message_id}]' + "以您的群地位无法发起投票")
                return
            elect = Elect()
            if config.votes_offset != 0 and not serious:
                elect.votes_count += -1 * config.votes_offset * (get_user_level(gid, uid) - basic_config.default_level)
            group_data[gid][uid] = elect
        else:
            # 非执行中投票，时间延长
            elect.timeout += timedelta(seconds=config.add_timeout)

    # 投票累加
    if ev.user_id in elect.votes and not priv.check_priv(ev, priv.SUPERUSER) and not has_tag(ev.group_id, ev.user_id, "无限投票"):
        await bot.send(ev, "你已经投过票了", at_sender=True)
        return
    else:
        elect.votes.append(ev.user_id)
        elect.votes_count += 1
        if config.votes_offset != 0 and not serious and elect.serious_count == 0:
            offset = max(config.votes_offset * (get_user_level(gid, ev.user_id) - basic_config.default_level), 0)
            elect.votes_count += offset
        num = config.ban_threshold - elect.votes_count
        if num > 0:
            await bot.send(ev, f"投票成功，当前票数：{elect.votes_count}, 还差{num}票")
        elif num < 0:
            await bot.send(ev, f"投票成功，累加{-num}票")
    if serious:
        elect.serious_count += 1
    votes_limit.increase(ev.user_id)
    # 投票数达到阈值
    if elect.votes_count >= config.ban_threshold and not elect.executing:
        elect.executing = True
        elect.timeout = datetime.now() + timedelta(seconds=config.execution_time)
        await bot.send(ev, f"票数达标，{config.execution_time}秒后对[CQ:at,qq={uid}]执行禁言，期间投票将累加禁言时间")
        # 等待执行
        await asyncio.sleep(config.execution_time)
        # 重新获取数据
        elect = group_data[gid][uid]
        # 计算禁言时间
        magnification1 = config.add_ban_duration ** (elect.votes_count - config.ban_threshold)
        magnification2 = 1
        await bot.send(ev, f"开始执行，累计投票数：{elect.votes_count}，禁言倍率：{round(magnification1, 2)}倍")
        serious_model = elect.serious_count / elect.votes_count >= config.serious_threshold_scale
        if serious_model:
            deduction_count = 0
            if config.probation > 0:
                deduction_count = add_deduction_count(gid, uid, config.probation)

            elect.ban_duration = config.serious_ban_duration
            history_ban_count = add_ban_count(gid, uid)
            magnification2 = config.repeat_offender ** (history_ban_count - 1 - deduction_count)
            if history_ban_count > 0:
                await bot.send(ev,
                               f"[CQ:at,qq={uid}]严重违规累计{history_ban_count} ({-1 * deduction_count})次，额外倍率：{round(magnification2, 2)}倍")
        ban_duration = elect.ban_duration * magnification1 * magnification2
        if ban_duration > config.duration_limit:
            ban_duration = config.duration_limit
        # 删除投票数据
        if config.interval_time <= 0:  # 无CD
            del group_data[gid][uid]
        elect.executing = False

        users = None
        if not serious_model or config.serious_link:
            users = list_link_users(gid, uid)

        # 执行禁言
        await expand_silence(ev, ban_duration, uid, users=users)


@sv.on_prefix(("反对投票", "投反对票"))
async def vote_against(bot, ev):
    if not votes_limit.check(ev.user_id):
        await bot.finish(ev, f"你今天已经投过{config.daily_limit}票了", at_sender=True)
        return
    uids = list_at_users(ev.message)
    if len(uids) == 0:
        return
    uid = uids[0]
    if uid == ev.user_id:
        return
    gid = ev.group_id
    if gid not in group_data or uid not in group_data[gid]:
        return

    elect = group_data[gid][uid]

    if elect.executing:
        return

    if elect.timeout < datetime.now():
        return
    else:
        elect.timeout += timedelta(seconds=config.add_timeout)

    if ev.user_id in elect.votes and not priv.check_priv(ev, priv.SUPERUSER):
        await bot.send(ev, "你已经投过票了", at_sender=True)
        return
    else:
        elect.votes.append(ev.user_id)
        # 删除一票
        if elect.votes_count > 0:
            elect.votes_count -= 1
            if config.votes_offset != 0 and elect.serious_count == 0:
                offset = max(config.votes_offset * (get_user_level(gid, ev.user_id) - 1), 0)
                elect.votes_count -= offset
        elect.serious_count = max(elect.serious_count - 1, 0)
        elect.votes_count = max(elect.votes_count, 0)

    votes_limit.increase(ev.user_id)
    await bot.send(ev, f"反对成功，当前票数：{elect.votes_count}")
    if len(elect.votes) == 0:
        del group_data[gid][uid]


@sv.on_fullmatch("查询举报关键词")
async def query_serious_words(bot, ev):
    await bot.send(ev, f"举报关键词：{config.serious_words}\n阈值：{config.serious_threshold_scale}\n带关键词的投票占比大于阈值时判断为严重违规")


@sv.on_prefix(("刷新cd", "重置投票"))
async def vote_refresh(bot, ev):
    if not await check_user_role(ev, role=config.manager):
        return
    users = list_at_users(ev.message)
    for uid in users:
        del group_data[ev.group_id][uid]
    await bot.send(ev, f"重置完成")



