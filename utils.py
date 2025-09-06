import re
from datetime import timedelta


def get_time(kw):
    match = re.search(r'(?P<num>[0-9]+)(?P<tp>小时|天|分|分钟)', kw)
    if match and int(match.group('num')) > 0:
        time = { '小时': 0, '分钟': 0, '天': 0 }
        t = match.group('tp')
        t = t if t != '分' else '分钟'
        time[t] = int(match.group('num'))
        return timedelta(days=time['天'], minutes=time['分钟'], hours=time['小时'])
    else:
        return timedelta(minutes=5)


def get_time_text(seconds):
    if seconds > 3600:
        return f"{int(seconds / 3600)}小时{int(seconds % 3600 / 60)}分"
    elif seconds > 60:
        return f"{int(seconds / 60)}分{seconds % 60}秒"
    elif seconds > 0:
        return f"{seconds}秒"
    else:
        return "0秒"


def list_at_users(msg):
    result = []
    for m in msg:
        if m.type == 'at' and m.data['qq'] != 'all':
            uid = int(m.data['qq'])
            result.append(uid)
    return result


