import responses

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

        srt2 = '''1
00:00:00,000 --> 00:00:30,312
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.

2
00:00:30,312 --> 00:00:60,002
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.
'''

        expected_srt = '''1
00:00:00,000 --> 00:00:10,312
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.

2
00:10:00,312 --> 00:00:60,101
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.

3
00:00:60,101 --> 00:01:30,413
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.

4
00:01:30,413 --> 00:02:00,102
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.
'''
        rsps.add(responses.GET, url1, body=srt1,
                 match_querystring=True)

        rsps.add(responses.GET, url2, body=srt2,
                 match_querystring=True)

        s = Show(test_show_id)

        s.get_transcript(end_time=120)

        assert s.metadata == {'title': [],
                              'runtime': []}

        assert s.srt == expected_srt, s.srt
