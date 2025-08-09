import shutil
import os
import hoshino
import configparser

Tags = {"无限投票": ""}

base_path = os.path.dirname(__file__)

# 读取配置文件
if not os.path.exists(os.path.join(base_path, 'config.ini')):
    try:
        shutil.copy(os.path.join(base_path, 'config_example.ini'), os.path.join(base_path, 'config.ini'))
    except Exception as e:
        hoshino.logger.error(f'读取配置文件失败： {e}')
conf = configparser.ConfigParser(allow_no_value=True)
conf.read(os.path.join(base_path, 'config.ini'), encoding='utf-8')

class BasicConfig:
    def __init__(self):
        self.manager = conf.get('BASIC', 'manager', fallback='owner')
        self.indulgences_enabled = conf.getboolean('BASIC', 'indulgences_enabled', fallback=True)
        self.indulgences_time_limit = conf.getint('BASIC', 'indulgences_time_limit', fallback=-28800)
        self.indulgences_deduct = conf.getboolean('BASIC', 'indulgences_deduct', fallback=True)
        self.link_enabled = conf.getboolean('BASIC', 'link_enabled', fallback=False)
        self.link_apportion = conf.getboolean('BASIC', 'link_apportion', fallback=False)
        self.link_scale = conf.getfloat('BASIC', 'link_scale', fallback=0.5)
        self.default_level = conf.getint('BASIC', 'default_level', fallback=2)


class CurfewConfig:
    def __init__(self):
        self.manager = conf.get('CURFEW', 'manager', fallback='admin')
        msg_types = conf.get('CURFEW', 'type_list', fallback='text,at,face,mface,reply,record,tts,gift,redbag,music,location,rps,dice,forward')
        self.type_list = msg_types.replace('，', ',').strip().split(',')
        self.base_duration = conf.getint('CURFEW', 'base_duration', fallback=60)
        self.increase = conf.getint('CURFEW', 'increase', fallback=3)
        self.speech_duration = conf.getint('CURFEW', 'speech_duration', fallback=0)
        self.limit_level = conf.getint('CURFEW', 'limit_level', fallback=1)


class VoteConfig:
    def __init__(self):
        self.manager = conf.get('VOTE', 'manager', fallback='owner')
        self.daily_limit = conf.getint('VOTE', 'daily_limit', fallback=6)
        self.default_timeout = conf.getint('VOTE', 'default_timeout', fallback=180)
        self.add_timeout = conf.getint('VOTE', 'add_timeout', fallback=40)
        self.default_ban_duration = conf.getint('VOTE', 'default_ban_duration', fallback=300)
        self.ban_threshold = conf.getint('VOTE', 'ban_threshold', fallback=5)
        self.add_ban_duration = conf.getfloat('VOTE', 'add_ban_duration', fallback=1.3)
        self.interval_time = conf.getint('VOTE', 'interval_time', fallback=1800)
        self.serious_threshold_scale = conf.getfloat('VOTE', 'serious_threshold', fallback=0.6)
        words = conf.get('VOTE', 'serious_words', fallback='广告,晒卡,r18g,血腥,政,境外势力,贴吧大神,群公告,群规,造反')
        self.serious_words = words.replace('，', ',').strip().split(',')
        self.serious_ban_duration = conf.getint('VOTE', 'serious_ban_duration', fallback=3600)
        self.repeat_offender = conf.getfloat('VOTE', 'repeat_offender', fallback=1.5)
        self.probation = conf.getint('VOTE', 'probation', fallback=259200)
        self.serious_link = conf.getboolean('VOTE', 'serious_link', fallback=False)
        self.duration_limit = conf.getint('VOTE', 'duration_limit', fallback=86400)
        self.execution_time = conf.getint('VOTE', 'execution_time', fallback=30)
        self.votes_offset = conf.getint('VOTE', 'votes_offset', fallback=0)
        self.voting_rights = conf.getint('VOTE', 'voting_rights', fallback=1)
        self.initiate_voting_rights = conf.getint('VOTE', 'initiate_voting_rights', fallback=2)


class GamesConfig:

    def __init__(self):
        self.daily_limit = conf.getint('GAME', 'daily_limit', fallback=1)
        self.freq_limit = conf.getint('GAME', 'freq_limit', fallback=600)
        self.pass_back = conf.getboolean('GAME', 'pass_back', fallback=False)
        self.default_timeout = conf.getint('GAME', 'default_timeout', fallback=40)
        self.add_timeout_min = conf.getint('GAME', 'add_timeout_min', fallback=5)
        self.add_timeout_max = conf.getint('GAME', 'add_timeout_max', fallback=20)
        self.add_timeout_prob = conf.getfloat('GAME', 'add_timeout_prob', fallback=0.05)
        self.prevent_holding = conf.getint('GAME', 'prevent_holding', fallback=3)
        self.default_prize_pool = conf.getint('GAME', 'default_prize_pool', fallback=180)
        self.add_prize_pool_min = conf.getint('GAME', 'add_prize_pool_min', fallback=1)
        self.add_prize_pool_max = conf.getint('GAME', 'add_prize_pool_max', fallback=30)
        self.unmanned_pool = conf.getint('GAME', 'unmanned_pool', fallback=0)
        self.give_up_scale = conf.getfloat('GAME', 'give_up_scale', fallback=0.1)
        self.battle_royale = conf.getboolean('GAME', 'battle_royale', fallback=False)
        self.battle_royale_scale = conf.getfloat('GAME', 'battle_royale_scale', fallback=0.4)
        self.battle_royale_timeout_scale = conf.getfloat('GAME', 'battle_royale_timeout_scale', fallback=0.7)
        self.award_probability = conf.getfloat('GAME', 'award_probability', fallback=0.5)
        self.battle_royale_award_probability = conf.getfloat('GAME', 'battle_royale_award_probability', fallback=0.5)
        self.battle_royale_timeout_min = conf.getint('GAME', 'battle_royale_timeout_min', fallback=10)
        self.award_max = conf.getint('GAME', 'award_max', fallback=3)
        self.award_min = conf.getint('GAME', 'award_min', fallback=1)
        self.award_max_threshold = conf.getint('GAME', 'award_max_threshold', fallback=5)
        self.award_deduction_probability = conf.getfloat('GAME', 'award_deduction_probability', fallback=0.6)
        self.punishment_duration = conf.getint('GAME', 'punishment_duration', fallback=10)


def update():
    # if not conf.has_option("BASIC", "test"):
    #     conf.set("BASIC", "test", '0.1')
    conf.write(open(os.path.join(base_path, 'config.ini'), 'w', encoding='utf-8'))

update()
