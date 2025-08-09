import os
import json
import copy
import hoshino
import math
import time
from aiocqhttp.exceptions import ActionFailed
from .config import BasicConfig, CurfewConfig
from .utils import get_time_text

base_path = os.path.dirname(__file__)
data_path = os.path.join(base_path, 'data.json')

group_default = {
    "users": {},
    "curfew": False,
    "under_curfew": False,
    "curfew_type": 0,
    "curfew_msg_type": copy.deepcopy(CurfewConfig().type_list),
    "curfew_msg_len": 0,
    "curfew_msg_forward": 0,
    "curfew_msg_notice": True,
    "literary_inquisition": False,
    "start_time": 0,
    "end_time": 0,
    "black_list": [],
    "keywords": [],
}
user_default = {
    "indulgences": 1,
    "level": BasicConfig().default_level,
    "tags": {},
    "ban_count": 0,
    "deduction_count": 0,
    "update_time": 0,
    "link_to": [],
    "temp": 0,
}
data = {"groups": {}}
basic_config = BasicConfig()


def get_black_list(gid):
    return get_group(gid)["black_list"]

def add_black_list(gid, black_list):
    group = get_group(gid)
    for bl in black_list:
        if bl not in group["black_list"]:
            group["black_list"].append(bl)
    save_all_data()
    return group["black_list"]

def del_black_list(gid, black_list):
    group = get_group(gid)
    for bl in black_list:
        if bl in group["black_list"]:
            group["black_list"].remove(bl)
    save_all_data()
    return group["black_list"]

def save_all_data():
    global data
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return

def load_all_data():
    global data
    if os.path.exists(data_path):
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        save_all_data()
    return

load_all_data()


def get_group(gid):
    gid = str(gid)
    if gid not in data["groups"]:
        data["groups"][gid] = copy.deepcopy(group_default)
        save_all_data()
    return data["groups"][gid]


def list_group_users(gid):
    return get_group(gid)["users"]


def get_user(gid, uid):
    uid = str(uid)
    group_users = list_group_users(gid)
    if uid not in group_users:
        group_users[uid] = copy.deepcopy(user_default)
        save_all_data()
    return group_users[uid]


def list_user_tags(gid, uid):
    return get_user(gid, uid)["tags"]


def list_users_by_tag(gid, key, value=""):
    result = []
    users = list_group_users(gid)
    for uid, user in users.items():
        if key in user["tags"].keys():
            if value != "":
                if user["tags"][key] == value:
                    result.append(uid)
            else:
                result.append(uid)
    return users

def has_tag(gid, uid, tag, value=""):
    tags = list_user_tags(gid, uid)
    if value != "" and tag in tags and tags[tag] == value:
        return True
    elif value == "" and tag in tags:
        return True
    return False

def set_user_tag(gid, uid, tag, value):
    user = get_user(gid, uid)
    user["tags"][tag] = value
    save_all_data()
    return

def del_user_tag(gid, uid, tag):
    user = get_user(gid, uid)
    if tag in user["tags"].keys():
        del user["tags"][tag]
        save_all_data()
    return

def list_link_users(gid, uid):
    user = get_user(gid, uid)
    return user["link_to"]


def add_link_user(gid, users):
    if len(users) <= 1:
        return
    for uid in users:
        user = get_user(gid, uid)
        for add_id in users:
            if add_id not in user["link_to"] and uid != add_id:
                user["link_to"].append(add_id)
    save_all_data()
    return


def del_link_user(gid, users):
    if len(users) == 0:
        return
    if len(users) == 1:
        user = get_user(gid, users[0])
        user["link_to"] = []
    else:
        for uid in users:
            user = get_user(gid, uid)
            for del_id in users:
                if del_id in user["link_to"]:
                    user["link_to"].remove(del_id)
    save_all_data()
    return


def add_ban_count(gid, uid):
    user = get_user(gid, uid)
    user["ban_count"] += 1
    save_all_data()
    return user["ban_count"]


def add_deduction_count(gid, uid, probation):
    user = get_user(gid, uid)
    if user["update_time"] == 0:
        user["update_time"] = time.time()
    difference = time.time() - user["update_time"]
    deduction_count = user["deduction_count"] + int(difference / probation)
    if deduction_count > user["ban_count"]:
        deduction_count = user["ban_count"]
    user["deduction_count"] = deduction_count
    return user["deduction_count"]


def use_indulgence(gid, uid, use_num=1, overdrawn=False):
    user = get_user(gid, uid)
    num = user["indulgences"]
    if num < use_num and not overdrawn:
        return False
    user["indulgences"] -= use_num
    save_all_data()
    return True


def add_indulgences(gid, uid, add_num):
    user = get_user(gid, uid)
    user["indulgences"] += add_num
    save_all_data()
    return

def get_indulgences(gid, uid):
    return get_user(gid, uid)["indulgences"]

def set_user_level(gid, uid, n, level_max = 3, level_min = 1):
    user = get_user(gid, uid)
    user["level"] = max(min(user["level"] + n, level_max), level_min)
    save_all_data()
    return user["level"]

def get_user_level(gid, uid):
    return get_user(gid, uid)["level"]

# 禁言加强版
# ev: 传入会话
# duration: 禁言时长（秒）
# user_id: 被禁言的用户id（默认为会话用户）
# skip_su: 是否跳过超级用户（默认跳过）
# need_num: 指定消耗的圣盾术层数（存在时忽略下面两个参数）
# limit: 每层圣盾术抵挡的禁言时长，负数会使用多层圣盾术，0表示不使用圣盾术（默认多层每层12小时）
# deduct: 不足以抵扣时是否使用圣盾术（默认不启用）
# users: 连坐
# apportion：是否分摊
# scale：连坐/分摊 比例
async def expand_silence(ev, duration,
                         user_id=None,
                         skip_su=True,
                         need_num=0,
                         limit=basic_config.indulgences_time_limit,
                         deduct=basic_config.indulgences_deduct,
                         users=None,
                         apportion=basic_config.link_apportion,
                         scale=basic_config.link_scale,
                         ):
    if skip_su and user_id in hoshino.config.SUPERUSERS:
        return
    if user_id is None:
        user_id = ev.user_id
    bot = hoshino.get_bot()

    # 连坐
    if users is not None and len(users) > 0:
        link_duration = 0
        if not apportion and scale >= 0:
            link_duration = math.ceil(duration * scale)
        elif apportion:
            if 0 < scale < 1:
                link_duration = math.ceil((duration - (duration * scale)) / len(users))
                duration = math.ceil(duration * scale)
            elif scale > 1:
                link_duration = math.ceil(duration * (scale - 1) / len(users))
            elif scale <= 0:
                link_duration = math.ceil(duration / (len(users) + 1))
                duration = link_duration
        if link_duration > 0:
            for uid in users:
                await expand_silence(ev, link_duration, uid)

    if duration <= 0:
        await lift_silence(ev, user_id)
        return
    if duration > 2592000:
        duration = 2592000
    indulgences = get_indulgences(ev.group_id, user_id)

    if indulgences <= 0 or basic_config.indulgences_enabled is False:
        await silence(ev, duration, user_id)
        return
    if need_num > 0:
        if indulgences < need_num:
            await silence(ev, duration, user_id)
            return
        if use_indulgence(ev.group_id, user_id, need_num):
            await bot.send(ev, f"[CQ:at,qq={user_id}]消耗了{need_num}层圣盾术，抵挡了禁言")
            return
    if limit == 0:
        await silence(ev, duration, user_id)
    deduction = False
    if limit < 0:
        deduction = True
        limit = -limit
    if duration <= limit:
        if use_indulgence(ev.group_id, user_id):
            await bot.send(ev, f"[CQ:at,qq={user_id}]消耗1层圣盾术，抵挡了禁言")
        return
    if deduction:
        use_num = int(duration / limit)
        if use_num <= indulgences:
            if use_indulgence(ev.group_id, user_id, use_num):
                await bot.send(ev, f"[CQ:at,qq={user_id}]消耗了{use_num}层圣盾术，抵挡了禁言")
                return
        elif deduct:
            duration -= indulgences * limit
            await bot.send(ev,
                           f"[CQ:at,qq={user_id}]消耗了{indulgences}层圣盾术，抵消了{get_time_text(indulgences * limit)}禁言")
            await silence(ev, duration, user_id)
            return
    await silence(ev, duration, user_id)


async def silence(ev, duration, uid=None) -> bool:
    bot = hoshino.get_bot()
    if not await check_user_role(ev, ev.self_id):
        await bot.send(ev, "检测到bot非管理员权限，无法执行，请及时禁用相关功能")
        return False
    if uid is None:
        uid = ev.user_id
    # if not await check_user_role(ev, uid):
    #     return False
    try:
        if duration <= 0:
            duration = 0
        duration = int(duration)
        await hoshino.get_bot().set_group_ban(self_id=ev.self_id, group_id=ev.group_id, user_id=uid, duration=duration)
        return True
    except ActionFailed as e:
        if 'NOT_MANAGEABLE' in str(e):
            return False
        else:
            hoshino.logger.error(f'禁言失败 {e}')
            return False
    except Exception as e:
        hoshino.logger.exception(e)
        return False


async def lift_silence(ev, uid=None) -> bool:
    bot = hoshino.get_bot()
    if not await check_user_role(ev, ev.self_id):
        await bot.send(ev, "检测到bot非管理员权限，无法执行，请及时禁用相关功能")
        return False
    if uid is None:
        uid = ev.user_id
    try:
        await hoshino.get_bot().set_group_ban(self_id=ev.self_id, group_id=ev.group_id, user_id=uid, duration=0)
        return True
    except ActionFailed as e:
        if 'NOT_MANAGEABLE' in str(e):
            return False
        else:
            hoshino.logger.error(f'解除禁言失败 {e}')
            return False
    except Exception as e:
        hoshino.logger.exception(e)
        return False



async def get_group_user(ev, uid):
    bot = hoshino.get_bot()
    if uid is None:
        uid = ev.user_id
    try:
        user = await bot.get_group_member_info(
            self_id=ev.self_id, group_id=ev.group_id, user_id=uid
        )
    except Exception as e:
        print(f"[ERROR] 获取群{ev.group_id}成员{uid}信息失败: {e}")
        return None
    return user

async def get_user_name(ev, uid = None):
    user = await get_group_user(ev, uid)
    if user is not None:
        user_name = user['card'] or user['nickname']
        return user_name + f" ({uid})"
    return str(uid)

async def get_users_name(ev, users):
    result = []
    for uid in users:
        user_name = await get_user_name(ev, uid)
        result.append(user_name)
    return result

async def get_user_role(ev, uid = None):
    user = await get_group_user(ev, uid)
    if user is not None:
        return user['role']
    return None

async def check_user_role(ev, uid = None, role = "admin"):
    if uid is None:
        uid = ev.user_id
    user_role = await get_user_role(ev, uid)
    if user_role is None:
        return False
    if role == "admin":
        return user_role == "admin" or user_role == "owner" or uid in hoshino.config.SUPERUSERS
    elif role == "owner":
        return user_role == "owner" or uid in hoshino.config.SUPERUSERS
    elif role == "superuser":
        return uid in hoshino.config.SUPERUSERS
    return False
