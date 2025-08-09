import asyncio
import math
from datetime import timedelta, datetime
import random
from hoshino import Service, priv
from hoshino.util import DailyNumberLimiter, FreqLimiter
from .config import GamesConfig
from .core import silence, add_indulgences
from .utils import get_time_text


help_msg = '''`开始传炸弹`: 开始游戏\n
`开始传炸弹大逃杀模式`: 开始大逃杀游戏\n
`传炸弹`: 向后传递炸弹或加入游戏，加入时随机插入位置并强制传递\n
`回传炸弹`: 向前传递炸弹，若上回合为加入游戏则传给加入者\n
`放弃传炸弹`: 投降，从奖池领走一定倍率时长\n
`我直接爆了`: 持有者引爆炸弹'''

sv = Service('击鼓传花', enable_on_default=False, help_=help_msg)

config = GamesConfig()

game_limit = DailyNumberLimiter(config.daily_limit)
game_freq_limit = FreqLimiter(config.freq_limit)

penalty_time = FreqLimiter(config.punishment_duration)

# 已经看不懂了，应该没啥问题吧
class Game:

    def __init__(self, player):
        self.players = [player]
        self.eliminated = []
        self.index = 0
        self.add_index = -1  # 中途加入的位置
        self.count = 0
        self.lock = False
        self.timeout = datetime.now() + timedelta(seconds=config.default_timeout)
        self.prize_pool = config.default_prize_pool
        self.award_num = 0

    def length(self):
        return len(self.players)

    def player_num(self):
        return self.length() + len(self.eliminated)

    def add_player(self, player):
        add_index = random.randint(0, self.length())
        self.players.insert(add_index, player)
        return add_index

    def index_of(self, player):
        try:
            player_index = self.players.index(player)
            return player_index
        except:
            return -1

    def give_up(self, player):
        player_index = self.index_of(player)
        if player_index == -1:
            return -1
        else:
            self.players.remove(player)
            if player_index == self.index:  # 持有者
                self.count += 1
            if self.index >= self.length():
                self.index = 0
            return self.index

    def next_index(self) -> int:
        self.index += 1
        if self.add_index != -1:  # 中途加入
            if self.add_index <= self.index:  # 如果插入在当前位置之前，防止重复传递需要再加一
                self.index += 1
            if self.add_index == self.index:
                self.count += 1
        if self.index >= self.length():
            self.index = 0
        self.count += 1
        return self.index

    def previous_index(self) -> int:
        if self.add_index != -1:  # 回传到中途加入的对象
            self.index = self.add_index
            self.add_index = -1
            return self.index
        self.index -= 1
        if self.index < 0:
            self.index = self.length() - 1
        self.count += 1
        return self.index

    def next(self, player) -> int:  # 返回下一个的index
        player_index = self.index_of(player)
        if player_index == -1:  # 中途加入
            self.add_index = self.add_player(player)
            random_add_timeout = timedelta(seconds=random.randint(config.add_timeout_min, config.add_timeout_max))
            random_add_prize = random.randint(config.add_prize_pool_min, config.add_prize_pool_max)
            self.timeout = self.timeout + random_add_timeout
            self.prize_pool += random_add_prize
            return self.next_index()
        if self.length() == 1:  # 只有一个人无法传递
            return -1
        if self.index != player_index:  # 非炸弹持有者
            return -2
        self.add_index = -1
        return self.next_index()

    def previous(self, player) -> int:  # 回传
        player_index = self.index_of(player)
        if player_index == -1:  # 中途加入不能回传
            return -1
        if self.length() == 1:  # 只有一个人无法传递
            return -1
        if self.index != player_index:  # 非炸弹持有者
            return -2
        return self.previous_index()

    def get_player(self, index):
        return self.players[index]

    def next_msg(self, player, flag=False):
        if flag:
            next_index = self.previous(player)
        else:
            next_index = self.next(player)
        if next_index == -2:
            penalty_time.start_cd(player)
            return f"[CQ:at,qq={player}]非持有者，惩罚{config.punishment_duration}秒CD"
        if next_index == -1:
            return None
        time_left_msg = get_time_text(int((self.timeout - datetime.now()).total_seconds()))
        prize_pool_msg = get_time_text(self.prize_pool)
        return f"{self.count}回合，炸弹在[CQ:at,qq={self.get_player(next_index)}]手上，奖池{prize_pool_msg}，剩余{time_left_msg}"

    def quit_msg(self, player, flag=False):
        next_index = self.give_up(player)
        if next_index == -1:
            return None
        if flag:
            scale = config.battle_royale_scale
            msg = "被淘汰"
        else:
            scale = config.give_up_scale
            msg = "放弃游戏"
        self.eliminated.append(player)
        prize = math.ceil(self.prize_pool * scale)
        prize_msg = get_time_text(prize)
        self.prize_pool -= prize
        if self.prize_pool <= 0:
            self.prize_pool = 0
        return prize, f"[CQ:at,qq={player}]{msg}，喜提{prize_msg}奖励，炸弹在[CQ:at,qq={self.get_player(next_index)}]手上。"


class GameListener:

    def __init__(self):
        self.groups = {}

    def get_group_status(self, gid):
        if gid not in self.groups:
            return False
        return True

    def turn_on(self, gid, uid):
        self.groups[gid] = Game(uid)

    def turn_off(self, gid):
        self.groups.pop(gid)

    def get_game(self, gid) -> Game:
        return self.groups[gid]


gls = GameListener()


@sv.on_prefix(("开始击鼓传花", "开始传炸弹"))
async def game_start(bot, ev):
    gid = ev.group_id
    uid = ev.user_id
    if gls.get_group_status(gid):
        await bot.finish(ev, f"游戏已经存在")
        return

    if not game_limit.check(uid) and not priv.check_priv(ev, priv.ADMIN):
        await bot.finish(ev, f"你今天已经发起过{config.daily_limit}次，无法再次发起", at_sender=True)
        return
    if not game_freq_limit.check(1):
        await bot.finish(ev, f"游戏CD中，请等待{get_time_text(game_freq_limit.left_time(1))}")
        return

    text = ev.message.extract_plain_text().strip()
    battle_royale = config.battle_royale
    award_num = random.randint(config.award_min, config.award_max)
    msg = f"游戏开始，炸弹在[CQ:at,qq={uid}]手上，奖池{get_time_text(config.default_prize_pool)}，剩余时间{get_time_text(config.default_timeout)}，"
    if text == "大逃杀模式":
        battle_royale = True
        msg = "大逃杀" + msg
    if battle_royale and config.battle_royale_award_probability > 0:
        msg += f"吃鸡奖励：{award_num}个圣盾术(概率{config.battle_royale_award_probability})，"
    elif not battle_royale and config.award_probability > 0:
        msg += f"击杀奖励：{award_num}个圣盾术(概率{config.award_probability})，"
    msg += f"发送`传炸弹`加入游戏，更多玩法发送`帮助击鼓传花`查询。"
    gls.turn_on(gid, uid)
    await bot.send(ev, msg)
    game = gls.get_game(gid)
    game.award_num = award_num
    if battle_royale:
        round_count = 0
        while gls.get_group_status(gid):
            if game.length() <= 1 and game.count > 0:
                gls.turn_off(gid)
                break
            if game.timeout <= datetime.now():
                game.lock = True
                if game.count == 0:
                    await bot.send(ev, f"游戏结束，无人参与")
                    gls.turn_off(gid)
                    return
                round_count += 1
                loser = game.get_player(game.index)
                prize, msg = game.quit_msg(loser, True)
                next_timeout = math.ceil((config.default_timeout +
                                          (game.length() * (config.add_timeout_max + config.add_timeout_min) / 2)) *
                                         (config.battle_royale_timeout_scale / round_count * 1.2))
                if next_timeout < 10:
                    next_timeout = 10
                msg += f"，剩余时间{get_time_text(next_timeout)}"
                await bot.send(ev, msg)
                await silence(ev, prize, loser)
                game.timeout = datetime.now() + timedelta(seconds=next_timeout)
                game.lock = False
            if random.random() <= config.add_timeout_prob:
                random_change = timedelta(seconds=random.randint(-2, 2))
                game.timeout += random_change
            await asyncio.sleep(0.4)
        game_limit.increase(uid)
        game_freq_limit.start_cd(1)
        winner = game.get_player(game.index)
        msg = f"游戏结束，恭喜[CQ:at,qq={winner}]获得胜利！"
        if random.random() <= config.battle_royale_award_probability:
            if config.award_max_threshold > 2 and game.player_num() < config.award_max_threshold:
                if game.player_num() == 2:
                    game.award_num = 0
                    msg += "参与人数不足3人，"
                else:
                    scale = game.player_num() / config.award_max_threshold
                    game.award_num = math.ceil(game.award_num * scale)
                    msg += f"参与人数不足{config.award_max_threshold}人，"
            msg += f"获得奖励:{game.award_num}个圣盾术。"
            add_indulgences(gid, winner, game.award_num)
        await bot.send(ev, msg)
    else:
        while gls.get_group_status(gid):
            if game.timeout <= datetime.now():
                gls.turn_off(gid)
                break
            if random.random() <= config.add_timeout_prob:
                game.timeout += timedelta(seconds=random.randint(-2, 2))
            await asyncio.sleep(0.4)
        if game.count == 0:
            if config.unmanned_pool <= 0:
                await bot.send(ev, f"游戏结束，无人参与")
                return
            else:
                game.prize_pool = config.unmanned_pool
        game_limit.increase(uid)
        game_freq_limit.start_cd(1)
        loser = game.get_player(game.index)
        killer = game.get_player(game.previous_index())
        msg = ""
        if game.prize_pool <= 0:
            msg = f"游戏结束，恭喜[CQ:at,qq={loser}]，但是禁言奖池已经空了，击杀者为[CQ:at,qq={killer}]"
        else:
            msg = f"游戏结束，恭喜[CQ:at,qq={loser}]喜提{get_time_text(game.prize_pool)}，击杀者为[CQ:at,qq={killer}]"
        if random.random() <= config.award_probability:
            if config.award_max_threshold > 2 and game.player_num() < config.award_max_threshold:
                if game.player_num() == 2:
                    game.award_num = 0
                    msg += "参与人数不足3人，"
                else:
                    scale = game.player_num() / config.award_max_threshold
                    game.award_num = math.ceil(game.award_num * scale)
                    msg += f"参与人数不足{config.award_max_threshold}人，"
            msg += f"，获得:{game.award_num}个圣盾术。"
            add_indulgences(gid, killer, game.award_num)
        await bot.send(ev, msg)
        await silence(ev, game.prize_pool, loser)


@sv.on_fullmatch("传炸弹")
async def pass_the_parcel(bot, ev):
    if not gls.get_group_status(ev.group_id):
        return
    if not penalty_time.check(ev.user_id):
        await bot.send(ev, f"[CQ:at,qq={ev.user_id}]cd中违反规则，重置cd。")
        penalty_time.start_cd(ev.user_id)
        return
    game = gls.get_game(ev.group_id)
    if game.lock:
        return
    if ev.user_id in game.eliminated:
        await bot.send(ev, f"[CQ:at,qq={ev.user_id}]你已经似了。")
        return
    if ev.user_id not in game.players and game.length() <= len(game.eliminated):
        await bot.send(ev, f"[CQ:at,qq={ev.user_id}]大逃杀模式过半无法加入。")
        return
    msg = game.next_msg(ev.user_id)
    if msg is None:
        return
    await bot.send(ev, msg)


@sv.on_fullmatch("回传炸弹")
async def pass_back_the_parcel(bot, ev):
    if not gls.get_group_status(ev.group_id) or not config.pass_back:
        return
    if not penalty_time.check(ev.user_id):
        await bot.send(ev, f"[CQ:at,qq={ev.user_id}]cd中违反规则，重置cd。")
        penalty_time.start_cd(ev.user_id)
        return
    game = gls.get_game(ev.group_id)
    if game.lock:
        return
    msg = game.next_msg(ev.user_id, True)
    if msg is None:
        return
    await bot.send(ev, msg)


@sv.on_fullmatch(("退出击鼓传花", "退出传炸弹", "放弃传炸弹"))
async def give_up(bot, ev):
    if not gls.get_group_status(ev.group_id):
        return
    game = gls.get_game(ev.group_id)
    prize, msg = game.quit_msg(ev.user_id)
    if msg is None:
        return
    if random.random() <= config.award_deduction_probability:
        game.award_num -= 1
        msg += f"奖池减少1个圣盾术。"
    await silence(ev, prize)
    await bot.send(ev, msg)


@sv.on_fullmatch("我直接爆了")
async def explosion(bot, ev):
    if not gls.get_group_status(ev.group_id):
        return
    game = gls.get_game(ev.group_id)
    if game.get_player(game.index) != ev.user_id:
        return
    game.timeout = datetime.now()
    await bot.send(ev, f"第{game.count}回合，[CQ:at,qq={ev.user_id}]自爆")
