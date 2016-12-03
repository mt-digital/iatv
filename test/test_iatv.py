import responses

from difflib import Differ

from iatv.iatv import Show, DOWNLOAD_BASE_URL


@responses.activate
def test_srt_building():
    '''
    SRT should have contiguous, continuous timings; each response from IATV starts at 00:00:00
    '''
    test_show_id = 'Test_Show'

    url1 = DOWNLOAD_BASE_URL + test_show_id + '/' +\
        test_show_id + '.cc5.srt?t=0/60'
    url2 = DOWNLOAD_BASE_URL + test_show_id + '/' +\
        test_show_id + '.cc5.srt?t=61/120'

    with responses.RequestsMock() as rsps:

        rsps.add(responses.GET,
                 'https://archive.org/details/Test_Show?output=json',
                 json={'metadata':
                       {'title': ['test show'],
                        'runtime': ['01:00:00']}
                       },
                 content_type='application/json',
                 status=200,
                 match_querystring=True)

        srt1 = '''1
00:00:00,000 --> 00:00:10,312
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.

2
00:00:10,312 --> 00:00:60,101
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.
'''

        # it is realistic to have 3 and 4 b/c for some reason IATV is like this
        srt2 = '''3
00:00:00,000 --> 00:00:30,312
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.

4
00:00:30,312 --> 00:00:60,002
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.
'''

        expected_srt = open('test/data/expected.srt', 'r').read()

        rsps.add(responses.GET, url1, body=srt1,
                 match_querystring=True)

        rsps.add(responses.GET, url2, body=srt2,
                 match_querystring=True)

        s = Show(test_show_id)

        s.get_transcript(end_time=120)

        assert s.metadata == {'title': [],
                              'runtime': []}

        assert s.srt == expected_srt, show_string_diff(
            s.srt, expected_srt)

        expected_transcript = [
            u'* EN-US Transcript * This is an example SRT file, which, while extremely short, is still a valid SRT file. This is an example SRT file, which, while extremely short, is still a valid SRT file. This is an example SRT file, which, while extremely short, is still a valid SRT file. This is an example SRT file, which, while extremely short, is still a valid SRT file.  '
        ]

        assert s.transcript == expected_transcript


def show_string_diff(s1, s2):
    """ Writes differences between strings s1 and s2 """
    d = Differ()
    diff = d.compare(s1.splitlines(), s2.splitlines())
    diffList = [el for el in diff
                if el[0] != ' ' and el[0] != '?']

    for l in diffList:

        if l[0] == '+':
            print('+' + bcolors.GREEN + l[1:] + bcolors.ENDC)
        elif l[0] == '-':
            print('-' + bcolors.RED + l[1:] + bcolors.ENDC)
        else:
            assert False, 'Error, diffList entry must start with + or -'


class bcolors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
