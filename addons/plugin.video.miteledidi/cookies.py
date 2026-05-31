
from plugintools import find_single_match

# url = requests.get('https://pastebin.com/raw/RG4CUX4p',headers=headers).text
# gmid = requests.get('https://pastebin.com/raw/gnz2qkVE',headers=headers).text

GMID = "gmid=gmid.ver4.AtLt8k4V6A.5Kt9Om8B8H72kqDYUwevTpcTcJudgWf9fCgojlCzzyrZM3ZxAh0Y8sg9bqCiUd3y.emqVgH6O1rV0Dhm17cYTbv2SFGVAufHLUH-GkERwUoVPtOHNK0W4gqQZCQNlqQN1JcUSfI9sW8W6JhqaeDRqhQ.sc3; ucid=3nIeQuA68LNQBQ0oP292xw; hasGmid=ver4"
COOKIE = "include=profile%2Cdata&extraProfileFields=username&lang=es&APIKey=3_-Io69iQoOPkTetSCpOyyuCH7KLUHfBQXFl3DADd-tYAPdlcT47Mp43nFJGr5kHpt&sdk=js_latest&login_token=st2.s.AtLt04QX0A.MnQUaDY5RnYAVBD8V-j0gkYkLtfIlIkAxLZQfA8M4n0YwttbZZbUROByniQft0nRGJdKCmu9WuzGc1qNuepEhRpRoEkB-Ru11xYuFdAYcvTsSGD_Xfo1yjcyf_2PC9ad.PyDgh-xXsdUeS5JwgkjXvC-eC7lKl0AAhOOgRYR-slg3UEcVXOH9Zow9rw08ep99R4UZVKAjXIPj6_CgLxiNkw.sc3&authMode=cookie&pageURL=https%3A%2F%2Fwww.mitele.es%2Fprogramas-tv%2Fmadres-desde-el-corazon%2Ftemporada-1%2Fepisodios%2Fprograma-3-40_015018833%2Fplayer%2F&sdkBuild=17112&format=json"

def get_cookies():
    cookies = find_single_match(COOKIE,'APIKey=(.*?)&sdk=js_latest&login_token=(.*?)&authMode=')
    return (cookies[0], cookies[1], GMID)