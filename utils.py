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


